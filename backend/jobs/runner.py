from __future__ import annotations

import logging
import os
import time
from collections import defaultdict
from datetime import UTC, date, datetime

from azure.core.exceptions import ResourceNotFoundError
from azure.storage.blob import BlobServiceClient
from sqlalchemy import text

from backend.config import settings
from backend.db.session import SessionLocal
from backend.services.run_service import ServiceError, ingest_run

logger = logging.getLogger('job_runner')
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s %(message)s',
)
logging.getLogger('azure').setLevel(logging.WARNING)


def _parse_iso_date(value: str | None) -> date | None:
    if not value:
        return None
    return date.fromisoformat(value)


def _discover_tenant_dates() -> list[tuple[str, date]]:
    client = BlobServiceClient.from_connection_string(settings.azurite_connection_string)
    container = client.get_container_client(settings.azure_raw_container)

    present: dict[tuple[str, date], set[str]] = defaultdict(set)
    try:
        for blob in container.list_blobs():
            parts = blob.name.split('/')
            if len(parts) < 6:
                continue
            tenant, source, yyyy, mm, dd = parts[0], parts[1], parts[2], parts[3], parts[4]
            if source not in {'bank-statement', 'remittance'}:
                continue
            try:
                business_date = date(int(yyyy), int(mm), int(dd))
            except ValueError:
                continue
            present[(tenant, business_date)].add(source)
    except ResourceNotFoundError:
        logger.info('Container %s does not exist yet; nothing to process', settings.azure_raw_container)
        return []


    pairs: list[tuple[str, date]] = []
    for key, sources in present.items():
        if {'bank-statement', 'remittance'}.issubset(sources):
            pairs.append(key)

    pairs.sort(key=lambda item: (item[0], item[1]))
    return pairs


def _acquire_lock(lock_key: str) -> bool:
    db = SessionLocal()
    try:
        # Use pg advisory lock with stable hash of key to avoid duplicate workers processing same slot.
        result = db.execute(
            text('SELECT pg_try_advisory_lock(hashtextextended(:k, 0))'),
            {'k': lock_key},
        ).scalar_one()
        return bool(result)
    finally:
        db.close()


def _release_lock(lock_key: str) -> None:
    db = SessionLocal()
    try:
        db.execute(text('SELECT pg_advisory_unlock(hashtextextended(:k, 0))'), {'k': lock_key})
        db.commit()
    finally:
        db.close()


def _process(tenant_code: str, business_date: date) -> None:
    lock_key = f'job-runner:{tenant_code}:{business_date.isoformat()}'
    if not _acquire_lock(lock_key):
        logger.info('Skipping %s %s because lock is held by another runner', tenant_code, business_date)
        return

    db = SessionLocal()
    started = datetime.now(tz=UTC)
    try:
        run = ingest_run(db, tenant_code, business_date)
        db.commit()
        logger.info(
            'Processed tenant=%s date=%s run_id=%s status=%s duration_sec=%.2f',
            tenant_code,
            business_date,
            run.id,
            run.status.value,
            (datetime.now(tz=UTC) - started).total_seconds(),
        )
    except ServiceError as exc:
        db.rollback()
        logger.warning('Business error tenant=%s date=%s detail=%s', tenant_code, business_date, exc)
    except Exception:
        db.rollback()
        logger.exception('Unhandled runner error tenant=%s date=%s', tenant_code, business_date)
    finally:
        db.close()
        _release_lock(lock_key)


def _resolve_work_items() -> list[tuple[str, date]]:
    tenant_filter = os.getenv('RUNNER_TENANT_CODE')
    date_filter = _parse_iso_date(os.getenv('RUNNER_BUSINESS_DATE'))

    discovered = _discover_tenant_dates()

    if tenant_filter:
        discovered = [item for item in discovered if item[0] == tenant_filter]
    if date_filter:
        discovered = [item for item in discovered if item[1] == date_filter]

    # Fallback useful for manual command mode if exact blob discovery is not desired.
    if not discovered and tenant_filter and date_filter:
        discovered = [(tenant_filter, date_filter)]

    return discovered


def run_once() -> int:
    items = _resolve_work_items()
    if not items:
        logger.info('No runnable tenant/date pairs discovered')
        return 0

    for tenant_code, business_date in items:
        _process(tenant_code, business_date)
    return len(items)


def run_scheduled() -> None:
    interval_seconds = int(os.getenv('RUNNER_INTERVAL_SECONDS', '300'))
    logger.info('Starting scheduled runner interval_seconds=%s', interval_seconds)
    while True:
        processed = run_once()
        logger.info('Runner cycle complete processed=%s sleeping=%ss', processed, interval_seconds)
        time.sleep(interval_seconds)


def main() -> None:
    mode = os.getenv('RUNNER_MODE', 'scheduled').strip().lower()
    if mode == 'once':
        processed = run_once()
        logger.info('Run-once completed processed=%s', processed)
        return
    if mode == 'scheduled':
        run_scheduled()
        return
    raise ValueError(f'Unsupported RUNNER_MODE={mode}. Use once or scheduled.')


if __name__ == '__main__':
    main()
