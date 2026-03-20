from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.db.deps import get_db
from backend.models.bank import BankStatementLine
from backend.models.core import IngestionRun, Tenant
from backend.models.journal import JournalEntryHeader, JournalEntryLine
from backend.models.reconciliation import ReconciliationMatch
from backend.models.remittance import RemittanceAdviceLine
from backend.schemas.api import IngestRunRequest, JournalLineView, JournalPreviewResponse, RunItemsResponse, RunResponse
from backend.services.run_service import ServiceError, ingest_run, post_journals

router = APIRouter(prefix='/runs', tags=['runs'])


def _run_to_response(db: Session, run: IngestionRun) -> RunResponse:
    tenant = db.get(Tenant, run.tenant_id)
    return RunResponse(
        run_id=str(run.id),
        tenant_code=tenant.code if tenant else 'unknown',
        business_date=run.business_date,
        status=run.status.value,
        parsed_line_count=run.parsed_line_count,
        matched_line_count=run.matched_line_count,
        review_required_count=run.review_required_count,
        review_reason_code=run.review_reason_code,
        started_at=run.started_at,
        finished_at=run.finished_at,
    )


@router.post('/ingest', response_model=RunResponse)
def trigger_ingest(payload: IngestRunRequest, db: Session = Depends(get_db)) -> RunResponse:
    try:
        run = ingest_run(db, payload.tenant_code, payload.business_date)
        db.commit()
        db.refresh(run)
        return _run_to_response(db, run)
    except ServiceError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get('/{run_id}', response_model=RunResponse)
def get_run(run_id: UUID, db: Session = Depends(get_db)) -> RunResponse:
    run = db.get(IngestionRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail='Run not found')
    return _run_to_response(db, run)


@router.get('/{run_id}/items', response_model=RunItemsResponse)
def get_run_items(run_id: UUID, db: Session = Depends(get_db)) -> RunItemsResponse:
    run = db.get(IngestionRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail='Run not found')

    matches = db.scalars(select(ReconciliationMatch).where(ReconciliationMatch.run_id == run.id)).all()
    bank_line_count = len(db.scalars(select(BankStatementLine)).all())
    remittance_line_count = len(db.scalars(select(RemittanceAdviceLine)).all())

    return RunItemsResponse(
        run_id=str(run.id),
        bank_line_count=bank_line_count,
        remittance_line_count=remittance_line_count,
        matches=[
            {
                'match_id': str(m.id),
                'status': m.status.value,
                'match_rule': m.match_rule,
                'confidence_score': m.confidence_score,
                'amount_applied': m.amount_applied,
                'variance_amount': m.variance_amount,
                'source': m.source,
                'reviewed_by': m.reviewed_by,
                'reviewed_at': m.reviewed_at,
                'review_comment': m.review_comment,
                'bank_line_id': str(m.bank_statement_line_id),
                'remittance_line_id': str(m.remittance_advice_line_id) if m.remittance_advice_line_id else None,
            }
            for m in matches
        ],
    )


@router.post('/{run_id}/post-journals', response_model=JournalPreviewResponse)
def post_run_journals(
    run_id: UUID,
    x_actor_id: str | None = Header(default=None, alias='X-Actor-Id'),
    db: Session = Depends(get_db),
) -> JournalPreviewResponse:
    try:
        header = post_journals(db, run_id, x_actor_id)
        db.commit()
        lines = db.scalars(select(JournalEntryLine).where(JournalEntryLine.journal_header_id == header.id)).all()
        run = db.get(IngestionRun, run_id)
        return JournalPreviewResponse(
            run_id=str(run_id),
            status=run.status.value if run else 'POSTED',
            journal_headers=1,
            journal_lines=[
                JournalLineView(
                    id=str(line.id),
                    line_number=line.line_number,
                    gl_account=line.gl_account,
                    debit=line.debit,
                    credit=line.credit,
                    currency=line.currency,
                    item_text=line.item_text,
                    reconciliation_match_id=(
                        str(line.reconciliation_match_id) if line.reconciliation_match_id else None
                    ),
                )
                for line in lines
            ],
        )
    except ServiceError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get('/{run_id}/journals', response_model=JournalPreviewResponse)
def get_run_journals(run_id: UUID, db: Session = Depends(get_db)) -> JournalPreviewResponse:
    run = db.get(IngestionRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail='Run not found')
    headers = db.scalars(select(JournalEntryHeader).where(JournalEntryHeader.run_id == run.id)).all()
    lines: list[JournalLineView] = []
    for header in headers:
        h_lines = db.scalars(select(JournalEntryLine).where(JournalEntryLine.journal_header_id == header.id)).all()
        for line in h_lines:
            lines.append(
                JournalLineView(
                    id=str(line.id),
                    line_number=line.line_number,
                    gl_account=line.gl_account,
                    debit=line.debit,
                    credit=line.credit,
                    currency=line.currency,
                    item_text=line.item_text,
                    reconciliation_match_id=str(line.reconciliation_match_id)
                    if line.reconciliation_match_id
                    else None,
                )
            )
    return JournalPreviewResponse(
        run_id=str(run.id),
        status=run.status.value,
        journal_headers=len(headers),
        journal_lines=lines,
    )
