# Runtime Smoke Runbook

Language: [Portugues (BR)](../runtime-smoke.md) | **English**

This runbook validates local runtime readiness before manual end-to-end testing.
It does not change workflow behavior; it only verifies that runtime processes,
database migrations, Matrix decision-path readiness, and deterministic LLM
execution are working in a reproducible way.

## Decision Path Notice

- standard Room-2 decisions use Matrix structured replies.
- HTTP callback/widget decision submission is not part of runtime operation.

## Local UV Runtime Smoke

1. Prepare dependencies and env:

```bash
uv sync
cp .env.example .env
```

1. Start only Postgres:

```bash
docker compose up -d postgres
```

1. Apply migrations:

```bash
uv run alembic upgrade head
```

1. Start runtime processes in separate terminals:

```bash
uv run uvicorn apps.bot_api.main:create_app --factory --host 0.0.0.0 --port 8000
```

```bash
uv run python -m apps.bot_matrix.main
```

```bash
uv run python -m apps.worker.main
```

Set `LOG_LEVEL=DEBUG` in `.env` when you need heartbeat-style runtime traces.
At `INFO`, logs show startup and meaningful routed/claimed job activity.

1. Check API reachability:

```bash
curl -i http://127.0.0.1:8000/openapi.json
```

## Matrix Structured Reply Readiness

Run a focused integration test that exercises Room-2 structured reply handling:

```bash
uv run pytest tests/integration/test_room2_reply_flow.py -q
```

Expected result:

- Room-2 reply parsing/validation paths execute successfully.
- Decision handling is driven by Matrix reply events (no HTTP decision surface).

## Deterministic LLM Smoke Path

Use deterministic mode when provider credentials are unavailable:

```bash
export LLM_RUNTIME_MODE=deterministic
```

In this mode, worker runtime uses deterministic LLM adapters and still executes
the LLM-dependent stages (`LLM1`/`LLM2`) and enqueue transitions without changing
triage semantics.

For provider mode, set:

- `OPENAI_API_KEY`
- `OPENAI_MODEL_LLM1`
- `OPENAI_MODEL_LLM2`

## Room-4 periodic summary scheduling

The Room-4 summary scheduler is a *one-shot* process.
Each execution computes the previous 12-hour window in `America/Bahia`
and enqueues at most one `post_room4_summary` job.

Operational prerequisites:

- `worker` is running (it consumes the queued job)
- environment variables are configured: `ROOM4_ID`, `SUPERVISOR_SUMMARY_TIMEZONE`, `SUPERVISOR_SUMMARY_MORNING_HOUR`, `SUPERVISOR_SUMMARY_EVENING_HOUR`
- migrations are applied (`uv run alembic upgrade head`)

Manual execution (spot validation):

```bash
uv run python -m apps.scheduler.main
```

Expected behavior:

- at 07:00 (`America/Bahia`): schedules window `[19:00 previous day, 07:00 current day)`
- at 19:00 (`America/Bahia`): schedules window `[07:00 current day, 19:00 current day)`
- re-running the same window does not duplicate Room-4 posting (window idempotency)

Linux cron example (production):

```cron
CRON_TZ=America/Bahia
0 7,19 * * * cd /srv/triage-automation && /usr/local/bin/uv run python -m apps.scheduler.main >> /var/log/ats-room4-scheduler.log 2>&1
```

## UV and Compose Parity

Use the same entrypoint commands from `docker-compose.yml`:

```bash
docker compose up --build
docker compose logs -f bot-api bot-matrix worker
```

Compose command parity:

- `bot-api`: `uv run uvicorn apps.bot_api.main:create_app --factory --host 0.0.0.0 --port 8000`
- `bot-matrix`: `uv run python -m apps.bot_matrix.main`
- `worker`: `uv run python -m apps.worker.main`
