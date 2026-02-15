# Slice 02 - Runtime Settings Expansion

## Goal
Add runtime settings required for live Matrix and LLM execution, with deterministic defaults for dev.

## Scope boundaries
Included: strongly typed settings fields and env template updates.
Excluded: implementing runtime behavior that consumes these settings.

## Files to create/modify
- `src/triage_automation/config/settings.py`
- `.env.example`
- settings-focused tests under `tests/unit/` or `tests/integration/`

## Tests to write FIRST (TDD)
- Add failing tests for required/optional runtime env fields.
- Add failing tests validating deterministic defaults where designed.

## Implementation steps
1. Add typed settings fields for Matrix bot auth/runtime polling and LLM runtime mode.
2. Update `.env.example` with sanitized placeholder values.
3. Keep backward-compatible loading for existing required keys.

## Refactor steps
- Group settings by concern with concise comments if needed.

## Verification commands
- `uv run pytest tests/unit -q`
- `uv run ruff check .`
- `uv run mypy src apps`

## Mandatory checklist
- [x] failing tests written first
- [x] new runtime settings are typed and documented
- [x] `.env.example` remains sanitized
- [x] public docstrings and typed signatures preserved
- [x] verification commands pass

## STOP RULE
- [x] stop here and do not start next slice
