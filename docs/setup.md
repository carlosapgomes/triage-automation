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

## 5. Run local stack (optional)

```bash
docker compose up --build
```

## 6. Runtime smoke validation (recommended before manual E2E)

Follow `docs/runtime-smoke.md` to validate:

- local `uv` runtime process startup
- Matrix structured reply readiness for Room-2 decisions
- deterministic LLM runtime mode for provider-unavailable testing

## 7. Admin operations

### 7.1 Reset admin password (CLI)

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
