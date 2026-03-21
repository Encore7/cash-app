from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from backend.db.deps import get_db
from backend.models.bank import BankStatement
from backend.models.core import BlobObject, IngestionRun, Tenant
from backend.models.enums import MatchStatus
from backend.models.journal import JournalEntry
from backend.models.reconciliation import ReconciliationMatch
from backend.models.remittance import RemittanceAdviceHeader, RemittanceAdviceLine

router = APIRouter(prefix="/analytics", tags=["analytics"])


# ---------------------------------------------------------------------------
# Summary endpoint (pie chart data + per-tenant breakdown)
# ---------------------------------------------------------------------------


@router.get("/summary")
def get_summary(db: Session = Depends(get_db)) -> dict[str, Any]:
    # Count by match status
    rows = db.execute(
        select(ReconciliationMatch.status, func.count(ReconciliationMatch.id)).group_by(
            ReconciliationMatch.status
        )
    ).all()

    status_counts: dict[str, int] = {r[0]: r[1] for r in rows}

    matched_statuses = {
        MatchStatus.AUTO_MATCHED,
        MatchStatus.APPROVED,
        MatchStatus.CLOSED,
    }
    unmatched_statuses = {MatchStatus.UNMATCHED}
    review_statuses = {
        MatchStatus.MANUAL_REVIEW,
        MatchStatus.PARTIAL_MATCH,
        MatchStatus.REJECTED,
    }

    matched = sum(status_counts.get(s, 0) for s in matched_statuses)
    unmatched = sum(status_counts.get(s, 0) for s in unmatched_statuses)
    manual_review = sum(status_counts.get(s, 0) for s in review_statuses)

    # Per-tenant breakdown via blob_objects → ingestion_runs → reconciliation_matches
    tenants = db.scalars(select(Tenant).order_by(Tenant.name)).all()
    tenant_details = []
    for tenant in tenants:
        # get run ids for tenant
        run_ids = db.scalars(
            select(IngestionRun.id).where(IngestionRun.tenant_id == tenant.id)
        ).all()
        t_matched = 0
        t_unmatched = 0
        t_review = 0
        if run_ids:
            t_rows = db.execute(
                select(ReconciliationMatch.status, func.count(ReconciliationMatch.id))
                .where(ReconciliationMatch.run_id.in_(run_ids))
                .group_by(ReconciliationMatch.status)
            ).all()
            t_counts: dict[str, int] = {r[0]: r[1] for r in t_rows}
            t_matched = sum(t_counts.get(s, 0) for s in matched_statuses)
            t_unmatched = sum(t_counts.get(s, 0) for s in unmatched_statuses)
            t_review = sum(t_counts.get(s, 0) for s in review_statuses)

        tenant_details.append(
            {
                "id": str(tenant.id),
                "code": tenant.code,
                "name": tenant.name,
                "is_active": tenant.is_active,
                "matched": t_matched,
                "unmatched": t_unmatched,
                "manual_review": t_review,
                "total": t_matched + t_unmatched + t_review,
            }
        )

    return {
        "matched": matched,
        "unmatched": unmatched,
        "manual_review": manual_review,
        "total": matched + unmatched + manual_review,
        "tenants": tenant_details,
    }


# ---------------------------------------------------------------------------
# Reconciliation matches list (optional filter by status)
# ---------------------------------------------------------------------------


