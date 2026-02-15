# Slice 18 - Cleanup Execution, Retry Exhaustion, Recovery, and E2E

## Goal
Complete cleanup redaction job, max-retry failure finalization, and restart recovery with end-to-end verification.

## Scope boundaries
Included: `execute_cleanup`, dead-letter/failure finalization, recovery scan, e2e tests.
Excluded: new product scope.

## Files to create/modify
- `src/triage_automation/application/services/execute_cleanup_service.py`
- `src/triage_automation/application/services/job_failure_service.py`
- `src/triage_automation/application/services/recovery_service.py`
- `tests/integration/test_execute_cleanup.py`
- `tests/integration/test_max_retries_failure_path.py`
- `tests/e2e/test_full_case_flow.py`

## Tests to write FIRST (TDD)
- Cleanup redacts all `case_messages` and writes audit.
- Cleanup sets `cleanup_completed_at` and `CLEANED`.
- Max retries exceeded marks job `dead`, case `FAILED`, enqueues failure final reply.
- Restart recovery resumes non-terminal work without duplicate side effects.
- E2E covers happy path and triage-deny path.

## Implementation steps
1. Implement `execute_cleanup` handler.
2. Implement retry exhaustion sequence per spec order.
3. Implement recovery scan and final integration tests.

## Verification commands
- `uv run pytest tests/integration/test_execute_cleanup.py -q`
- `uv run pytest tests/integration/test_max_retries_failure_path.py -q`
- `uv run pytest tests/e2e/test_full_case_flow.py -q`
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
