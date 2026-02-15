# Triage Automation

![Python](https://img.shields.io/badge/python-3.12-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Lint](https://img.shields.io/badge/lint-ruff-orange.svg)
![Type Check](https://img.shields.io/badge/types-mypy-blue.svg)
![Tests](https://img.shields.io/badge/tests-pytest-brightgreen.svg)

Backend services for an event-driven triage workflow over Matrix rooms.

Core services:
- `bot-api` (FastAPI webhook + auth foundation)
- `bot-matrix` (Matrix event ingestion wiring)
- `worker` (job execution runtime)

This repo is implemented with strict TDD and OpenSpec slice history under `openspec/changes/archive/`.

## Why This Project

- Automates multi-step triage flow across Matrix rooms.
- Preserves auditability with append-only event records.
- Uses deterministic state transitions and queued background jobs.
- Adds admin backend foundations (roles/auth/prompt templates) without introducing UI behavior.

## Current Scope

- Triage workflow foundation is implemented and covered by automated tests.
- Admin foundation exists in backend only (prompt templates, users/roles, auth/login).
- No admin UI is included.

## Runtime Topology

```text
Matrix Rooms ---> bot-matrix ----\
                                  \
Webhook Callback ---> bot-api -----> PostgreSQL <---- worker
                                  /
Login/Auth ----------> bot-api ---/
```

## Public API Surface (Current)

- `POST /callbacks/triage-decision` (HMAC-protected webhook callback)
- `POST /auth/login` (opaque-token login endpoint)

## Project Docs

- Setup: `docs/setup.md`
- Architecture: `docs/architecture.md`
- Security: `docs/security.md`
- Internal implementation context: `PROJECT_CONTEXT.md`

## Repository Layout

```text
apps/                         # Runtime entrypoints (bot-api, bot-matrix, worker)
src/triage_automation/        # Application/domain/infrastructure code
alembic/                      # DB migrations
tests/                        # Unit, integration, and e2e tests
docs/                         # Public project docs
openspec/                     # Change/spec workflow artifacts
```

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

## Deployment Note

This repository is currently optimized for local/dev deployment with Docker Compose.
For production deployment, add environment-specific hardening (secret manager integration,
network policy, TLS termination, and observability).

## CI

Quality gates are enforced in `.github/workflows/quality-gates.yml`.

## License

MIT. See `LICENSE`.

## Attribution

This project was developed with assistance from large language models (LLMs).
