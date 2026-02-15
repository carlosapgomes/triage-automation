# Slice 07 - Test Suite Policy Alignment

## Goal
Finalize explicit policy for tests: enforce same standards or scoped exclusions with rationale.

## Scope boundaries
Included: `tests/**` policy decision and any required remediation.
Excluded: production business logic changes.

## Files to create/modify
- `ruff.toml`
- `mypy.ini`
- `tests/**/*.py`

## Tests to write FIRST (TDD)
- N/A (policy/remediation in tests)

## Implementation steps
1. Decide and encode test policy scope.
2. Remediate violations required by chosen policy.

## Refactor steps
- Keep tests readable; avoid low-value boilerplate.

## Verification commands
- `uv run pytest -q`
- `uv run ruff check .`
- `uv run mypy src apps`

## Mandatory checklist
- [x] test policy encoded in tooling
- [x] full test suite passes
- [x] checks pass

## STOP RULE
- [x] stop here and do not start next slice
