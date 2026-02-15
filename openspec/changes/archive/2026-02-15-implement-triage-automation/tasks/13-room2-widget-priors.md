# Slice 13 - Room-2 Widget Posting with 7-day Prior Lookup

## Goal
Post Room-2 widget payload and ack; include optional 7-day prior decision context.

## Scope boundaries
Included: prior lookup query and payload assembly.
Excluded: webhook callback handling.

## Files to create/modify
- `src/triage_automation/application/services/post_room2_widget_service.py`
- `src/triage_automation/infrastructure/db/prior_case_queries.py`
- `src/triage_automation/infrastructure/matrix/message_templates.py`
- `tests/unit/test_prior_case_lookup.py`
- `tests/integration/test_post_room2_widget.py`

## Tests to write FIRST (TDD)
- Lookup excludes current case and uses 7-day window.
- Payload includes required fields and optional prior fields.
- Room-2 ack stored as `bot_ack` message mapping.
- Status transitions to `WAIT_DOCTOR`.

## Implementation steps
1. Implement prior-case query helpers.
2. Build widget payload with optional prior sections.
3. Post widget+ack and persist message mappings.

## Verification commands
- `uv run pytest tests/unit/test_prior_case_lookup.py -q`
- `uv run pytest tests/integration/test_post_room2_widget.py -q`
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
