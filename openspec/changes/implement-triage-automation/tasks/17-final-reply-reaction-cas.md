# Slice 17 - Room-1 Final Replies and Cleanup CAS Trigger

## Goal
Implement final Room-1 reply jobs and first-thumbs-only cleanup trigger via CAS.

## Scope boundaries
Included: final message variants, reaction routing, audit-only thumbs in Room-2/3.
Excluded: redaction execution.

## Files to create/modify
- `src/triage_automation/application/services/post_room1_final_service.py`
- `src/triage_automation/application/services/reaction_service.py`
- `src/triage_automation/infrastructure/db/case_repository.py`
- `tests/integration/test_room1_final_reply_jobs.py`
- `tests/integration/test_reaction_cleanup_trigger.py`

## Tests to write FIRST (TDD)
- Final replies match exact templates and are reply-to origin PDF.
- Posting final reply sets `room1_final_reply_event_id` and `WAIT_R1_CLEANUP_THUMBS`.
- Concurrent thumbs-up race triggers cleanup once.
- Room-2/3 ack thumbs are audit-only and do not enqueue cleanup.

## Implementation steps
1. Implement final reply job handlers.
2. Add reaction router by room and target event kind.
3. Implement CAS update on `cleanup_triggered_at IS NULL`.

## Verification commands
- `uv run pytest tests/integration/test_room1_final_reply_jobs.py -q`
- `uv run pytest tests/integration/test_reaction_cleanup_trigger.py -q`
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
