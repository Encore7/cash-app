.PHONY: setup infra-up infra-down db-upgrade db-revision seed-raw lint run api-up api-down test

setup:
	cp -n .env.example .env || true
	uv sync

infra-up:
	docker compose up -d postgres azurite

api-up:
	docker compose up -d backend frontend

api-down:
	docker compose stop backend frontend

infra-down:
	docker compose down

db-upgrade:
	uv run alembic upgrade head

db-revision:
	uv run alembic revision --autogenerate -m "$(m)"

seed-raw:
	uv run python scripts/bootstrap_raw_data.py

lint:
	uv run ruff check .

run:
	uv run backend

test:
	uv run pytest -q
