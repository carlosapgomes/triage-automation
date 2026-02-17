# Slice 01: Contracts and Guards

## Goal
Define widget API contracts and role guard behavior without changing decision business logic.

## Scope Boundaries
- In: DTOs for widget bootstrap/submit, auth token parsing, admin role guard utility.
- Out: Route wiring, UI rendering, Room-2 posting changes.

## Files to Create/Modify
- `src/triage_automation/application/dto/widget_models.py` (new)
- `src/triage_automation/infrastructure/http/auth_guard.py` (new or extend)
- `tests/unit/test_widget_models.py` (new)
- `tests/unit/test_auth_guard_service.py` (extend/new)

## Tests to Write FIRST
- Payload validation parity with webhook decision rules.
- Guard rejects missing token, invalid token, non-admin role.
- Guard accepts valid admin token.

## Implementation Steps
1. Add DTOs with strict validation and docstrings.
2. Add/extend guard utility using existing token repository/services.
3. Keep contracts independent from adapters.

## Refactor Steps
- Consolidate shared validation helpers with existing webhook DTOs.

## Verification Commands
- `uv run pytest tests/unit/test_widget_models.py tests/unit/test_auth_guard_service.py -q`
- `uv run ruff check .`
- `uv run mypy src apps`

## Mandatory Checklist
- [ ] No state-machine or webhook route behavior changed
- [ ] Public functions include docstrings and typed signatures
- [ ] Tests fail before implementation and pass after

## STOP RULE
Stop after tests and quality gates are green for this slice; do not start route wiring.
