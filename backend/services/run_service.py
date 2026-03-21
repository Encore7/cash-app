from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from azure.storage.blob import BlobServiceClient
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from backend.config import settings
from backend.models.bank import BankStatement
from backend.models.core import BlobObject, IngestionRun, Tenant
from backend.models.enums import MatchStatus, RunStatus, SourceType
from backend.models.journal import JournalEntry
from backend.models.reconciliation import ReconciliationMatch
from backend.models.remittance import RemittanceAdviceHeader, RemittanceAdviceLine
from backend.schemas.api import MatchActionResponse
from backend.services.matching_service import generate_match_candidates
from backend.services.parsing_service import parse_bank_statement, parse_remittance
from backend.utils.blob import build_blob_prefix, sha256_bytes


class ServiceError(Exception):
    pass


def _ensure_tenant(db: Session, tenant_code: str) -> Tenant:
    tenant = db.scalar(select(Tenant).where(Tenant.code == tenant_code))
    if tenant:
        return tenant
    tenant = Tenant(
        code=tenant_code, name=tenant_code.replace("-", " ").title(), is_active=True
    )
    db.add(tenant)
    db.flush()
    return tenant


def _get_blob(
    client: BlobServiceClient, container_name: str, prefix: str, suffix: str
) -> tuple[str, bytes]:
    container = client.get_container_client(container_name)
    candidates = [
        b
        for b in container.list_blobs(name_starts_with=prefix)
        if b.name.lower().endswith(suffix)
    ]
    if not candidates:
        raise ServiceError(f"No blob found under prefix={prefix} for suffix={suffix}")
    chosen = sorted(
        candidates, key=lambda b: b.last_modified or datetime.min, reverse=True
    )[0]
    data = container.download_blob(chosen.name).readall()
    return chosen.name, data


def _upsert_blob_object(
    db: Session,
    tenant: Tenant,
    source_type: SourceType,
    business_date,
    blob_path: str,
    payload: bytes,
) -> BlobObject:
    content_hash = sha256_bytes(payload)
    # Strip leading UUID prefix (e.g. "21332fca_Sample Bank Statement.xlsx" → "Sample Bank Statement.xlsx")
    raw_file_name = blob_path.split("/")[-1]
    parts = raw_file_name.split("_", 1)
    original_file_name = (
        parts[1]
        if len(parts) == 2 and len(parts[0]) == 8 and parts[0].isalnum()
        else raw_file_name
    )
    # Atomic INSERT ... ON CONFLICT DO NOTHING: blocks until any competing
    # transaction commits, then skips the insert instead of raising IntegrityError.
    stmt = (
        pg_insert(BlobObject)
        .values(
            id=uuid4(),
            tenant_id=tenant.id,
            source_type=source_type,
            business_date=business_date,
            container_name=settings.azure_raw_container,
            blob_path=blob_path,
            original_file_name=original_file_name,
            content_hash=content_hash,
            size_bytes=len(payload),
        )
        .on_conflict_do_nothing(constraint="uq_blob_dedup")
    )
    db.execute(stmt)
    db.flush()
    return db.scalar(
        select(BlobObject).where(
            BlobObject.tenant_id == tenant.id,
            BlobObject.source_type == source_type,
            BlobObject.business_date == business_date,
            BlobObject.content_hash == content_hash,
        )
    )


def _create_run_if_needed(
    db: Session,
    tenant: Tenant,
    business_date,
    bank_blob: BlobObject,
    rem_blob: BlobObject,
) -> IngestionRun:
    run_id = uuid4()
    # Atomic INSERT ... ON CONFLICT DO NOTHING avoids UniqueViolation when the
    # job-runner and the API endpoint race to create the same run slot.
    stmt = (
        pg_insert(IngestionRun)
        .values(
            id=run_id,
            tenant_id=tenant.id,
            business_date=business_date,
            status=RunStatus.RECEIVED,
            bank_blob_id=bank_blob.id,
            remittance_blob_id=rem_blob.id,
        )
        .on_conflict_do_nothing(constraint="uq_ingestion_run_slot")
    )
    db.execute(stmt)
    db.flush()

    run = db.scalar(
        select(IngestionRun)
        .where(
            IngestionRun.tenant_id == tenant.id,
            IngestionRun.business_date == business_date,
            IngestionRun.bank_blob_id == bank_blob.id,
            IngestionRun.remittance_blob_id == rem_blob.id,
        )
        .order_by(IngestionRun.started_at.desc())
    )
    if run is None:
        raise ServiceError("Could not create or retrieve ingestion run")
    if run.status == RunStatus.FAILED:
        run.status = RunStatus.RECEIVED
        run.error_message = None
        run.review_reason_code = None
        run.finished_at = None
        db.flush()
    return run


