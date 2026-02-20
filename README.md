# Augmented Triage System (ATS)

Augmented Triage System (ATS) is a backend service designed to support real-world clinical triage workflows while keeping healthcare professionals fully in control of decisions and patient care.

![Python](https://img.shields.io/badge/python-3.12-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Lint](https://img.shields.io/badge/lint-ruff-orange.svg)
![Type Check](https://img.shields.io/badge/types-mypy-blue.svg)
![Tests](https://img.shields.io/badge/tests-pytest-brightgreen.svg)

Backend services for an event-driven triage workflow over Matrix rooms.

Core services:

- `bot-api` (FastAPI auth/runtime foundation)
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
- Admin and monitoring surface is available in `bot-api`:
  - web session flow (`GET /`, `GET /login`, `POST /login`, `POST /logout`)
  - login/auth (`/auth/login`)
  - monitoring API (`/monitoring/cases`, `/monitoring/cases/{case_id}`)
  - server-rendered dashboard (`/dashboard/cases`, `/dashboard/cases/{case_id}`)
  - server-rendered prompt admin (`GET /admin/prompts`, `POST /admin/prompts/{prompt_name}/activate-form`)
  - admin prompt-management API (`/admin/prompts/*`)

## Runtime Topology

```text
Matrix Rooms ---> bot-matrix ----\
                                  \
Login/Auth ----------> bot-api ----> PostgreSQL <---- worker
```

## Public Surface (Current)

Web pages and session routes:

- `GET /`
- `GET /login`
- `POST /login`
- `POST /logout`
- `GET /dashboard/cases`
- `GET /dashboard/cases/{case_id}`
- `GET /admin/prompts`
- `POST /admin/prompts/{prompt_name}/activate-form`

JSON API routes:

- `POST /auth/login`
- `GET /monitoring/cases`
- `GET /monitoring/cases/{case_id}`
- `GET /admin/prompts/versions`
- `GET /admin/prompts/{prompt_name}/active`
- `POST /admin/prompts/{prompt_name}/activate`

## Web Access and Roles

Browser-first access flow:

1. Open `/` in a browser.
2. Anonymous access is redirected to `/login`.
3. Submit email and password in the login form.
4. On success, the app redirects to `/dashboard/cases`.
5. Use `Sair` (`POST /logout`) to end the session.

Role matrix:

| Role | Dashboard pages | Prompt admin pages | Prompt admin APIs |
| --- | --- | --- | --- |
| `reader` | allowed | forbidden (`403`) | forbidden (`403`) |
| `admin` | allowed | allowed | allowed |

## Project Docs

- Setup: `docs/setup.md`
- Admin operations (bootstrap + password reset): `docs/setup.md#7-admin-operations`
- Runtime smoke runbook: `docs/runtime-smoke.md`
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

1. Create local env file:

```bash
cp .env.example .env
```

1. Run database migrations:

```bash
uv run alembic upgrade head
```

1. Optional: bootstrap first admin at startup (one-time when `users` is empty):

```bash
export BOOTSTRAP_ADMIN_EMAIL=admin@example.org
export BOOTSTRAP_ADMIN_PASSWORD='change-me-now'
```

For production-like environments, prefer `BOOTSTRAP_ADMIN_PASSWORD_FILE`.

1. Run local quality gates:

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
