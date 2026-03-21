from __future__ import annotations

import logging
import os
import time
from collections import defaultdict
from datetime import UTC, date, datetime

from azure.core.exceptions import ResourceNotFoundError
from azure.storage.blob import BlobServiceClient
from sqlalchemy import select, text
from sqlalchemy.orm import selectinload

from backend.config import settings
from backend.db.session import SessionLocal
from backend.models.core import JobScheduleRule, JobScheduleRuleTenant, Tenant
from backend.models.enums import ScheduleFrequency
from backend.services.run_service import ServiceError, ingest_run

logger = logging.getLogger("job_runner")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logging.getLogger("azure").setLevel(logging.WARNING)


def _parse_iso_date(value: str | None) -> date | None:
    if not value:
        return None
    return date.fromisoformat(value)


def _discover_tenant_dates(tenant_code: str | None = None) -> list[tuple[str, date]]:
    client = BlobServiceClient.from_connection_string(
        settings.azurite_connection_string
    )
    container = client.get_container_client(settings.azure_raw_container)

    present: dict[tuple[str, date], set[str]] = defaultdict(set)
    try:
        for blob in container.list_blobs():
            parts = blob.name.split("/")
            if len(parts) < 6:
                continue
            tenant, source, yyyy, mm, dd = (
                parts[0],
                parts[1],
                parts[2],
                parts[3],
                parts[4],
            )
            if source not in {"bank-statement", "remittance"}:
                continue
            try:
                business_date = date(int(yyyy), int(mm), int(dd))
            except ValueError:
                continue
            present[(tenant, business_date)].add(source)
    except ResourceNotFoundError:
        logger.info(
            "Container %s does not exist yet; nothing to process",
            settings.azure_raw_container,
        )
        return []

    pairs: list[tuple[str, date]] = []
    for key, sources in present.items():
        if {"bank-statement", "remittance"}.issubset(sources):
            pairs.append(key)

    if tenant_code:
        pairs = [p for p in pairs if p[0] == tenant_code]

    pairs.sort(key=lambda item: (item[0], item[1]))
    return pairs


def _process(tenant_code: str, business_date: date) -> None:
    lock_key = f"job-runner:{tenant_code}:{business_date.isoformat()}"
    db = SessionLocal()
    started = datetime.now(tz=UTC)
    try:
        locked = db.execute(
            text("SELECT pg_try_advisory_xact_lock(hashtextextended(:k, 0))"),
            {"k": lock_key},
        ).scalar_one()
        if not locked:
            logger.info(
                "Skipping %s %s because lock is held by another runner",
                tenant_code,
                business_date,
            )
            return
        run = ingest_run(db, tenant_code, business_date)
        db.commit()
        logger.info(
            "Processed tenant=%s date=%s run_id=%s status=%s duration_sec=%.2f",
            tenant_code,
            business_date,
            run.id,
            run.status.value,
            (datetime.now(tz=UTC) - started).total_seconds(),
        )
    except ServiceError as exc:
        db.rollback()
        logger.warning(
            "Business error tenant=%s date=%s detail=%s",
            tenant_code,
            business_date,
            exc,
        )
    except Exception:
        db.rollback()
        logger.exception(
            "Unhandled runner error tenant=%s date=%s", tenant_code, business_date
        )
    finally:
        db.close()


def _should_run_rule(rule: JobScheduleRule, now: datetime) -> bool:
    """Check whether a scheduling rule should fire at the given UTC datetime."""
    if not rule.is_active:
        return False
    try:
        hour, minute = int(rule.run_time[:2]), int(rule.run_time[3:])
    except (ValueError, IndexError):
        return False

    if now.hour != hour or now.minute != minute:
        return False

    # Guard against double-firing within the same hour
    if rule.last_triggered_at is not None:
        last = rule.last_triggered_at
        if last.tzinfo is None:
            last = last.replace(tzinfo=UTC)
        if (now - last).total_seconds() < 3600:
            return False

    if rule.frequency == ScheduleFrequency.DAILY:
        return True
    if rule.frequency == ScheduleFrequency.WEEKLY:
        return rule.day_of_week is not None and now.weekday() == rule.day_of_week
    if rule.frequency == ScheduleFrequency.MONTHLY:
        return rule.day_of_month is not None and now.day == rule.day_of_month
    return False


