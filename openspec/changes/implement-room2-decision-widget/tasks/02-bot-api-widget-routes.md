# Slice 02: Bot API Widget Routes

## Goal
Expose widget bootstrap and submit endpoints in `bot-api`, reusing existing decision service path.

## Scope Boundaries
- In: route handlers, request/response mapping, auth guard enforcement.
- Out: Room-2 message formatting and frontend asset implementation.

## Files to Create/Modify
- `apps/bot_api/main.py`
- `src/triage_automation/infrastructure/http/widget_router.py` (new)
- `tests/integration/test_widget_routes.py` (new)

## Tests to Write FIRST
- Bootstrap endpoint returns case context for authenticated admin.
- Submit endpoint maps to existing decision outcome semantics (`applied`, wrong state, not found).
- Unauthorized and reader-role submissions are rejected.

## Implementation Steps
1. Add dedicated router and inject dependencies.
2. Wire router in app factory preserving existing routes.
3. Reuse `HandleDoctorDecisionService` to avoid rule duplication.

## Refactor Steps
- Extract shared error/outcome mapping helper for callback + widget submit.

## Verification Commands
- `uv run pytest tests/integration/test_widget_routes.py -q`
- `uv run ruff check .`
- `uv run mypy src apps`

## Mandatory Checklist
- [ ] Existing `/callbacks/triage-decision` remains unchanged
- [ ] Existing `/auth/login` remains unchanged
- [ ] No business logic moved into adapter layer

## STOP RULE
Stop once widget routes are tested and passing; do not change Room-2 posting yet.
