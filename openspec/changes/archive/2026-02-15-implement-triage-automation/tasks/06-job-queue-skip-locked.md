# Slice 06 - Postgres Job Queue with SKIP LOCKED

## Goal
Implement queue primitives with claim, retry scheduling, and dead-letter behavior.

## Scope boundaries
Included: enqueue/claim/complete/fail/retry/dead operations.
Excluded: concrete job handlers.

## Files to create/modify
- `src/triage_automation/application/ports/job_queue_port.py`
- `src/triage_automation/infrastructure/db/job_queue_repository.py`
- `src/triage_automation/application/services/backoff.py`
- `tests/integration/test_job_queue_repository.py`

## Tests to write FIRST (TDD)
- Enqueue creates `queued` jobs.
- Concurrent workers claim distinct jobs via `FOR UPDATE SKIP LOCKED`.
- `run_after` scheduling respected.
- Retry updates attempts and run_after.
- Max attempts can move job to `dead`.

## Implementation steps
1. Implement queue repository SQL paths.
2. Implement deterministic exponential backoff with jitter bounds.
3. Add integration tests for concurrency semantics.

## Verification commands
- `uv run pytest tests/integration/test_job_queue_repository.py -q`
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