def _check_and_run_rules(now: datetime) -> int:
    """Read active rules from DB, fire any that are due, return count of items processed."""
    db = SessionLocal()
    processed = 0
    try:
        rules = db.scalars(
            select(JobScheduleRule)
            .options(
                selectinload(JobScheduleRule.rule_tenants).selectinload(
                    JobScheduleRuleTenant.tenant
                )
            )
            .where(JobScheduleRule.is_active.is_(True))
        ).all()

        for rule in rules:
            if not _should_run_rule(rule, now):
                continue

            if rule.rule_type == "matching":
                logger.info("Matching rule %s fired – matching step reserved.", rule.id)
                rule.last_triggered_at = now
                db.commit()
                continue

            # PROCESSING rule – discover blobs for configured tenants (or all)
            tenant_codes = [rt.tenant.code for rt in rule.rule_tenants if rt.tenant]
            if tenant_codes:
                all_items: list[tuple[str, date]] = []
                for code in tenant_codes:
                    all_items.extend(_discover_tenant_dates(tenant_code=code))
            else:
                all_items = _discover_tenant_dates()

            for tenant_code, business_date in all_items:
                _process(tenant_code, business_date)
                processed += 1

            rule.last_triggered_at = now
            db.commit()
            logger.info(
                "Rule %s fired frequency=%s tenant_count=%s processed=%s",
                rule.id,
                rule.frequency.value,
                len(tenant_codes) or "all",
                processed,
            )
    except Exception:
        db.rollback()
        logger.exception("Error checking/running scheduled rules")
    finally:
        db.close()
    return processed


def run_for_rule(rule_id: str) -> tuple[int, list[dict]]:
    """Manually trigger a rule by ID (blocking). Returns (count, items) tuple."""
    return run_for_rule_with_progress(rule_id, None)


