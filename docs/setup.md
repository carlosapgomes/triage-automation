# Setup Guide

## Prerequisites

- Python `3.12.x`
- `uv`
- Docker + Docker Compose (optional but recommended for local stack)

## 1. Install dependencies

```bash
uv sync
```

## 2. Create local environment file

```bash
cp .env.example .env
```

Required variables (from `.env.example`):

- `ROOM1_ID`
- `ROOM2_ID`
- `ROOM3_ID`
- `MATRIX_HOMESERVER_URL`
- `WEBHOOK_PUBLIC_URL`
- `DATABASE_URL`
- `WEBHOOK_HMAC_SECRET`
- `LOG_LEVEL`
- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`

## 3. Run database migrations

```bash
uv run alembic upgrade head
```

## 4. Run test and quality gates

```bash
uv run ruff check .
uv run mypy src apps
uv run pytest -q
```

## 5. Run local stack (optional)

```bash
docker compose up --build
```

## Common commands

- Create migration:
```bash
uv run alembic revision -m "describe-change"
```

- Apply latest migration:
```bash
uv run alembic upgrade head
```

- Roll back one migration:
```bash
uv run alembic downgrade -1
```
