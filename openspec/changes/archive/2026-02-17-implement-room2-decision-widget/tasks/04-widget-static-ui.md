# Slice 04: Widget Static UI

## Goal
Implement a minimal pt-BR widget UI for login, context display, and decision submission.

## Scope Boundaries
- In: static HTML/CSS/JS assets, API client calls, client-side validation.
- Out: new business rules, triage state logic, Room-3 behavior.

## Files to Create/Modify
- `apps/bot_api/static/widget/room2/index.html` (new)
- `apps/bot_api/static/widget/room2/app.js` (new)
- `apps/bot_api/static/widget/room2/styles.css` (new)
- `tests/unit/test_widget_static_contract.py` (new)

## Tests to Write FIRST
- Form field and payload contract checks.
- Decision controls enforce allowed `support_flag` values.
- UI handles API errors deterministically.

## Implementation Steps
1. Add login form using `/auth/login`.
2. Load widget context from bootstrap endpoint.
3. Submit decisions via widget submit endpoint.

## Refactor Steps
- Extract shared API client helper for auth and submit.

## Verification Commands
- `uv run pytest tests/unit/test_widget_static_contract.py -q`
- `uv run ruff check .`
- `uv run mypy src apps`

## Mandatory Checklist
- [x] UI text is pt-BR
- [x] No secret (HMAC) exposed to frontend
- [x] Payload matches backend DTO contract

## STOP RULE
Stop after static widget can perform one successful submit in tests.
