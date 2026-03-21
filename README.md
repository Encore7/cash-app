# cash-app

Production-style starter for a multi-tenant cash application pipeline.

## What is included
- Postgres metadata schema managed by Alembic
- Azurite blob storage for tenant/date-partitioned raw files
- SQLAlchemy models for tenant, ingestion, matching, and journal metadata
- Bootstrap script to upload sample files from `data/` into Azurite
- FastAPI backend for ingestion, matching decisions, and journal posting
- React + Material UI dashboard for analyst workflow preview

## Quickstart
1. `make setup`
2. `make infra-up`
3. `make db-upgrade`
4. `make seed-raw`
5. `make api-up`
6. Optional scheduled runner: `make runner-up`

## Blob partitioning convention
- `raw/{tenant}/bank-statement/{yyyy}/{mm}/{dd}/...xlsx`
- `raw/{tenant}/remittance/{yyyy}/{mm}/{dd}/...pdf`

## API endpoints
- `POST /runs/ingest`
- `GET /runs/{run_id}`
- `GET /runs/{run_id}/items`
- `POST /matches/{id}/approve`
- `POST /matches/{id}/reject`
- `POST /matches/manual-link?run_id=...`
- `POST /runs/{run_id}/post-journals`
- `GET /runs/{run_id}/journals`

## Job Runner (Compose Service)
- Scheduled mode service: `make runner-up`
- Stop runner service: `make runner-down`
- Manual one-off run: `make runner-once`

Manual one-off with explicit tenant/date:
```bash
docker compose run --rm \
  -e RUNNER_MODE=once \
  -e RUNNER_TENANT_CODE=bike-team-gmbh \
  -e RUNNER_BUSINESS_DATE=2026-03-19 \
  job-runner
```

Runner env vars:
- `RUNNER_MODE=scheduled|once`
- `RUNNER_INTERVAL_SECONDS=300`
- `RUNNER_TENANT_CODE=` optional tenant filter
- `RUNNER_BUSINESS_DATE=` optional date filter (`YYYY-MM-DD`)

## Demo Runbook (Clean Start to Journals)
Use these commands in order for a reliable end-to-end demo.

1. Clean reset (drop DB + Azurite volumes):
```bash
docker compose down -v
```

2. Start core services:
```bash
docker compose up -d --build postgres azurite backend frontend
```

3. Apply migrations:
```bash
uv run alembic upgrade head
```

4. Seed sample files into Azurite:
```bash
uv run python scripts/bootstrap_raw_data.py --tenant bike-team-gmbh --business-date 2026-03-21
```

5. Trigger ingestion (parse + match):
```bash
curl -sS -X POST http://localhost:8000/runs/ingest \
  -H 'Content-Type: application/json' \
  -d '{"tenant_code":"bike-team-gmbh","business_date":"2026-03-21"}'
```

6. Capture run id and inspect matching output:
```bash
RUN_ID=$(curl -sS -X POST http://localhost:8000/runs/ingest \
  -H 'Content-Type: application/json' \
  -d '{"tenant_code":"bike-team-gmbh","business_date":"2026-03-21"}' \
  | python -c "import sys,json; print(json.load(sys.stdin)['run_id'])")

echo "$RUN_ID"
curl -sS "http://localhost:8000/runs/$RUN_ID/items"
```

7. Post journals and verify journal output:
```bash
curl -sS -X POST "http://localhost:8000/runs/$RUN_ID/post-journals"
curl -sS "http://localhost:8000/runs/$RUN_ID/journals"
```

8. Optional DB-level proof:
```bash
docker compose exec -T postgres psql -U backend -d backend -c "select count(*) from bank_statement;"
docker compose exec -T postgres psql -U backend -d backend -c "select count(*) from reconciliation_matches;"
docker compose exec -T postgres psql -U backend -d backend -c "select count(*) from journal_entry;"
```
