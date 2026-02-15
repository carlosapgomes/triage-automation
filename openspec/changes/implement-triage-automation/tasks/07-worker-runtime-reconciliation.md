# Slice 07 - Worker Runtime and Boot Reconciliation

## Goal
Build worker loop with startup reconciliation that resets stale `running` jobs to `queued`.

## Scope boundaries
Included: poll-dispatch loop, boot reconciliation, graceful shutdown.
Excluded: job-type business logic.

## Files to create/modify
- `apps/worker/main.py`
- `src/triage_automation/application/services/worker_runtime.py`
- `src/triage_automation/infrastructure/db/worker_bootstrap.py`
- `tests/unit/test_worker_runtime.py`
- `tests/integration/test_worker_boot_reconciliation.py`

## Tests to write FIRST (TDD)
- Startup reset keeps attempts unchanged.
- Empty queue sleeps without busy-looping.
- Unknown job type is marked failed deterministically.

## Implementation steps
1. Add bootstrap reconciliation query.
2. Implement async polling loop.
3. Add dispatch registry and cancellation-safe loop exits.

## Verification commands
- `uv run pytest tests/unit/test_worker_runtime.py -q`
- `uv run pytest tests/integration/test_worker_boot_reconciliation.py -q`
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
