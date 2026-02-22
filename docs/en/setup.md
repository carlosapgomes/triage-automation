# Setup Guide

Language: [Portugues (BR)](../setup.md) | **English**

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

Core variables for Matrix-only decision runtime:

- `ROOM1_ID`
- `ROOM2_ID`
- `ROOM3_ID`
- `MATRIX_HOMESERVER_URL`
- `DATABASE_URL`
- `LLM_RUNTIME_MODE`
- `LOG_LEVEL`
- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`

For the complete environment contract, review `.env.example`.

Provider mode optional variables:

- `OPENAI_API_KEY`
- `OPENAI_MODEL_LLM1`
- `OPENAI_MODEL_LLM2`
- `OPENAI_TIMEOUT_SECONDS` (default: 60; increase for large PDFs)

Optional first-admin bootstrap variables:

- `BOOTSTRAP_ADMIN_EMAIL`
- `BOOTSTRAP_ADMIN_PASSWORD` or `BOOTSTRAP_ADMIN_PASSWORD_FILE` (set only one)

Bootstrap behavior:

- Executed by `bot-api` on startup
- Creates initial `admin` user only when `users` table is empty
- If users already exist, bootstrap is skipped
- `BOOTSTRAP_ADMIN_PASSWORD_FILE` is recommended in production-like environments

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

## 5. Browser-first login/logout flow

After migrations and service startup, use the portal directly in a browser.

1. Open root page:

- URL: `http://localhost:8000/`
- expected for anonymous user: redirect to `/login`

1. Login:

- submit `email` + `password` on `GET /login`
- expected success: redirect to `/dashboard/cases`
- expected invalid credentials: HTML error on login page, no session cookie

1. Authorization by role:

- `reader`: can access dashboard pages, cannot access prompt-admin pages
- `admin`: can access dashboard pages and prompt-admin pages

1. Logout:

- submit `POST /logout` (button `Sair` in header)
- expected result: redirect to `/login` and session cookie cleared

## 6. Run local stack (optional)

```bash
docker compose up --build
```

## 7. Runtime smoke validation (recommended before manual E2E)

Follow `docs/en/runtime-smoke.md` to validate:

- local `uv` runtime process startup
- Matrix structured reply readiness for Room-2 decisions
- deterministic LLM runtime mode for provider-unavailable testing

## 8. Admin operations

### 8.1 Reset admin password (CLI)

Use this flow when an admin password needs rotation or recovery.
It updates the bcrypt hash directly in `users` using the configured `DATABASE_URL`.

1. Set target admin identity and new password:

```bash
export ADMIN_EMAIL=admin@example.org
export ADMIN_NEW_PASSWORD='change-me-now'
```

1. Apply reset:

```bash
uv run python - <<'PY'
import asyncio
import os
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine
from triage_automation.config.settings import load_settings
from triage_automation.infrastructure.security.password_hasher import BcryptPasswordHasher

email = os.environ["ADMIN_EMAIL"].strip().lower()
new_password = os.environ["ADMIN_NEW_PASSWORD"]
if not email:
    raise SystemExit("ADMIN_EMAIL cannot be blank")
if not new_password.strip():
    raise SystemExit("ADMIN_NEW_PASSWORD cannot be blank")

settings = load_settings()
engine = create_async_engine(settings.database_url)
hasher = BcryptPasswordHasher()
password_hash = hasher.hash_password(new_password)

async def main() -> None:
    async with engine.begin() as conn:
        result = await conn.execute(
            sa.text(
                "UPDATE users "
                "SET password_hash = :password_hash, updated_at = CURRENT_TIMESTAMP "
                "WHERE lower(email) = :email AND role = 'admin' AND is_active = true"
            ),
            {"password_hash": password_hash, "email": email},
        )
    await engine.dispose()
    if result.rowcount == 0:
        raise SystemExit("No active admin user found for ADMIN_EMAIL")
    print("Admin password updated successfully")

asyncio.run(main())
PY
```

1. Verify with login:

- `POST /auth/login` with the same `ADMIN_EMAIL` and new password
- expected result: `200` and a token payload

### 8.2 Reset admin password (Docker Compose)

Use this flow when the stack runs in containers and you prefer not to use host Python tooling.

1. Ensure `bot-api` is running:

```bash
docker compose up -d postgres bot-api
```

1. Set target admin identity and new password:

```bash
export ADMIN_EMAIL=admin@example.org
export ADMIN_NEW_PASSWORD='change-me-now'
```

1. Apply reset from inside `bot-api` container:

```bash
docker compose exec -T \
  -e ADMIN_EMAIL="$ADMIN_EMAIL" \
  -e ADMIN_NEW_PASSWORD="$ADMIN_NEW_PASSWORD" \
  bot-api \
  uv run python - <<'PY'
import asyncio
import os
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine
from triage_automation.config.settings import load_settings
from triage_automation.infrastructure.security.password_hasher import BcryptPasswordHasher

email = os.environ["ADMIN_EMAIL"].strip().lower()
new_password = os.environ["ADMIN_NEW_PASSWORD"]
if not email:
    raise SystemExit("ADMIN_EMAIL cannot be blank")
if not new_password.strip():
    raise SystemExit("ADMIN_NEW_PASSWORD cannot be blank")

settings = load_settings()
engine = create_async_engine(settings.database_url)
hasher = BcryptPasswordHasher()
password_hash = hasher.hash_password(new_password)

async def main() -> None:
    async with engine.begin() as conn:
        result = await conn.execute(
            sa.text(
                "UPDATE users "
                "SET password_hash = :password_hash, updated_at = CURRENT_TIMESTAMP "
                "WHERE lower(email) = :email AND role = 'admin' AND is_active = true"
            ),
            {"password_hash": password_hash, "email": email},
        )
    await engine.dispose()
    if result.rowcount == 0:
        raise SystemExit("No active admin user found for ADMIN_EMAIL")
    print("Admin password updated successfully")

asyncio.run(main())
PY
```

1. Verify with login:

- `POST /auth/login` with the same `ADMIN_EMAIL` and new password
- expected result: `200` and a token payload

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
