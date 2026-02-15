# Slice 05 - Worker Runtime Integration Coverage

## Goal
Strengthen runtime integration coverage for dispatch, retry/dead-letter, and boot recovery behavior.

## Scope boundaries
Included: tests and minimal wiring changes needed to satisfy failing runtime coverage.
Excluded: unrelated feature additions.

## Files to create/modify
- `tests/integration/` worker-runtime focused suites
- minimal runtime composition files if tests reveal wiring gaps

## Tests to write FIRST (TDD)
- Add failing integration test for boot reconciliation before polling.
- Add failing integration test for retry scheduling and dead-letter boundaries in live wiring.

## Implementation steps
1. Add integration fixtures for runtime worker composition.
2. Address only defects required for green tests.
3. Keep runtime semantics aligned with existing service-level behavior.

## Refactor steps
- Deduplicate runtime test fixtures if repeated setup becomes large.

## Verification commands
- `uv run pytest tests/integration/test_worker_boot_reconciliation.py tests/integration/test_max_retries_failure_path.py -q`
- `uv run ruff check .`
- `uv run mypy src apps`

## Mandatory checklist
- [x] failing tests written first
- [x] runtime recovery and retry/dead-letter paths are covered
- [x] no behavior drift from existing contracts
- [x] public docstrings and typed signatures preserved
- [x] verification commands pass

## STOP RULE
- [x] stop here and do not start next slice
