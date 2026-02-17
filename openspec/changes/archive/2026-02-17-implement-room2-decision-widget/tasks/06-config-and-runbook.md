# Slice 06: Config and Runbook

## Goal
Document and validate runtime configuration for widget usage in manual tests.

## Scope Boundaries
- In: settings/env/docs/runbook updates.
- Out: core business logic changes.

## Files to Create/Modify
- `src/triage_automation/config/settings.py`
- `.env.example`
- `docs/manual_e2e_runbook.md`
- `tests/unit/test_settings.py`
- `tests/unit/test_manual_e2e_runbook_docs.py`

## Tests to Write FIRST
- Settings validation for widget URL and defaults.
- Runbook documentation assertions for widget steps and negative checks.

## Implementation Steps
1. Add explicit widget settings with validation aliases.
2. Update `.env.example` placeholders.
3. Update runbook with widget positive/negative scripts.

## Refactor Steps
- Keep settings naming aligned with existing env conventions.

## Verification Commands
- `uv run pytest tests/unit/test_settings.py tests/unit/test_manual_e2e_runbook_docs.py -q`
- `uv run ruff check .`
- `uv run mypy src apps`

## Mandatory Checklist
- [x] No real secrets or production URLs in example env
- [x] Widget test instructions are deterministic
- [x] Existing runtime startup commands remain valid

## STOP RULE
Stop after docs and config tests pass.
