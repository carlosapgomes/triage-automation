# Slice 08 - CI and Local Gate Enforcement

## Goal
Ensure CI/local workflows enforce ratcheted docstring/type standards on every change.

## Scope boundaries
Included: CI workflow and contributor command baseline.
Excluded: new product features.

## Files to create/modify
- CI workflow files (if present)
- `README.md` and/or contributor docs

## Tests to write FIRST (TDD)
- N/A (workflow/config slice)

## Implementation steps
1. Wire required checks into CI.
2. Document local commands matching CI gates.

## Refactor steps
- Keep CI runtime reasonable and deterministic.

## Verification commands
- CI dry-run/syntax validation if available
- `uv run ruff check .`
- `uv run mypy src apps`

## Mandatory checklist
- [x] CI enforces ratchet checks
- [x] local workflow documented
- [x] checks pass locally

## STOP RULE
- [x] stop here and do not start next slice
