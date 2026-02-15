# Slice 04 - Domain Status and Transition Guards

## Goal
Implement deterministic state transition guards for all case statuses.

## Scope boundaries
Included: status constants and allowed transition map.
Excluded: adapters, DB IO, business side effects.

## Files to create/modify
- `src/triage_automation/domain/case_status.py`
- `src/triage_automation/domain/transitions.py`
- `tests/unit/test_case_transitions.py`

## Tests to write FIRST (TDD)
- Allowed transitions pass.
- Invalid transitions raise domain error.
- Final reply transitions directly to `WAIT_R1_CLEANUP_THUMBS`.

## Implementation steps
1. Define explicit status model.
2. Add transition map and assertion helper.
3. Add deterministic error messages.

## Verification commands
- `uv run pytest tests/unit/test_case_transitions.py -q`
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
