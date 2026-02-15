# Slice 19 - Prompt Templates Schema and Constraints

## Goal
Add `prompt_templates` DB schema with strict versioning and single-active-version rule per prompt name.

## Scope boundaries
Included: migration + metadata + tests for constraints/indexes.
Excluded: repositories, worker integration, and FK creation to `users` (added in Slice 22).

## Files to create/modify
- `alembic/versions/0002_prompt_templates.py`
- `src/triage_automation/infrastructure/db/metadata.py`
- `tests/integration/test_migration_prompt_templates.py`

## Tests to write FIRST (TDD)
- Table exists with required columns.
- `UNIQUE(name, version)` enforced.
- Partial unique index enforces single active row per name.
- `version > 0` check enforced.
- `updated_by_user_id` exists as nullable UUID column (no FK yet).
- Seeded default active prompts exist: `llm1_system`, `llm1_user`, `llm2_system`, `llm2_user` at `version=1`.

## Implementation steps
1. Add migration for `prompt_templates`.
2. Seed default active prompt rows in migration.
3. Add metadata model definitions.
4. Add integration tests asserting constraints/indexes and seed presence.

## Refactor steps
- Extract reusable migration assertion helpers.

## Verification commands
- `uv run pytest tests/integration/test_migration_prompt_templates.py -q`
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
