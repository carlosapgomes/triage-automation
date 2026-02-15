# Slice 07 - Room-1 Intake Listener Routing

## Goal
Wire bot-matrix runtime loop for Room-1 PDF intake events into existing intake service.

## Scope boundaries
Included: listener loop parsing and routing to `Room1IntakeService`.
Excluded: reaction and Room-3 reply routing.

## Files to create/modify
- `apps/bot_matrix/main.py`
- runtime Matrix listener modules under `src/triage_automation/infrastructure/matrix/`
- integration tests for intake routing

## Tests to write FIRST (TDD)
- Add failing integration test proving a valid Room-1 PDF event reaches intake service via runtime listener.
- Add failing test proving unsupported events are safely ignored.

## Implementation steps
1. Build runtime listener polling/dispatch for Room-1 intake events.
2. Parse events with existing parser and route only valid intake payloads.
3. Keep idempotency and queue-enqueue behavior delegated to service layer.

## Refactor steps
- Extract event-dispatch helper(s) to keep listener loop readable.

## Verification commands
- `uv run pytest tests/integration/test_room1_intake_flow.py -q`
- `uv run ruff check .`
- `uv run mypy src apps`

## Mandatory checklist
- [x] failing tests written first
- [x] Room-1 intake events are routed through existing service
- [x] unsupported events are ignored safely
- [x] public docstrings and typed signatures preserved
- [x] verification commands pass

## STOP RULE
- [x] stop here and do not start next slice
