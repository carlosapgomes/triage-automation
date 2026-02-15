# Slice 15 - Room-3 Request Posting

## Goal
Post scheduling request + Room-3 ack and transition case to `WAIT_APPT`.

## Scope boundaries
Included: request/ack template posting and message tracking.
Excluded: reply parsing.

## Files to create/modify
- `src/triage_automation/application/services/post_room3_request_service.py`
- `src/triage_automation/infrastructure/matrix/message_templates.py`
- `tests/integration/test_post_room3_request.py`

## Tests to write FIRST (TDD)
- Request includes `case: <uuid>`.
- Ack is posted and tracked for audit-only thumbs.
- Status transitions to `WAIT_APPT`.
- Duplicate job execution remains idempotent.

## Implementation steps
1. Add request template formatter.
2. Post request and ack with stored event mappings.
3. Append related audit events.

## Verification commands
- `uv run pytest tests/integration/test_post_room3_request.py -q`
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
