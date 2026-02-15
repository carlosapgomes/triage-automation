# Slice 02 - Runtime Config and Docker Compose Baseline

## Goal
Add validated settings and compose wiring for `bot-api`, `bot-matrix`, `worker`, and `postgres`.

## Scope boundaries
Included: config contracts, env validation, basic service startup.
Excluded: webhook or Matrix business behavior.

## Files to create/modify
- `Dockerfile`
- `docker-compose.yml`
- `.env.example`
- `apps/bot_api/main.py`
- `apps/bot_matrix/main.py`
- `apps/worker/main.py`
- `src/triage_automation/config/settings.py`
- `tests/unit/test_settings.py`

## Tests to write FIRST (TDD)
- Required env var missing -> validation error.
- Defaults are deterministic.
- Room IDs and URLs are non-empty.

## Implementation steps
1. Define Pydantic settings model.
2. Wire app entrypoints to load settings.
3. Add compose baseline with Postgres dependency.

## Verification commands
- `uv run pytest tests/unit/test_settings.py -q`
- `uv run ruff check .`
- `uv run mypy src apps`

## Checklist
- [x] spec section referenced
- [x] failing tests written
- [x] edge cases included
- [x] minimal implementation complete
- [x] tests pass
- [x] lint passes
- [x] type checks pass
- [x] stop and do not start next slice
