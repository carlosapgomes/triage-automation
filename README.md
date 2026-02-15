# Triage Automation

Backend services for an event-driven triage workflow over Matrix rooms.

Core services:
- `bot-api` (FastAPI webhook + auth foundation)
- `bot-matrix` (Matrix event ingestion wiring)
- `worker` (job execution runtime)

This repo is implemented with strict TDD and OpenSpec slice history under `openspec/changes/archive/`.

## Current Scope

- Triage workflow foundation is implemented and covered by automated tests.
- Admin foundation exists in backend only (prompt templates, users/roles, auth/login).
- No admin UI is included.

## Project Docs

- Setup: `docs/setup.md`
- Architecture: `docs/architecture.md`
- Security: `docs/security.md`
- Internal implementation context: `PROJECT_CONTEXT.md`

## Quick Start

1. Install dependencies:
```bash
uv sync
```

2. Create local env file:
```bash
cp .env.example .env
```

3. Run database migrations:
```bash
uv run alembic upgrade head
```

4. Run local quality gates:
```bash
uv run ruff check .
uv run mypy src apps
uv run pytest -q
```

## Local Services (Docker Compose)

```bash
docker compose up --build
```

Compose expects `.env` to be present and starts:
- `postgres`
- `bot-api`
- `bot-matrix`
- `worker`

## CI

Quality gates are enforced in `.github/workflows/quality-gates.yml`.