def _persist_bank_data(
    db: Session, blob_object: BlobObject, payload: bytes
) -> list[BankStatement]:
    existing = db.scalars(
        select(BankStatement).where(BankStatement.blob_object_id == blob_object.id)
    ).all()
    if existing:
        return list(existing)

    rows = parse_bank_statement(payload)
    statements: list[BankStatement] = []
    for row in rows:
        statement = BankStatement(blob_object_id=blob_object.id, **row)
        db.add(statement)
        statements.append(statement)
    db.flush()
    return statements


def _persist_remittance_data(
    db: Session, blob_object: BlobObject, payload: bytes
) -> tuple[list[RemittanceAdviceLine], list[str]]:
    existing_header = db.scalar(
        select(RemittanceAdviceHeader).where(
            RemittanceAdviceHeader.blob_object_id == blob_object.id
        )
    )
    if existing_header:
        return list(existing_header.lines), []

    report, _, _, _ = parse_remittance(payload)
    normalized = report.normalized
    header = RemittanceAdviceHeader(
        blob_object_id=blob_object.id,
        advice_number=normalized.advice_number,
        advice_date=normalized.advice_date,
        payer_name=normalized.payer_name,
        document_currency=normalized.document_currency,
        total_paid_amount=normalized.total_paid_amount,
    )
    db.add(header)
    db.flush()

    lines: list[RemittanceAdviceLine] = []
    for row in normalized.lines:
        line_payload = row.model_dump(
            include={
                "line_number",
                "invoice_number",
                "invoice_date",
                "paid_amount",
                "currency",
                "customer_reference",
                "raw_line_text",
            }
        )
        line = RemittanceAdviceLine(advice_header_id=header.id, **line_payload)
        db.add(line)
        lines.append(line)
    db.flush()
    return lines, report.reason_codes


def _persist_matches(
    db: Session,
    run: IngestionRun,
    bank_rows: list[BankStatement],
    rem_lines: list[RemittanceAdviceLine],
) -> list[ReconciliationMatch]:
    existing = db.scalars(
        select(ReconciliationMatch).where(ReconciliationMatch.run_id == run.id)
    ).all()
    if existing:
        return existing

    bank_payload = [
        {
            "id": str(row.id),
            "amount": row.amount,
            "bank_reference": row.bank_reference,
            "customer_reference": row.customer_reference,
            "payment_purpose": row.payment_purpose,
        }
        for row in bank_rows
    ]
    rem_payload = [
        {
            "id": str(line.id),
            "invoice_number": line.invoice_number,
            "paid_amount": line.paid_amount,
        }
        for line in rem_lines
    ]

    candidates = generate_match_candidates(bank_payload, rem_payload)
    persisted: list[ReconciliationMatch] = []
    for cand in candidates:
        match = ReconciliationMatch(
            run_id=run.id,
            bank_statement_id=UUID(cand["bank_statement_line_id"]),
            remittance_advice_line_id=(
                UUID(cand["remittance_advice_line_id"])
                if cand["remittance_advice_line_id"]
                else None
            ),
            status=cand["status"],
            match_rule=cand["match_rule"],
            confidence_score=cand["confidence_score"],
            amount_applied=cand["amount_applied"],
            variance_amount=cand["variance_amount"],
            source=cand["source"],
            is_selected=cand.get("is_selected", False),
        )
        db.add(match)
        persisted.append(match)
    db.flush()
    return persisted


# ---------------------------------------------------------------------------
# GL account constants (cash accounting / bank reconciliation)
# ---------------------------------------------------------------------------
_CASH_GL = "100000"  # Bank / cash main account (GL)
_COMPANY_CODE = "1000"  # Default company code (SAP-style)
_DOC_TYPE = "SA"  # Standard accounting document


