# cash-app

Production-style multi-tenant AR cash application / bank reconciliation pipeline.

## Overview

Cash-app ingests raw bank statement (Excel `.xlsx`) and remittance advice (PDF) files from Azure Blob Storage, parses them, runs a rule-based matching engine (optionally backed by Google Gemini LLM for PDF extraction), generates GL journal entries, and provides a React analyst dashboard for reviewing and posting matches.

**Stack:** Python 3.13 · FastAPI · SQLAlchemy 2 · Alembic · PostgreSQL 16 · Azurite (Azure Storage emulator) · React 19 · Vite 7 · Material UI v7

---

## What is included

- **PostgreSQL schema** managed by Alembic migrations (tenants, blob objects, ingestion runs, bank statements, remittance advices, reconciliation matches, journal entries, job schedule rules)
- **Azurite** blob storage for tenant/date-partitioned raw files
- **Parsing service** — Excel bank statement parser (German column headers) and PDF remittance parser (LLM or heuristic fallback)
- **LLM service** — Gemini API integration for structured remittance data extraction; cascades to regex heuristics when no API key is configured
- **Matching service** — three-step confidence-scored rule engine: header reference matching → line buyer_reference fallback → no-match sentinel
- **Run service** — full pipeline orchestration (download → parse → match → journal) with idempotency guards via PostgreSQL `ON CONFLICT DO NOTHING`
- **Job runner** — standalone daemon (scheduled or one-shot) with advisory locking to prevent duplicate processing
- **FastAPI backend** — four router groups: `/runs`, `/matches`, `/analytics`, `/jobs`
- **React + MUI dashboard** — three pages: Analytics (reconciliation overview, match evidence), Jobs (schedule rules + WebSocket progress), Journal (GL entries)
- **Bootstrap script** to upload sample files from `data/` into Azurite

---

## Quickstart

```bash
make setup        # copy .env.example → .env and run uv sync
make infra-up     # start postgres + azurite
make db-upgrade   # apply all Alembic migrations
make seed-raw     # upload sample files to Azurite
make api-up       # start backend (port 8000) + frontend (port 5173)
make runner-up    # optional: start scheduled job runner
```

---

## Blob partitioning convention

```
raw/{tenant}/bank-statement/{yyyy}/{mm}/{dd}/{prefix}_{filename}.xlsx
raw/{tenant}/remittance/{yyyy}/{mm}/{dd}/{prefix}_{filename}.pdf
```

---

## Configuration

All settings are read from environment variables (or a `.env` file). Key variables:

| Variable | Default | Description |
|---|---|---|
| `POSTGRES_HOST` | `localhost` | |
| `POSTGRES_PORT` | `5432` | |
| `POSTGRES_DB` | `backend` | |
| `POSTGRES_USER` | `backend` | |
| `POSTGRES_PASSWORD` | `backend` | |
| `AZURITE_BLOB_HOST` | `127.0.0.1` | |
| `AZURITE_BLOB_PORT` | `10000` | |
| `AZURE_ACCOUNT_NAME` | `devstoreaccount1` | Azurite default |
| `AZURE_ACCOUNT_KEY` | _(Azurite default)_ | |
| `AZURE_RAW_CONTAINER` | `raw` | Blob container for uploads |
| `APP_HOST` | `0.0.0.0` | |
| `APP_PORT` | `8000` | |
| `GOOGLE_API_KEY` | _(none)_ | Gemini LLM key; falls back to heuristic if unset |
| `GEMINI_MODEL` | `gemini-flash-latest` | |
| `AUTO_POST_CONFIDENCE_THRESHOLD` | `0.9` | Minimum confidence to auto-post without review |

---

## API Reference

Interactive docs available at `http://localhost:8000/docs` when the backend is running.

### Health

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Returns `{"status": "ok"}` |

### Runs (`/runs`)

| Method | Path | Description |
|---|---|---|
| `POST` | `/runs/ingest` | Trigger full ingest run (parse → match → journal) for a tenant + business_date |
| `GET` | `/runs/{run_id}` | Get run status, counters, and timestamps |
| `GET` | `/runs/{run_id}/items` | Get matched items (bank/remittance line counts + match list) |
| `POST` | `/runs/{run_id}/post-journals` | Post journal entries; requires `X-Actor-Id` header |
| `GET` | `/runs/{run_id}/journals` | Get generated journal lines for a run |

