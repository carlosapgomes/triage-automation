# Slice 03 - Initial Postgres Schema and Migrations

## Goal
Create schema/migrations for `cases`, `case_events`, `case_messages`, and `jobs` exactly per handoff.

## Scope boundaries
Included: tables, constraints, indexes, defaults.
Excluded: repository/service logic.

## Files to create/modify
- `alembic.ini`
- `alembic/env.py`
- `alembic/versions/0001_initial_schema.py`
- `src/triage_automation/infrastructure/db/metadata.py`
- `tests/integration/test_migration_initial_schema.py`

## Tests to write FIRST (TDD)
- Tables exist.
- Required unique constraints/indexes exist.
- `jobs.status` default is `queued`.

## Implementation steps
1. Define SQLAlchemy metadata.
2. Author initial Alembic migration.
3. Add migration verification test.

## Verification commands
- `uv run pytest tests/integration/test_migration_initial_schema.py -q`
- `uv run ruff check .`
- `uv run mypy src apps`

## Checklist
- [x] spec section referenced
- [x] failing tests written
- [x] edge cases included
- [x] minimal implementation complete
- [x] tests pass
- [x] lint passes
- [x] type checks pass
- [x] stop and do not start next slice
