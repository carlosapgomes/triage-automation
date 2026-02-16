# Slice 12 - Manual E2E Runbook and Smoke Workflow

## Goal
Document and validate operational runbook for local runtime and Cloudflare-tunneled webhook testing.

## Scope boundaries
Included: docs, smoke commands, and deterministic validation steps.
Excluded: deployment platform redesign.

## Files to create/modify
- `README.md`
- `docs/setup.md`
- new runtime operations guide under `docs/`
- optional helper scripts for smoke checks

## Tests to write FIRST (TDD)
- Add failing doc/smoke validation checks where applicable (scripted smoke commands).
- Add failing integration test(s) only if needed to back operational claims.

## Implementation steps
1. Add step-by-step local smoke checks (direct webhook call + signature validation).
2. Add Cloudflare tunnel verification flow and expected outcomes.
3. Ensure commands reflect actual runtime entrypoints.

## Refactor steps
- Keep operational docs concise, deterministic, and synchronized with compose/uv commands.

## Verification commands
- `uv run pytest -q`
- `uv run ruff check .`
- `uv run mypy src apps`

## Mandatory checklist
- [x] failing validations/tests written first where applicable
- [x] runbook covers local and tunneled webhook checks
- [x] runtime commands are parity-checked (`uv` and compose)
- [x] public docstrings and typed signatures preserved in touched code
- [x] verification commands pass

## STOP RULE
- [x] stop here and do not start next slice
