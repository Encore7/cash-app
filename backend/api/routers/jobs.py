from __future__ import annotations

import queue as _queue_module
import threading
import uuid
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.db.deps import get_db
from backend.models.core import JobScheduleRule, JobScheduleRuleTenant, Tenant
from backend.models.enums import ScheduleFrequency
from backend.schemas.api import (
    JobRuleCreate,
    JobRuleResponse,
    TenantInRule,
    TenantResponse,
)

# Active job progress queues — keyed by rule_id string
_active_jobs: dict[str, _queue_module.SimpleQueue] = {}
# Final message cache so reconnecting WebSocket clients can get the result
_job_results: dict[str, dict] = {}

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _rule_to_response(rule: JobScheduleRule) -> JobRuleResponse:
    tenants = [
        TenantInRule(
            id=str(rt.tenant.id),
            code=rt.tenant.code,
            name=rt.tenant.name,
        )
        for rt in rule.rule_tenants
        if rt.tenant is not None
    ]
    return JobRuleResponse(
        id=str(rule.id),
        rule_type=rule.rule_type,
        tenants=tenants,
        frequency=rule.frequency.value,
        day_of_week=rule.day_of_week,
        day_of_month=rule.day_of_month,
        run_time=rule.run_time,
        is_active=rule.is_active,
        created_at=rule.created_at,
        last_triggered_at=rule.last_triggered_at,
    )


def _load_rule(db: Session, rule_id: UUID) -> JobScheduleRule:
    rule = db.scalar(
        select(JobScheduleRule)
        .options(
            selectinload(JobScheduleRule.rule_tenants).selectinload(
                JobScheduleRuleTenant.tenant
            )
        )
        .where(JobScheduleRule.id == rule_id)
    )
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    return rule


def _set_rule_tenants(
    db: Session, rule: JobScheduleRule, tenant_ids: list[str]
) -> None:
    for rt in list(rule.rule_tenants):
        db.delete(rt)
    db.flush()
    rule.rule_tenants = []
    for tid_str in tenant_ids:
        try:
            tid = UUID(tid_str)
        except ValueError:
            continue
        if db.get(Tenant, tid):
            db.add(JobScheduleRuleTenant(rule_id=rule.id, tenant_id=tid))
    db.flush()


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
        select(JobScheduleRule)
        .options(
            selectinload(JobScheduleRule.rule_tenants).selectinload(
                JobScheduleRuleTenant.tenant
            )
        )
        .order_by(JobScheduleRule.created_at.desc())
    ).all()
    return [_rule_to_response(r) for r in rules]


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
        rule_type=payload.rule_type,
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
    db.flush()

    for tid_str in payload.tenant_ids:
        try:
            tid = UUID(tid_str)
        except ValueError:
            continue
        if db.get(Tenant, tid):
            db.add(JobScheduleRuleTenant(rule_id=rule.id, tenant_id=tid))

    db.commit()
    rule = _load_rule(db, rule.id)
    return _rule_to_response(rule)


@router.patch("/rules/{rule_id}", response_model=JobRuleResponse)
def update_rule(
    rule_id: UUID, payload: JobRuleCreate, db: Session = Depends(get_db)
) -> JobRuleResponse:
    rule = _load_rule(db, rule_id)
    try:
        frequency = ScheduleFrequency(payload.frequency)
    except ValueError:
        raise HTTPException(
            status_code=422, detail=f"Invalid frequency: {payload.frequency}"
        )

    rule.rule_type = payload.rule_type
    rule.frequency = frequency
    rule.day_of_week = (
        payload.day_of_week if frequency == ScheduleFrequency.WEEKLY else None
    )
    rule.day_of_month = (
        payload.day_of_month if frequency == ScheduleFrequency.MONTHLY else None
    )
    rule.run_time = payload.run_time
    rule.is_active = payload.is_active

    _set_rule_tenants(db, rule, payload.tenant_ids)
    db.commit()
    return _rule_to_response(_load_rule(db, rule_id))


@router.delete("/rules/{rule_id}", status_code=204)
def delete_rule(rule_id: UUID, db: Session = Depends(get_db)) -> None:
    rule = db.get(JobScheduleRule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    db.delete(rule)
    db.commit()


@router.post("/rules/{rule_id}/trigger")
def trigger_rule(rule_id: UUID, db: Session = Depends(get_db)) -> dict:
    if not db.get(JobScheduleRule, rule_id):
        raise HTTPException(status_code=404, detail="Rule not found")

    str_id = str(rule_id)
    q: _queue_module.SimpleQueue = _queue_module.SimpleQueue()
    _active_jobs[str_id] = q
    _job_results.pop(str_id, None)

    from backend.jobs.runner import run_for_rule_with_progress

    def _progress_cb(msg: dict) -> None:
        if msg.get("type") in ("done", "error"):
            _job_results[str_id] = msg
        q.put(msg)

    def _worker() -> None:
        try:
            run_for_rule_with_progress(str_id, _progress_cb)
        except Exception as exc:
            err_msg = {"type": "error", "message": str(exc)}
            _job_results[str_id] = err_msg
            q.put(err_msg)
        finally:
            # Keep queue alive for 60 s so a late WS connect can still drain it
            import time

            time.sleep(60)
            _active_jobs.pop(str_id, None)
            _job_results.pop(str_id, None)

    threading.Thread(target=_worker, daemon=True).start()
    return {"status": "started", "rule_id": str_id}


@router.websocket("/ws/{rule_id}")
async def job_progress_ws(websocket: WebSocket, rule_id: UUID) -> None:
    import asyncio

    await websocket.accept()
    str_id = str(rule_id)

    # Wait up to 5 s for the queue or a cached result to be available
    for _ in range(25):
        if str_id in _active_jobs or str_id in _job_results:
            break
        await asyncio.sleep(0.2)

    # If the job already finished, send the cached final result immediately
    if str_id in _job_results:
        await websocket.send_json(_job_results[str_id])
        await websocket.close()
        return

    q = _active_jobs.get(str_id)
    if q is None:
        await websocket.send_json(
            {"type": "error", "message": "No active job for this rule"}
        )
        await websocket.close()
        return

    try:
        while True:
            # Guard: if another WS handler already consumed the done/error message
            # from the queue, retrieve the cached result so this client doesn't hang.
            if str_id in _job_results:
                await websocket.send_json(_job_results[str_id])
                break
            try:
                msg = q.get_nowait()
                await websocket.send_json(msg)
                if msg.get("type") in ("done", "error"):
                    break
            except _queue_module.Empty:
                await asyncio.sleep(0.2)
    except WebSocketDisconnect:
        pass