### Matches (`/matches`)

| Method | Path | Description |
|---|---|---|
| `POST` | `/matches/{match_id}/approve` | Approve a match with optional `reason_code` and `comment` |
| `POST` | `/matches/{match_id}/reject` | Reject a match |
| `POST` | `/matches/manual-link` | Manually link a bank row to a remittance line; creates `APPROVED` match with `confidence=1.0` |

All match endpoints accept `X-Actor-Id` header and return `MatchActionResponse`.

### Analytics (`/analytics`)

| Method | Path | Description |
|---|---|---|
| `GET` | `/analytics/summary` | Pie-chart data: matched/unmatched/review counts + per-buyer remittance doc counts |
| `GET` | `/analytics/matches` | Flat match list with joined bank + remittance fields; optional `?status=` filter |
| `GET` | `/analytics/bank-statements` | All bank statement rows (sorted by booking_date desc) |
| `GET` | `/analytics/remittance-headers` | All remittance advice headers with embedded line arrays |
| `POST` | `/analytics/matches/{match_id}/mark-matched` | Quick-approve a match → `APPROVED` |
| `POST` | `/analytics/matches/{match_id}/mark-unmatched` | Quick-reject a match → `UNMATCHED` |
| `POST` | `/analytics/matches/bulk-match` | Bulk-approve a list of match IDs |
| `POST` | `/analytics/matches/bulk-unmatch` | Bulk-reject a list of match IDs |
| `GET` | `/analytics/matches/{match_id}/evidence` | Side-by-side evidence: bank statement + remittance line + remittance header |
| `GET` | `/analytics/journal-entries` | All journal entries |
| `GET` | `/analytics/download/{blob_object_id}` | Stream raw blob (PDF/Excel) from Azurite |

### Jobs (`/jobs`)

| Method | Path | Description |
|---|---|---|
| `GET` | `/jobs/rules` | List all schedule rules |
| `POST` | `/jobs/rules` | Create a schedule rule (`processing` or `matching`; daily/weekly/monthly) |
| `PATCH` | `/jobs/rules/{rule_id}` | Update a rule |
| `DELETE` | `/jobs/rules/{rule_id}` | Delete a rule (204) |
| `POST` | `/jobs/rules/{rule_id}/trigger` | Manually trigger a rule (background thread) |
| `WS` | `/jobs/ws/{rule_id}` | WebSocket for real-time job progress |

---

## Matching Algorithm

The matching engine scores each bank statement row against all available remittance advices in three steps:

1. **Header reference matching** — compares `bank_reference`, `buyer_reference`, and `buyer_account_number` between the bank row and remittance header. 2+ field hits → base confidence `0.80`; 1 field hit → `0.55`. Amount agreement (±0.02) adds `+0.12` for total match or `+0.08` for line-combination match; no amount agreement deducts `−0.10`.
2. **Line buyer_reference fallback** — matches `remittance_line.buyer_reference == bank.buyer_reference`; confidence `0.55`, status `MANUAL_REVIEW`.
3. **No-match sentinel** — confidence `0.10`, status `UNMATCHED`.

**Status thresholds:** `≥ 0.85 → AUTO_MATCHED` · `≥ 0.65 → PARTIAL_MATCH` · `< 0.65 → MANUAL_REVIEW`

**Auto-post threshold:** runs with all selected matches at `confidence ≥ AUTO_POST_CONFIDENCE_THRESHOLD` (default `0.9`) transition to `READY_TO_POST`; otherwise `REVIEW_REQUIRED`.

---

## Run Status Lifecycle

```
RECEIVED → PARSED → MATCHED → READY_TO_POST → POSTED
                           └→ REVIEW_REQUIRED → POSTED
                    └→ FAILED
```

---

## Job Runner (Compose Service)

```bash
make runner-up    # start scheduled runner (polls every 300 s)
make runner-down  # stop runner
make runner-once  # one-shot run and exit
```