def run_for_rule_with_progress(rule_id: str, progress_cb) -> tuple[int, list[dict]]:
    """Manually trigger a rule by ID with optional progress callback.

    ``progress_cb`` is called with dict messages:
      {"type": "progress", "step": str, "percent": int}
      {"type": "done", "processed": int, "items": list}
      {"type": "error", "message": str}
    """
    import uuid as _uuid

    def _emit(msg: dict) -> None:
        if progress_cb:
            try:
                progress_cb(msg)
            except Exception:
                pass

    _emit({"type": "progress", "step": "Loading rule…", "percent": 5})
    db = SessionLocal()
    try:
        rule = db.scalar(
            select(JobScheduleRule)
            .options(
                selectinload(JobScheduleRule.rule_tenants).selectinload(
                    JobScheduleRuleTenant.tenant
                )
            )
            .where(JobScheduleRule.id == _uuid.UUID(str(rule_id)))
        )
        if not rule:
            _emit({"type": "error", "message": "Rule not found"})
            return 0, []

        tenant_codes = [rt.tenant.code for rt in rule.rule_tenants if rt.tenant]

        # ── MATCHING rule ─────────────────────────────────────────────────────
        if rule.rule_type == "matching":
            _emit(
                {
                    "type": "progress",
                    "step": "Finding parsed runs to match…",
                    "percent": 15,
                }
            )
            from backend.services.run_service import run_matching_for_parsed_runs

            db2 = SessionLocal()
            try:
                matches = run_matching_for_parsed_runs(
                    db2, tenant_codes if tenant_codes else None
                )
                db2.commit()
                n_matches = len(matches)
            finally:
                db2.close()

            rule.last_triggered_at = datetime.now(tz=UTC)
            db.commit()
            _emit({"type": "done", "processed": n_matches, "items": []})
            logger.info("Matching rule %s completed matches=%s", rule_id, n_matches)
            return n_matches, []

        # ── PROCESSING rule ───────────────────────────────────────────────────
        _emit(
            {
                "type": "progress",
                "step": "Discovering tenant/date pairs…",
                "percent": 10,
            }
        )
        if tenant_codes:
            all_items: list[tuple[str, date]] = []
            for code in tenant_codes:
                all_items.extend(_discover_tenant_dates(tenant_code=code))
        else:
            all_items = _discover_tenant_dates()

        if not all_items:
            _emit({"type": "done", "processed": 0, "items": []})
            rule.last_triggered_at = datetime.now(tz=UTC)
            db.commit()
            return 0, []

        from backend.services.run_service import (
            ServiceError,
            ingest_run_processing_only,
        )

        total = len(all_items)
        processed_items: list[dict] = []
        for idx, (tenant_code, business_date) in enumerate(all_items):
            percent = 15 + int((idx / total) * 80)
            _emit(
                {
                    "type": "progress",
                    "step": f"Processing {tenant_code} / {business_date}…",
                    "percent": percent,
                }
            )
            lock_key = f"job-runner:{tenant_code}:{business_date.isoformat()}"
            db2 = SessionLocal()
            started = datetime.now(tz=UTC)
            try:
                locked = db2.execute(
                    text("SELECT pg_try_advisory_xact_lock(hashtextextended(:k, 0))"),
                    {"k": lock_key},
                ).scalar_one()
                if not locked:
                    logger.info(
                        "Skipping %s %s (lock held)", tenant_code, business_date
                    )
                    continue
                ingest_run_processing_only(db2, tenant_code, business_date)
                db2.commit()
                processed_items.append(
                    {"tenant": tenant_code, "date": str(business_date)}
                )
                logger.info(
                    "Processed tenant=%s date=%s duration_sec=%.2f",
                    tenant_code,
                    business_date,
                    (datetime.now(tz=UTC) - started).total_seconds(),
                )
            except ServiceError as exc:
                db2.rollback()
                logger.warning(
                    "Business error tenant=%s date=%s detail=%s",
                    tenant_code,
                    business_date,
                    exc,
                )
            except Exception:
                db2.rollback()
                logger.exception(
                    "Unhandled error tenant=%s date=%s", tenant_code, business_date
                )
            finally:
                db2.close()

        rule.last_triggered_at = datetime.now(tz=UTC)
        db.commit()
        _emit(
            {
                "type": "done",
                "processed": len(processed_items),
                "items": processed_items,
            }
        )
        return len(processed_items), processed_items
    except Exception as exc:
        db.rollback()
        logger.exception("Error in run_for_rule_with_progress rule_id=%s", rule_id)
        _emit({"type": "error", "message": str(exc)})
        return 0, []
    finally:
        db.close()


def _resolve_work_items() -> list[tuple[str, date]]:
    tenant_filter = os.getenv("RUNNER_TENANT_CODE")
    date_filter = _parse_iso_date(os.getenv("RUNNER_BUSINESS_DATE"))

    discovered = _discover_tenant_dates()

    if tenant_filter:
        discovered = [item for item in discovered if item[0] == tenant_filter]
    if date_filter:
        discovered = [item for item in discovered if item[1] == date_filter]

    if not discovered and tenant_filter and date_filter:
        discovered = [(tenant_filter, date_filter)]

    return discovered


def run_once() -> int:
    items = _resolve_work_items()
    if not items:
        logger.info("No runnable tenant/date pairs discovered")
        return 0

    for tenant_code, business_date in items:
        _process(tenant_code, business_date)
    return len(items)


def run_scheduled() -> None:
    interval_seconds = int(os.getenv("RUNNER_INTERVAL_SECONDS", "60"))
    logger.info("Starting scheduled runner interval_seconds=%s", interval_seconds)
    while True:
        now = datetime.now(tz=UTC)
        rule_processed = _check_and_run_rules(now)
        logger.info(
            "Runner cycle complete rule_processed=%s sleeping=%ss",
            rule_processed,
            interval_seconds,
        )
        time.sleep(interval_seconds)


def main() -> None:
    mode = os.getenv("RUNNER_MODE", "scheduled").strip().lower()
    if mode == "once":
        processed = run_once()
        logger.info("Run-once completed processed=%s", processed)
        return
    if mode == "scheduled":
        run_scheduled()
        return
    raise ValueError(f"Unsupported RUNNER_MODE={mode}. Use once or scheduled.")


if __name__ == "__main__":
    main()
