# Slice 16 - Room-3 Reply Parsing and Strict Re-prompt

## Goal
Parse strict scheduler templates; invalid replies always trigger strict re-prompt and remain `WAIT_APPT`.

## Scope boundaries
Included: reply-to validation, case ID validation, parse success/failure handling.
Excluded: cleanup logic.

## Files to create/modify
- `src/triage_automation/domain/scheduler_parser.py`
- `src/triage_automation/application/services/room3_reply_service.py`
- `src/triage_automation/infrastructure/matrix/message_templates.py`
- `tests/unit/test_scheduler_parser.py`
- `tests/integration/test_room3_scheduler_reply_flow.py`

## Tests to write FIRST (TDD)
- Confirmed template parses required fields.
- Denied template parses required fields.
- Non-reply or wrong target request ignored.
- Case mismatch ignored and audited.
- Invalid format sends strict re-prompt and keeps `WAIT_APPT`.

## Implementation steps
1. Implement strict parser with deterministic error types.
2. Add service flow for validation + parse + enqueue next final-reply job.
3. Add strict re-prompt template for invalid format.

## Verification commands
- `uv run pytest tests/unit/test_scheduler_parser.py -q`
- `uv run pytest tests/integration/test_room3_scheduler_reply_flow.py -q`
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