def _generate_journal_entries(
    db: Session,
    run: IngestionRun,
    bank_rows: list[BankStatement],
    matches: list[ReconciliationMatch],
) -> list[JournalEntry]:
    """Create one Cash GL (100000) journal line per bank transaction.

    When a bank row is matched to a remittance advice, the payment is split
    into one line per invoice (remittance line), mirroring how the payer
    allocated the bulk wire across their open items.

    When a bank row has no remittance match a single line is created using
    the bank reference / customer reference as item text.

    Direction
    ---------
    Inflow  (bank amount ≥ 0) → Debit  GL 100000
    Outflow (bank amount < 0) → Credit GL 100000

    Item text
    ---------
    Remittance-split : "invoice_number/customer_reference" from the remittance line
    Plain bank row   : bank_reference or customer_reference from the bank statement
    """
    existing = db.scalars(
        select(JournalEntry).where(JournalEntry.run_id == run.id)
    ).first()
    if existing:
        return list(
            db.scalars(select(JournalEntry).where(JournalEntry.run_id == run.id)).all()
        )

    # Group selected matches that carry a remittance line, keyed by bank_statement_id
    rem_matches_by_bank: dict[UUID, list[ReconciliationMatch]] = {}
    for m in matches:
        if m.is_selected and m.remittance_advice_line_id:
            rem_matches_by_bank.setdefault(m.bank_statement_id, []).append(m)

    # Index remaining selected matches (no remittance line) for item-text lookup
    plain_match_by_bank: dict[UUID, ReconciliationMatch] = {
        m.bank_statement_id: m
        for m in matches
        if m.is_selected and not m.remittance_advice_line_id
    }

    line_no = 1

    for bank in bank_rows:
        is_inflow = bank.amount >= 0
        posting_date = bank.booking_date
        currency = bank.currency

        rem_matches = rem_matches_by_bank.get(bank.id)

        if rem_matches:
            # ── One journal line per matched remittance invoice ────────────
            for match in rem_matches:
                rl = db.get(RemittanceAdviceLine, match.remittance_advice_line_id)
                # Prefer the remittance line's own paid_amount, fall back to match amount
                if rl and rl.paid_amount is not None:
                    amount = float(rl.paid_amount)
                elif match.amount_applied is not None:
                    amount = abs(float(match.amount_applied))
                else:
                    amount = abs(float(bank.amount))

                parts: list[str] = []
                if rl:
                    if rl.invoice_number:
                        parts.append(rl.invoice_number)
                    if rl.customer_reference:
                        parts.append(rl.customer_reference)
                item_text: str | None = "/".join(parts)[:255] or None

                db.add(
                    JournalEntry(
                        line_number=line_no,
                        run_id=run.id,
                        company_code=_COMPANY_CODE,
                        posting_date=posting_date,
                        document_date=posting_date,
                        document_type=_DOC_TYPE,
                        gl_account=_CASH_GL,
                        debit=amount if is_inflow else None,
                        credit=amount if not is_inflow else None,
                        currency=currency,
                        item_text=item_text,
                        reconciliation_match_id=match.id,
                        bank_statement_id=bank.id,
                        remittance_advice_line_id=match.remittance_advice_line_id,
                    )
                )
                line_no += 1

        else:
            # ── One journal line for the bank row ──────────────────────────
            abs_amount = abs(float(bank.amount))
            parts = []
            if bank.bank_reference:
                parts.append(bank.bank_reference)
            elif bank.customer_reference:
                parts.append(bank.customer_reference)
            item_text = "/".join(parts)[:255] or None

            plain_match = plain_match_by_bank.get(bank.id)

            db.add(
                JournalEntry(
                    line_number=line_no,
                    run_id=run.id,
                    company_code=_COMPANY_CODE,
                    posting_date=posting_date,
                    document_date=posting_date,
                    document_type=_DOC_TYPE,
                    gl_account=_CASH_GL,
                    debit=abs_amount if is_inflow else None,
                    credit=abs_amount if not is_inflow else None,
                    currency=currency,
                    item_text=item_text,
                    reconciliation_match_id=plain_match.id if plain_match else None,
                    bank_statement_id=bank.id,
                    remittance_advice_line_id=None,
                )
            )
            line_no += 1

    db.flush()
    return list(
        db.scalars(select(JournalEntry).where(JournalEntry.run_id == run.id)).all()
    )


