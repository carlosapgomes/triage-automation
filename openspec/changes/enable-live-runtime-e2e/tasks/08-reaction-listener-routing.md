# Slice 08 - Reaction Listener Routing

## Goal
Wire reaction events from runtime Matrix listener into existing reaction service.

## Scope boundaries
Included: reaction event normalization and routing.
Excluded: Room-3 reply parsing flow.

## Files to create/modify
- `apps/bot_matrix/main.py`
- reaction event mapping modules under `src/triage_automation/infrastructure/matrix/`
- integration tests for reaction routing

## Tests to write FIRST (TDD)
- Add failing integration test for Room-1 thumbs-up cleanup trigger path via listener.
- Add failing integration test for Room-2/3 audit-only thumbs behavior via listener.

## Implementation steps
1. Normalize Matrix reaction events to existing `ReactionEvent` model.
2. Route to `ReactionService` with room-aware IDs from settings.
3. Preserve first-thumbs cleanup CAS semantics.

## Refactor steps
- Keep reaction mapping isolated from transport-specific event shapes.

## Verification commands
- `uv run pytest tests/integration/test_reaction_cleanup_trigger.py -q`
- `uv run ruff check .`
- `uv run mypy src apps`

## Mandatory checklist
- [x] failing tests written first
- [x] Room-1 cleanup trigger semantics remain unchanged
- [x] Room-2/3 thumbs remain audit-only
- [x] public docstrings and typed signatures preserved
- [x] verification commands pass

## STOP RULE
- [x] stop here and do not start next slice
