from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from backend.db.deps import get_db
from backend.schemas.api import ManualLinkRequest, MatchActionResponse, MatchDecisionRequest
from backend.services.run_service import ServiceError, approve_match, manual_link, reject_match

router = APIRouter(prefix='/matches', tags=['matches'])


@router.post('/{match_id}/approve', response_model=MatchActionResponse)
def approve(
    match_id: UUID,
    payload: MatchDecisionRequest,
    x_actor_id: str | None = Header(default=None, alias='X-Actor-Id'),
    db: Session = Depends(get_db),
) -> MatchActionResponse:
    try:
        resp = approve_match(db, match_id, x_actor_id, payload.reason_code, payload.comment)
        db.commit()
        return resp
    except ServiceError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post('/{match_id}/reject', response_model=MatchActionResponse)
def reject(
    match_id: UUID,
    payload: MatchDecisionRequest,
    x_actor_id: str | None = Header(default=None, alias='X-Actor-Id'),
    db: Session = Depends(get_db),
) -> MatchActionResponse:
    try:
        resp = reject_match(db, match_id, x_actor_id, payload.reason_code, payload.comment)
        db.commit()
        return resp
    except ServiceError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post('/manual-link', response_model=MatchActionResponse)
def create_manual_link(
    payload: ManualLinkRequest,
    run_id: UUID,
    x_actor_id: str | None = Header(default=None, alias='X-Actor-Id'),
    db: Session = Depends(get_db),
) -> MatchActionResponse:
    try:
        resp = manual_link(
            db,
            run_id,
            UUID(payload.bank_statement_id),
            UUID(payload.remittance_advice_line_id) if payload.remittance_advice_line_id else None,
            x_actor_id,
            payload.reason_code,
            payload.comment,
        )
        db.commit()
        return resp
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail='Invalid UUID in payload') from exc
    except ServiceError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