def ingest_run_processing_only(
    db: Session, tenant_code: str, business_date
) -> IngestionRun:
    """Download blobs and populate bank_statement + remittance tables only (no matching)."""
    client = BlobServiceClient.from_connection_string(
        settings.azurite_connection_string
    )
    tenant = _ensure_tenant(db, tenant_code)

    bank_prefix = build_blob_prefix(tenant_code, "bank-statement", business_date)
    rem_prefix = build_blob_prefix(tenant_code, "remittance", business_date)

    bank_blob_path, bank_payload = _get_blob(
        client, settings.azure_raw_container, bank_prefix, ".xlsx"
    )
    rem_blob_path, rem_payload = _get_blob(
        client, settings.azure_raw_container, rem_prefix, ".pdf"
    )

    bank_blob = _upsert_blob_object(
        db,
        tenant,
        SourceType.BANK_STATEMENT,
        business_date,
        bank_blob_path,
        bank_payload,
    )
    rem_blob = _upsert_blob_object(
        db, tenant, SourceType.REMITTANCE, business_date, rem_blob_path, rem_payload
    )

    run = _create_run_if_needed(db, tenant, business_date, bank_blob, rem_blob)
    # If already processed beyond RECEIVED, skip re-parsing
    if run.status not in {RunStatus.RECEIVED, RunStatus.FAILED}:
        return run

    _persist_bank_data(db, bank_blob, bank_payload)
    _persist_remittance_data(db, rem_blob, rem_payload)
    bank_blob.is_parsed = True
    rem_blob.is_parsed = True
    run.status = RunStatus.PARSED
    db.flush()
    return run


def run_matching_for_parsed_runs(
    db: Session, tenant_codes: list[str] | None = None
) -> list[ReconciliationMatch]:
    """Find all PARSED ingestion runs, run reconciliation matching, and update their status."""
    from backend.models.core import Tenant as _Tenant  # avoid circular at module level

    query = select(IngestionRun).where(IngestionRun.status == RunStatus.PARSED)
    if tenant_codes:
        query = query.join(_Tenant, IngestionRun.tenant_id == _Tenant.id).where(
            _Tenant.code.in_(tenant_codes)
        )
    runs = db.scalars(query).all()

    all_matches: list[ReconciliationMatch] = []
    for run in runs:
        bank_blob = db.get(BlobObject, run.bank_blob_id)
        bank_rows = (
            list(
                db.scalars(
                    select(BankStatement).where(
                        BankStatement.blob_object_id == bank_blob.id
                    )
                ).all()
            )
            if bank_blob
            else []
        )
        rem_blob = db.get(BlobObject, run.remittance_blob_id)
        rem_header = (
            db.scalar(
                select(RemittanceAdviceHeader).where(
                    RemittanceAdviceHeader.blob_object_id == rem_blob.id
                )
            )
            if rem_blob
            else None
        )
        rem_lines = list(rem_header.lines) if rem_header else []

        matches = _persist_matches(db, run, bank_rows, rem_lines)
        all_matches.extend(matches)

        run.status = RunStatus.MATCHED
        run.matched_line_count = len(matches)

        requires_review = any(
            m.status
            in {
                MatchStatus.PARTIAL_MATCH,
                MatchStatus.UNMATCHED,
                MatchStatus.MANUAL_REVIEW,
            }
            for m in matches
            if m.is_selected
        ) or any(
            (m.confidence_score or Decimal("0.0"))
            < Decimal(str(settings.auto_post_confidence_threshold))
            for m in matches
            if m.is_selected
        )
        run.review_required_count = len(
            [
                m
                for m in matches
                if m.is_selected
                and m.status
                in {
                    MatchStatus.PARTIAL_MATCH,
                    MatchStatus.UNMATCHED,
                    MatchStatus.MANUAL_REVIEW,
                }
            ]
        )
        if requires_review:
            run.status = RunStatus.REVIEW_REQUIRED
            run.review_reason_code = "LOW_CONFIDENCE_OR_PARTIAL"
        else:
            run.status = RunStatus.READY_TO_POST

        _generate_journal_entries(db, run, bank_rows, matches)
        db.flush()

    return all_matches


