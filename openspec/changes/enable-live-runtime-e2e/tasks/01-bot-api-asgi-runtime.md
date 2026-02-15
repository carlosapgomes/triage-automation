# Slice 01 - Bot API ASGI Runtime

## Goal
Run `bot-api` as a real long-lived ASGI service while preserving existing route behavior.

## Scope boundaries
Included: runtime serving entrypoint and compose command alignment.
Excluded: new API routes, payload contract changes, business logic redesign.

## Files to create/modify
- `apps/bot_api/main.py`
- `docker-compose.yml`
- tests under `tests/integration/` for runtime serving behavior

## Tests to write FIRST (TDD)
- Add failing integration test proving app process serves existing `/callbacks/triage-decision` and `/auth/login` routes.
- Add failing regression test that callback behavior remains unchanged.

## Implementation steps
1. Add ASGI runtime startup path for `create_app()`.
2. Align compose command to run ASGI server.
3. Keep existing dependency wiring and route handlers intact.

## Refactor steps
- Extract small runtime bootstrap helpers if startup code becomes dense.

## Verification commands
- `uv run pytest tests/integration/test_triage_decision_webhook.py tests/integration/test_login_endpoint.py -q`
- `uv run ruff check .`
- `uv run mypy src apps`

## Mandatory checklist
- [x] failing tests written first
- [x] bot-api serves existing routes in runtime mode
- [x] no webhook/login behavior change
- [x] public docstrings and typed signatures preserved
- [x] verification commands pass

## STOP RULE
- [x] stop here and do not start next slice
