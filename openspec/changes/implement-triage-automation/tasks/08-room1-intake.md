# Slice 08 - Room-1 PDF Intake Flow

## Goal
Process valid Room-1 human PDF events into case creation + processing ack + queue enqueue.

## Scope boundaries
Included: filtering, idempotent intake, audit, message tracking.
Excluded: PDF processing internals.

## Files to create/modify
- `apps/bot_matrix/main.py`
- `src/triage_automation/infrastructure/matrix/event_parser.py`
- `src/triage_automation/application/services/room1_intake_service.py`
- `tests/unit/test_room1_event_parser.py`
- `tests/integration/test_room1_intake_flow.py`

## Tests to write FIRST (TDD)
- Ignore non-human events.
- Ignore non-PDF messages.
- Valid PDF creates one case and enqueues `process_pdf_case`.
- Duplicate intake event is ignored.
- Concurrency race still creates one case.

## Implementation steps
1. Parse and validate intake events.
2. Persist case/audit/message mapping transactionally.
3. Post processing reply-to message and enqueue job.

## Verification commands
- `uv run pytest tests/unit/test_room1_event_parser.py -q`
- `uv run pytest tests/integration/test_room1_intake_flow.py -q`
- `uv run ruff check .`
- `uv run mypy src apps`

## Checklist
- [x] spec section referenced
- [x] failing tests written
- [x] edge cases included
- [x] concurrency cases included
- [x] minimal implementation complete
- [x] tests pass
- [x] lint passes
- [x] type checks pass
- [x] stop and do not start next slice