def ingest_run(db: Session, tenant_code: str, business_date) -> IngestionRun:
    client = BlobServiceClient.from_connection_string(
        settings.azurite_connection_string
    )
    tenant = _ensure_tenant(db, tenant_code)

    bank_prefix = build_blob_prefix(tenant_code, "bank-statement", business_date)
    rem_prefix = build_blob_prefix(tenant_code, "remittance", business_date)

    bank_blob_path, bank_payload = _get_blob(
        client, settings.azure_raw_container, bank_prefix, ".xlsx"
    )
    rem_blob_path, rem_payload = _get_blob(
        client, settings.azure_raw_container, rem_prefix, ".pdf"
    )

    bank_blob = _upsert_blob_object(
        db,
        tenant,
        SourceType.BANK_STATEMENT,
        business_date,
        bank_blob_path,
        bank_payload,
    )
    rem_blob = _upsert_blob_object(
        db, tenant, SourceType.REMITTANCE, business_date, rem_blob_path, rem_payload
    )

    run = _create_run_if_needed(db, tenant, business_date, bank_blob, rem_blob)
    if run.status in {
        RunStatus.POSTED,
        RunStatus.READY_TO_POST,
        RunStatus.REVIEW_REQUIRED,
    }:
        return run

    bank_rows = _persist_bank_data(db, bank_blob, bank_payload)
    rem_lines, extraction_reasons = _persist_remittance_data(db, rem_blob, rem_payload)
    bank_blob.is_parsed = True
    rem_blob.is_parsed = True
    run.status = RunStatus.PARSED
    run.parsed_line_count = len(bank_rows) + len(rem_lines)

    matches = _persist_matches(db, run, bank_rows, rem_lines)
    run.status = RunStatus.MATCHED
    run.matched_line_count = len(matches)

    requires_review = (
        bool(extraction_reasons)
        or any(
            m.status
            in {
                MatchStatus.PARTIAL_MATCH,
                MatchStatus.UNMATCHED,
                MatchStatus.MANUAL_REVIEW,
            }
            for m in matches
            if m.is_selected
        )
        or any(
            (m.confidence_score or Decimal("0.0"))
            < Decimal(str(settings.auto_post_confidence_threshold))
            for m in matches
            if m.is_selected
        )
    )

    run.review_required_count = len(
        [
            m
            for m in matches
            if m.is_selected
            and m.status
            in {
                MatchStatus.PARTIAL_MATCH,
                MatchStatus.UNMATCHED,
                MatchStatus.MANUAL_REVIEW,
            }
        ]
    )

    if requires_review:
        run.status = RunStatus.REVIEW_REQUIRED
        run.review_reason_code = (
            extraction_reasons[0] if extraction_reasons else "LOW_CONFIDENCE_OR_PARTIAL"
        )
    else:
        run.status = RunStatus.READY_TO_POST

    _generate_journal_entries(db, run, bank_rows, matches)
    db.flush()
    return run


def _actor(actor_id: str | None) -> str:
    return actor_id or "analyst.demo"


def _get_match(db: Session, match_id: UUID) -> ReconciliationMatch:
    match = db.get(ReconciliationMatch, match_id)
    if not match:
        raise ServiceError(f"Match {match_id} not found")
    return match


def approve_match(
    db: Session,
    match_id: UUID,
    actor_id: str | None,
    reason_code: str | None,
    comment: str | None,
) -> MatchActionResponse:
    match = _get_match(db, match_id)
    match.status = MatchStatus.APPROVED
    match.reviewed_by = _actor(actor_id)
    match.reviewed_at = datetime.utcnow()
    match.review_comment = comment

    db.flush()
    return MatchActionResponse(
        match_id=str(match.id),
        status=match.status.value,
        reviewed_by=match.reviewed_by,
        reviewed_at=match.reviewed_at,
    )


def reject_match(
    db: Session,
    match_id: UUID,
    actor_id: str | None,
    reason_code: str | None,
    comment: str | None,
) -> MatchActionResponse:
    match = _get_match(db, match_id)
    match.status = MatchStatus.REJECTED
    match.reviewed_by = _actor(actor_id)
    match.reviewed_at = datetime.utcnow()
    match.review_comment = comment

    db.flush()
    return MatchActionResponse(
        match_id=str(match.id),
        status=match.status.value,
        reviewed_by=match.reviewed_by,
        reviewed_at=match.reviewed_at,
    )


def manual_link(
    db: Session,
    run_id: UUID,
    bank_statement_id: UUID,
    remittance_advice_line_id: UUID | None,
    actor_id: str | None,
    reason_code: str | None,
    comment: str | None,
) -> MatchActionResponse:
    for old in db.scalars(
        select(ReconciliationMatch).where(
            ReconciliationMatch.run_id == run_id,
            ReconciliationMatch.bank_statement_id == bank_statement_id,
            ReconciliationMatch.is_selected.is_(True),
        )
    ):
        old.is_selected = False

    manual = ReconciliationMatch(
        run_id=run_id,
        bank_statement_id=bank_statement_id,
        remittance_advice_line_id=remittance_advice_line_id,
        status=MatchStatus.APPROVED,
        match_rule="manual_link",
        confidence_score=Decimal("1.0000"),
        amount_applied=None,
        variance_amount=Decimal("0.00"),
        source="MANUAL",
        is_selected=True,
        reviewed_by=_actor(actor_id),
        reviewed_at=datetime.utcnow(),
        review_comment=comment,
    )
    db.add(manual)
    db.flush()

    return MatchActionResponse(
        match_id=str(manual.id),
        status=manual.status.value,
        reviewed_by=manual.reviewed_by,
        reviewed_at=manual.reviewed_at,
    )


