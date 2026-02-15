# Slice 05 - Ratchet Infrastructure Package

## Goal
Bring `src/triage_automation/infrastructure` into compliance with configured docstring and typing policy.

## Scope boundaries
Included: infrastructure package remediation.
Excluded: application/domain/apps.

## Files to create/modify
- `src/triage_automation/infrastructure/**/*.py`
- integration tests if adapter signatures require it

## Tests to write FIRST (TDD)
- Add integration tests only if adapter surface changes require explicit coverage.

## Implementation steps
1. Add missing public docstrings.
2. Add/repair typing in DB/HTTP/security adapters.

## Refactor steps
- Keep adapter behavior unchanged and avoid schema/business modifications.

## Verification commands
- `uv run pytest tests/integration -q`
- `uv run ruff check .`
- `uv run mypy src apps`

## Mandatory checklist
- [x] infrastructure package clean under ratchet rules
- [x] integration tests pass
- [x] no functional changes

## STOP RULE
- [x] stop here and do not start next slice
