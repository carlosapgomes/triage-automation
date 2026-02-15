# Slice 05 - Case, Audit, and Message Repositories

## Goal
Implement repository ports/adapters for `cases`, `case_events`, and `case_messages`.

## Scope boundaries
Included: persistence operations and idempotency-safe duplicate handling.
Excluded: job queue and worker loop.

## Files to create/modify
- `src/triage_automation/application/ports/case_repository_port.py`
- `src/triage_automation/application/ports/audit_repository_port.py`
- `src/triage_automation/application/ports/message_repository_port.py`
- `src/triage_automation/infrastructure/db/session.py`
- `src/triage_automation/infrastructure/db/case_repository.py`
- `src/triage_automation/infrastructure/db/audit_repository.py`
- `src/triage_automation/infrastructure/db/message_repository.py`
- `tests/integration/test_case_repositories.py`

## Tests to write FIRST (TDD)
- Case insert works.
- Duplicate `room1_origin_event_id` handled deterministically.
- Append-only audit persistence works.
- Duplicate `(room_id,event_id)` in `case_messages` rejected safely.

## Implementation steps
1. Add ports and async DB adapters.
2. Implement transaction helpers.
3. Translate unique violations into domain-safe errors.

## Verification commands
- `uv run pytest tests/integration/test_case_repositories.py -q`
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
