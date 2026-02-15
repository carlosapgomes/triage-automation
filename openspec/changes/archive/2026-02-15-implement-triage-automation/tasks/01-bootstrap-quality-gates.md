# Slice 01 - Project Bootstrap and Quality Gates

## Goal
Create a runnable Python monorepo skeleton with deterministic tooling (`uv`, `pytest`, `ruff`, `mypy`).

## Scope boundaries
Included: repository scaffolding and baseline test/lint/typecheck setup.
Excluded: business logic, DB schema, Matrix/webhook behavior.

## Files to create/modify
- `pyproject.toml`
- `uv.lock`
- `README.md`
- `.python-version`
- `ruff.toml`
- `mypy.ini`
- `pytest.ini`
- `apps/bot_api/__init__.py`
- `apps/bot_matrix/__init__.py`
- `apps/worker/__init__.py`
- `src/triage_automation/__init__.py`
- `tests/unit/test_project_imports.py`

## Tests to write FIRST (TDD)
- Imports for package/apps succeed.
- Imports do not require runtime env vars.

## Implementation steps
1. Add tool configuration files.
2. Create minimal package entry modules.
3. Add unit test for import sanity.

## Verification commands
- `uv run pytest -q`
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
