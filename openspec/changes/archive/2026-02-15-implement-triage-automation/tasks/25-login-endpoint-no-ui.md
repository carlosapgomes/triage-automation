# Slice 25 - Minimal Login Endpoint (No UI)

## Goal
Expose one backend login endpoint for auth foundation issuing an opaque token, no UI.

## Scope boundaries
Included: one login route, auth service integration, auth event audit, response contract.
Excluded: any UI, user management endpoints, prompt editing endpoints.

## Files to create/modify
- `apps/bot_api/main.py`
- `src/triage_automation/application/dto/auth_models.py`
- `src/triage_automation/infrastructure/http/auth_router.py`
- `src/triage_automation/infrastructure/security/token_service.py`
- `tests/integration/test_login_endpoint.py`

## Tests to write FIRST (TDD)
- Valid credentials return opaque token response including role.
- Invalid credentials return auth error.
- Inactive user returns forbidden/inactive response.
- Login writes corresponding `auth_events` entry.
- Login persists token hash in `auth_tokens`.
- Route count unchanged except login route addition.

## Implementation steps
1. Add request/response DTOs.
2. Add opaque token generation + token hash persistence flow.
3. Add login route calling auth service and returning opaque token response.

## Refactor steps
- Keep route thin; move all decision logic to service.

## Verification commands
- `uv run pytest tests/integration/test_login_endpoint.py -q`
- `uv run ruff check .`
- `uv run mypy src apps`

## Mandatory checklist
- [x] spec section referenced
- [x] failing tests written
- [x] edge cases included
- [x] minimal implementation
- [x] tests pass
- [x] lint passes
- [x] type checks pass
- [x] no triage workflow behavior change

## STOP RULE
- [x] stop here and do not start next slice