def post_journals(
    db: Session, run_id: UUID, actor_id: str | None
) -> list[JournalEntry]:
    run = db.get(IngestionRun, run_id)
    if not run:
        raise ServiceError(f"Run {run_id} not found")

    if run.status not in {RunStatus.READY_TO_POST, RunStatus.REVIEW_REQUIRED}:
        raise ServiceError(f"Run {run.id} is not ready for posting: {run.status.value}")

    selected = db.scalars(
        select(ReconciliationMatch).where(
            ReconciliationMatch.run_id == run.id,
            ReconciliationMatch.is_selected.is_(True),
        )
    ).all()

    postable = [
        m
        for m in selected
        if m.status
        in {MatchStatus.AUTO_MATCHED, MatchStatus.APPROVED, MatchStatus.PARTIAL_MATCH}
        and m.remittance_advice_line_id is not None
    ]
    blocking = [
        m
        for m in selected
        if m.status in {MatchStatus.REJECTED, MatchStatus.MANUAL_REVIEW}
    ]
    if blocking:
        raise ServiceError("Run has unresolved matches; cannot post journals")
    if not postable:
        raise ServiceError("Run has no postable remittance matches")

    posting_date = run.business_date
    primary_bank = db.get(BankStatement, postable[0].bank_statement_id)
    if primary_bank and primary_bank.booking_date:
        posting_date = primary_bank.booking_date

    existing_lines = db.scalars(
        select(JournalEntry).where(JournalEntry.run_id == run.id)
    ).all()
    if existing_lines:
        run.status = RunStatus.POSTED
        run.finished_at = datetime.utcnow()
        db.flush()
        return existing_lines

    line_no = 1
    created: list[JournalEntry] = []
    used_bank_ids: set[UUID] = set()
    for match in postable:
        bank_row = db.get(BankStatement, match.bank_statement_id)
        rem_line = (
            db.get(RemittanceAdviceLine, match.remittance_advice_line_id)
            if match.remittance_advice_line_id
            else None
        )
        if not bank_row or not rem_line or rem_line.paid_amount is None:
            continue
        used_bank_ids.add(bank_row.id)

        amount = abs(rem_line.paid_amount)
        entry = JournalEntry(
            run_id=run.id,
            line_number=line_no,
            company_code="1000",
            posting_date=posting_date,
            document_date=posting_date,
            document_type="SA",
            gl_account="100000",
            debit=None,
            credit=amount,
            currency=rem_line.currency or bank_row.currency,
            item_text=(
                f"{rem_line.invoice_number}/{rem_line.customer_reference}"
                if rem_line.invoice_number and rem_line.customer_reference
                else (
                    rem_line.invoice_number
                    or rem_line.customer_reference
                    or bank_row.customer_reference
                    or bank_row.bank_reference
                    or "auto-posted"
                )
            ),
            source_file_name=f"run-{run.id}.json",
            reconciliation_match_id=match.id,
            bank_statement_id=bank_row.id,
            remittance_advice_line_id=rem_line.id,
        )
        db.add(entry)
        created.append(entry)
        line_no += 1

    unmatched_bank_rows = db.scalars(
        select(BankStatement)
        .where(BankStatement.blob_object_id == run.bank_blob_id)
        .order_by(BankStatement.line_number.asc())
    ).all()
    for bank_row in unmatched_bank_rows:
        if bank_row.id in used_bank_ids:
            continue
        amount = abs(bank_row.amount)
        entry = JournalEntry(
            run_id=run.id,
            line_number=line_no,
            company_code="1000",
            posting_date=bank_row.booking_date or posting_date,
            document_date=bank_row.booking_date or posting_date,
            document_type="SA",
            gl_account="100000",
            debit=amount if bank_row.amount > 0 else None,
            credit=amount if bank_row.amount < 0 else None,
            currency=bank_row.currency,
            item_text=bank_row.customer_reference
            or bank_row.bank_reference
            or "unmatched-bank-line",
            source_file_name=f"run-{run.id}.json",
            bank_statement_id=bank_row.id,
        )
        db.add(entry)
        created.append(entry)
        line_no += 1

    run.status = RunStatus.POSTED
    run.finished_at = datetime.utcnow()
    db.flush()
    return created
