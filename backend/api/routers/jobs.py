from __future__ import annotations

import uuid
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.db.deps import get_db
from backend.models.core import JobScheduleRule, Tenant
from backend.models.enums import ScheduleFrequency
from backend.schemas.api import JobRuleCreate, JobRuleResponse, TenantResponse

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _rule_to_response(db: Session, rule: JobScheduleRule) -> JobRuleResponse:
    tenant_code: str | None = None
    tenant_name: str | None = None
    if rule.tenant_id:
        tenant = db.get(Tenant, rule.tenant_id)
        if tenant:
            tenant_code = tenant.code
            tenant_name = tenant.name
    return JobRuleResponse(
        id=str(rule.id),
        tenant_id=str(rule.tenant_id) if rule.tenant_id else None,
        tenant_code=tenant_code,
        tenant_name=tenant_name,
        frequency=rule.frequency.value,
        day_of_week=rule.day_of_week,
        day_of_month=rule.day_of_month,
        run_time=rule.run_time,
        is_active=rule.is_active,
        created_at=rule.created_at,
        last_triggered_at=rule.last_triggered_at,
    )


@router.get("/tenants", response_model=list[TenantResponse])
def list_tenants(db: Session = Depends(get_db)) -> list[TenantResponse]:
    tenants = db.scalars(select(Tenant).order_by(Tenant.name)).all()
    return [
        TenantResponse(id=str(t.id), code=t.code, name=t.name, is_active=t.is_active)
        for t in tenants
    ]


@router.get("/rules", response_model=list[JobRuleResponse])
def list_rules(db: Session = Depends(get_db)) -> list[JobRuleResponse]:
    rules = db.scalars(
        select(JobScheduleRule).order_by(JobScheduleRule.created_at.desc())
    ).all()
    return [_rule_to_response(db, r) for r in rules]


@router.post("/rules", response_model=JobRuleResponse, status_code=201)
def create_rule(
    payload: JobRuleCreate, db: Session = Depends(get_db)
) -> JobRuleResponse:
    try:
        frequency = ScheduleFrequency(payload.frequency)
    except ValueError:
        raise HTTPException(
            status_code=422, detail=f"Invalid frequency: {payload.frequency}"
        )

    rule = JobScheduleRule(
        id=uuid.uuid4(),
        tenant_id=payload.tenant_id,
        frequency=frequency,
        day_of_week=(
            payload.day_of_week if frequency == ScheduleFrequency.WEEKLY else None
        ),
        day_of_month=(
            payload.day_of_month if frequency == ScheduleFrequency.MONTHLY else None
        ),
        run_time=payload.run_time,
        is_active=payload.is_active,
        created_at=datetime.utcnow(),
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return _rule_to_response(db, rule)


@router.patch("/rules/{rule_id}", response_model=JobRuleResponse)
def update_rule(
    rule_id: UUID, payload: JobRuleCreate, db: Session = Depends(get_db)
) -> JobRuleResponse:
    rule = db.get(JobScheduleRule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    try:
        frequency = ScheduleFrequency(payload.frequency)
    except ValueError:
        raise HTTPException(
            status_code=422, detail=f"Invalid frequency: {payload.frequency}"
        )

    rule.tenant_id = payload.tenant_id
    rule.frequency = frequency
    rule.day_of_week = (
        payload.day_of_week if frequency == ScheduleFrequency.WEEKLY else None
    )
    rule.day_of_month = (
        payload.day_of_month if frequency == ScheduleFrequency.MONTHLY else None
    )
    rule.run_time = payload.run_time
    rule.is_active = payload.is_active
    db.commit()
    db.refresh(rule)
    return _rule_to_response(db, rule)


@router.delete("/rules/{rule_id}", status_code=204)
def delete_rule(rule_id: UUID, db: Session = Depends(get_db)) -> None:
    rule = db.get(JobScheduleRule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    db.delete(rule)
    db.commit()


@router.post("/rules/{rule_id}/trigger")
def trigger_rule(rule_id: UUID, db: Session = Depends(get_db)) -> dict:
    rule = db.get(JobScheduleRule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    from backend.jobs.runner import run_for_rule

    processed, items = run_for_rule(str(rule_id))

    # Refresh the rule to reflect last_triggered_at updated by run_for_rule
    db.refresh(rule)
    return {"processed": processed, "items": items}
