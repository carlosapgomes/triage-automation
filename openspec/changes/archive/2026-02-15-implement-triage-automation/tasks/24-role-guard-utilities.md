# Slice 24 - Role Guard Utilities (Admin vs Reader)

## Goal
Add explicit role guard utilities for application use (`admin` full, `reader` audit-only).

## Scope boundaries
Included: domain/application role guard helpers and tests.
Excluded: new business endpoints beyond login.

## Files to create/modify
- `src/triage_automation/application/services/access_guard_service.py`
- `src/triage_automation/domain/auth/roles.py`
- `tests/unit/test_access_guard_service.py`

## Tests to write FIRST (TDD)
- Admin satisfies admin-required guard.
- Reader denied for admin-required guard.
- Reader allowed for audit-read guard.
- Unknown role rejected explicitly.

## Implementation steps
1. Implement explicit guard helpers using domain role enum.
2. Add typed authorization error hierarchy.
3. Ensure no adapter-layer business logic.

## Refactor steps
- Consolidate guard error messages for deterministic API behavior.

## Verification commands
- `uv run pytest tests/unit/test_access_guard_service.py -q`
- `uv run ruff check .`
- `uv run mypy src apps`

## Mandatory checklist
- [x] spec section referenced
- [x] failing tests written
- [x] edge cases included
- [x] minimal implementation
- [x] tests pass
- [x] lint passes
- [x] type checks pass
- [x] no triage workflow behavior change

## STOP RULE
- [x] stop here and do not start next slice