Manual one-off with explicit tenant/date:
```bash
docker compose run --rm \
  -e RUNNER_MODE=once \
  -e RUNNER_TENANT_CODE=bike-team-gmbh \
  -e RUNNER_BUSINESS_DATE=2026-03-19 \
  job-runner
```

Runner env vars:

| Variable | Default | Description |
|---|---|---|
| `RUNNER_MODE` | `scheduled` | `scheduled` or `once` |
| `RUNNER_INTERVAL_SECONDS` | `300` | Poll interval in scheduled mode |
| `RUNNER_TENANT_CODE` | _(all)_ | Optional tenant filter |
| `RUNNER_BUSINESS_DATE` | _(all)_ | Optional date filter (`YYYY-MM-DD`) |

---

## Makefile targets

| Target | Description |
|---|---|
| `make setup` | Copy `.env.example` → `.env` and run `uv sync` |
| `make infra-up` | Start postgres + azurite only |
| `make infra-down` | `docker compose down` |
| `make db-upgrade` | `uv run alembic upgrade head` |
| `make db-revision m="message"` | Auto-generate a new Alembic migration |
| `make seed-raw` | Run `scripts/bootstrap_raw_data.py` |
| `make api-up` | Start backend + frontend containers |
| `make api-down` | Stop backend + frontend |
| `make runner-up` | Start job-runner in scheduled mode |
| `make runner-down` | Stop job-runner |
| `make runner-once` | One-shot job-runner run |
| `make lint` | `uv run ruff check .` |
| `make run` | `uv run backend` (local dev server) |
| `make test` | `uv run pytest -q` |

---

## Docker Services

| Service | Image / Build | Ports | Notes |
|---|---|---|---|
| `postgres` | `postgres:16-alpine` | `5432` | Healthcheck: `pg_isready` |
| `azurite` | `mcr.microsoft.com/azure-storage/azurite:3.35.0` | `10000` | Blob emulator; `--skipApiVersionCheck` |
| `backend` | `Dockerfile.backend` | `8000` | FastAPI app; depends on postgres + azurite healthy |
| `job-runner` | `Dockerfile.backend` | — | Scheduler daemon; shares backend image |
| `frontend` | `Dockerfile.frontend` | `5173` | React/Vite; `VITE_API_URL=http://localhost:8000` |

---

## Demo Runbook (Clean Start to Journals)

Use these commands in order for a reliable end-to-end demo.

1. Clean reset (drop DB + Azurite volumes):
```bash
docker compose down -v
```

2. Start core services:
```bash
docker compose up -d --build
```

3. Apply migrations:
```bash
uv run alembic upgrade head
```

4. Seed sample files into Azurite:
```bash
uv run python scripts/bootstrap_raw_data.py --tenant sportcenter-team-gmbh --business-date 2026-03-21
```

5. Trigger ingestion (parse + match):
```bash
curl.exe -X POST "http://localhost:8000/runs/ingest" ^
  -H "Content-Type: application/json" ^
  -d "{\"tenant_code\":\"sportcenter-team-gmbh\",\"business_date\":\"2026-03-21\"}"
```

6. Capture run id and inspect matching output:
```bash
RUN_ID=$(curl -sS -X POST http://localhost:8000/runs/ingest \
  -H 'Content-Type: application/json' \
  -d '{"tenant_code":"sportcenter-team-gmbh","business_date":"2026-03-21"}' \
  | python -c "import sys,json; print(json.load(sys.stdin)['run_id'])")

echo "$RUN_ID"
curl -sS "http://localhost:8000/runs/$RUN_ID/items"
```

7. Post journals and verify journal output:
```bash
curl -sS -X POST "http://localhost:8000/runs/$RUN_ID/post-journals" -H "X-Actor-Id: demo-user"
curl -sS "http://localhost:8000/runs/$RUN_ID/journals"
```

8. Optional DB-level proof:
```bash
docker compose exec -T postgres psql -U backend -d backend -c "select count(*) from bank_statement;"
docker compose exec -T postgres psql -U backend -d backend -c "select count(*) from reconciliation_matches;"
docker compose exec -T postgres psql -U backend -d backend -c "select count(*) from journal_entry;"
```
