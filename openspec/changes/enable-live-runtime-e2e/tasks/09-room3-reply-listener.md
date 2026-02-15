# Slice 09 - Room-3 Reply Listener Routing

## Goal
Wire Room-3 reply events from runtime listener into existing strict parser/re-prompt service flow.

## Scope boundaries
Included: reply event routing and case-target mapping path.
Excluded: new template formats or scheduling behavior changes.

## Files to create/modify
- `apps/bot_matrix/main.py`
- Room-3 reply listener/mapping modules under `src/triage_automation/infrastructure/matrix/`
- integration tests for listener-to-service flow

## Tests to write FIRST (TDD)
- Add failing integration test for valid Room-3 reply processed through listener path.
- Add failing integration test for invalid template causing strict re-prompt through listener path.

## Implementation steps
1. Detect Room-3 reply-to events in runtime listener.
2. Map to existing `Room3ReplyEvent` and call `Room3ReplyService`.
3. Preserve strict format/re-prompt and WAIT_APPT semantics.

## Refactor steps
- Extract reply-event parsing helpers to minimize branching in main loop.

## Verification commands
- `uv run pytest tests/integration/test_room3_scheduler_reply_flow.py -q`
- `uv run ruff check .`
- `uv run mypy src apps`

## Mandatory checklist
- [x] failing tests written first
- [x] strict Room-3 parser behavior remains unchanged
- [x] invalid replies re-prompt and remain in WAIT_APPT
- [x] public docstrings and typed signatures preserved
- [x] verification commands pass

## STOP RULE
- [x] stop here and do not start next slice
