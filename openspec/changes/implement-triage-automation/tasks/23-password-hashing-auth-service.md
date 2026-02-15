# Slice 23 - Password Hashing Service and Auth Application Logic

## Goal
Implement secure password hashing/verification and login orchestration service.

## Scope boundaries
Included: bcrypt hasher adapter, auth application service, auth event logging.
Excluded: HTTP route and token transport concerns.

## Files to create/modify
- `src/triage_automation/application/ports/password_hasher_port.py`
- `src/triage_automation/infrastructure/security/password_hasher.py`
- `src/triage_automation/application/services/auth_service.py`
- `tests/unit/test_password_hasher.py`
- `tests/unit/test_auth_service.py`

## Tests to write FIRST (TDD)
- Hashing never stores plaintext and verifies correct password.
- Wrong password fails verification.
- Inactive users cannot authenticate.
- Login attempt always writes auth event (success/failure).

## Implementation steps
1. Add password hasher interface and bcrypt adapter.
2. Add auth service for credential verification.
3. Emit `auth_events` for outcomes.

## Refactor steps
- Keep auth decision logic pure and separate from persistence calls.

## Verification commands
- `uv run pytest tests/unit/test_password_hasher.py -q`
- `uv run pytest tests/unit/test_auth_service.py -q`
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
