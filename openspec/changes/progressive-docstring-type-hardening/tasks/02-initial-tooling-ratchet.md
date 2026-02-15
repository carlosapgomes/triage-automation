# Slice 02 - Initial Tooling Ratchet

## Goal
Introduce non-breaking ratchet config for first package group.

## Scope boundaries
Included: incremental `ruff`/`mypy` rule activation for targeted scope.
Excluded: multi-package remediation.

## Files to create/modify
- `ruff.toml`
- `mypy.ini`

## Tests to write FIRST (TDD)
- N/A (config-driven)

## Implementation steps
1. Enable docstring/type rules for selected package.
2. Keep global scope relaxed enough to avoid unrelated failures.

## Refactor steps
- Minimize ignore list; document each ignore rationale.

## Verification commands
- `uv run ruff check .`
- `uv run mypy src apps`

## Mandatory checklist
- [x] targeted rules enabled
- [x] unrelated packages unaffected
- [x] checks pass

## STOP RULE
- [x] stop here and do not start next slice