@router.get("/matches")
def get_matches(
    status: str | None = None,
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    q = (
        select(ReconciliationMatch)
        .options(
            selectinload(ReconciliationMatch.bank_statement),
            selectinload(ReconciliationMatch.remittance_advice_line),
        )
        .order_by(ReconciliationMatch.created_at.desc())
    )
    if status:
        q = q.where(ReconciliationMatch.status == status)

    records = db.scalars(q).all()
    result = []
    for m in records:
        bs = m.bank_statement
        ral = m.remittance_advice_line
        result.append(
            {
                "id": str(m.id),
                "run_id": str(m.run_id),
                "status": m.status,
                "confidence_score": float(m.confidence_score),
                "match_rule": m.match_rule,
                "amount_applied": (
                    float(m.amount_applied) if m.amount_applied is not None else None
                ),
                "variance_amount": (
                    float(m.variance_amount) if m.variance_amount is not None else None
                ),
                "notes": m.notes,
                "source": m.source,
                "is_selected": m.is_selected,
                "created_at": m.created_at.isoformat() if m.created_at else None,
                "reviewed_by": m.reviewed_by,
                "reviewed_at": m.reviewed_at.isoformat() if m.reviewed_at else None,
                "review_comment": m.review_comment,
                # bank side
                "bank_booking_date": bs.booking_date.isoformat() if bs else None,
                "bank_amount": float(bs.amount) if bs else None,
                "bank_currency": bs.currency if bs else None,
                "bank_counterparty": bs.counterparty_name if bs else None,
                "bank_reference": bs.bank_reference if bs else None,
                "bank_payment_purpose": bs.payment_purpose if bs else None,
                # remittance side
                "remittance_invoice_number": ral.invoice_number if ral else None,
                "remittance_paid_amount": (
                    float(ral.paid_amount)
                    if ral and ral.paid_amount is not None
                    else None
                ),
                "remittance_currency": ral.currency if ral else None,
                "remittance_customer_reference": (
                    ral.customer_reference if ral else None
                ),
            }
        )
    return result


# ---------------------------------------------------------------------------
# Bank statements list
# ---------------------------------------------------------------------------


@router.get("/bank-statements")
def get_bank_statements(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    records = db.scalars(
        select(BankStatement).order_by(BankStatement.booking_date.desc())
    ).all()
    return [
        {
            "id": str(r.id),
            "blob_object_id": str(r.blob_object_id),
            "line_number": r.line_number,
            "booking_date": r.booking_date.isoformat(),
            "value_date": r.value_date.isoformat() if r.value_date else None,
            "amount": float(r.amount),
            "currency": r.currency,
            "counterparty_name": r.counterparty_name,
            "payment_purpose": r.payment_purpose,
            "bank_reference": r.bank_reference,
            "customer_reference": r.customer_reference,
        }
        for r in records
    ]


# ---------------------------------------------------------------------------
# Remittance advice headers + their lines
# ---------------------------------------------------------------------------


@router.get("/remittance-headers")
def get_remittance_headers(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    headers = db.scalars(
        select(RemittanceAdviceHeader)
        .options(selectinload(RemittanceAdviceHeader.lines))
        .order_by(RemittanceAdviceHeader.advice_date.desc())
    ).all()
    result = []
    for h in headers:
        result.append(
            {
                "id": str(h.id),
                "blob_object_id": str(h.blob_object_id),
                "advice_number": h.advice_number,
                "advice_date": h.advice_date.isoformat() if h.advice_date else None,
                "payer_name": h.payer_name,
                "document_currency": h.document_currency,
                "total_paid_amount": (
                    float(h.total_paid_amount)
                    if h.total_paid_amount is not None
                    else None
                ),
                "lines": [
                    {
                        "id": str(ln.id),
                        "line_number": ln.line_number,
                        "invoice_number": ln.invoice_number,
                        "invoice_date": (
                            ln.invoice_date.isoformat() if ln.invoice_date else None
                        ),
                        "paid_amount": (
                            float(ln.paid_amount)
                            if ln.paid_amount is not None
                            else None
                        ),
                        "currency": ln.currency,
                        "customer_reference": ln.customer_reference,
                        "raw_line_text": ln.raw_line_text,
                    }
                    for ln in sorted(h.lines, key=lambda x: x.line_number)
                ],
            }
        )
    return result


# ---------------------------------------------------------------------------
# Match / Unmatch actions (preparer decision)
# ---------------------------------------------------------------------------


@router.post("/matches/{match_id}/mark-matched")
def mark_matched(
    match_id: UUID,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    match = db.get(ReconciliationMatch, match_id)
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    match.status = MatchStatus.APPROVED
    match.reviewed_at = datetime.utcnow()
    db.commit()
    return {"id": str(match.id), "status": match.status}


@router.post("/matches/{match_id}/mark-unmatched")
def mark_unmatched(
    match_id: UUID,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    match = db.get(ReconciliationMatch, match_id)
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    match.status = MatchStatus.UNMATCHED
    match.reviewed_at = datetime.utcnow()
    db.commit()
    return {"id": str(match.id), "status": match.status}


# ---------------------------------------------------------------------------
# Journal entries
# ---------------------------------------------------------------------------


@router.get("/journal-entries")
def get_journal_entries(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    records = db.scalars(
        select(JournalEntry).order_by(
            JournalEntry.posting_date.desc(), JournalEntry.line_number
        )
    ).all()
    return [
        {
            "id": str(r.id),
            "run_id": str(r.run_id),
            "line_number": r.line_number,
            "company_code": r.company_code,
            "posting_date": r.posting_date.isoformat(),
            "document_date": r.document_date.isoformat(),
            "document_type": r.document_type,
            "gl_account": r.gl_account,
            "debit": float(r.debit) if r.debit is not None else None,
            "credit": float(r.credit) if r.credit is not None else None,
            "currency": r.currency,
            "item_text": r.item_text,
            "source_file_name": r.source_file_name,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "reconciliation_match_id": (
                str(r.reconciliation_match_id) if r.reconciliation_match_id else None
            ),
            "bank_statement_id": (
                str(r.bank_statement_id) if r.bank_statement_id else None
            ),
            "remittance_advice_line_id": (
                str(r.remittance_advice_line_id)
                if r.remittance_advice_line_id
                else None
            ),
        }
        for r in records
    ]
