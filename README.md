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
