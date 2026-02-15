# Slice 22 - Users, Roles, and Auth Events Schema and Repositories

## Goal
Add `users` and `auth_events` schema plus repositories for user retrieval and auth auditing.

## Scope boundaries
Included: migrations, metadata, repository ports/adapters, FK finalize step for `prompt_templates.updated_by_user_id`, and opaque-token persistence schema.
Excluded: password hashing and login endpoint behavior.

## Files to create/modify
- `alembic/versions/0003_users_auth_events.py`
- `src/triage_automation/infrastructure/db/metadata.py`
- `src/triage_automation/domain/auth/roles.py`
- `src/triage_automation/application/ports/user_repository_port.py`
- `src/triage_automation/application/ports/auth_event_repository_port.py`
- `src/triage_automation/application/ports/auth_token_repository_port.py`
- `src/triage_automation/infrastructure/db/user_repository.py`
- `src/triage_automation/infrastructure/db/auth_event_repository.py`
- `src/triage_automation/infrastructure/db/auth_token_repository.py`
- `tests/integration/test_migration_users_auth_events.py`
- `tests/integration/test_user_and_auth_event_repositories.py`

## Tests to write FIRST (TDD)
- `users` schema has role check constraint and unique email.
- `auth_events` schema and indexes exist.
- `auth_tokens` schema exists with unique `token_hash` and FK to `users`.
- `prompt_templates.updated_by_user_id` FK to `users(id)` exists after migration.
- Role enum values are exactly `admin` and `reader`.
- Repositories fetch active user by email, append auth events, and persist token records.

## Implementation steps
1. Add migration for `users` and `auth_events`.
2. Add migration for `auth_tokens`.
3. Alter `prompt_templates.updated_by_user_id` to add FK to `users(id)`.
4. Add domain role enum.
5. Add repository interfaces and DB adapters.

## Refactor steps
- Reuse shared timestamp and UUID helper patterns.

## Verification commands
- `uv run pytest tests/integration/test_migration_users_auth_events.py -q`
- `uv run pytest tests/integration/test_user_and_auth_event_repositories.py -q`
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
