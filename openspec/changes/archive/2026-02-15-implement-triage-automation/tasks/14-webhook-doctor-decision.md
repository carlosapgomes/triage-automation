# Slice 14 - HMAC Webhook and Doctor Decision Handling

## Goal
Implement authenticated callback endpoint and decision persistence with next-job enqueue.

## Scope boundaries
Included: HMAC validation, request schema, support_flag contract enforcement.
Excluded: Room-3 and Room-1 posting logic.

## Files to create/modify
- `apps/bot_api/main.py`
- `src/triage_automation/infrastructure/http/hmac_auth.py`
- `src/triage_automation/application/dto/webhook_models.py`
- `src/triage_automation/application/services/handle_doctor_decision_service.py`
- `tests/unit/test_hmac_auth.py`
- `tests/integration/test_triage_decision_webhook.py`

## Tests to write FIRST (TDD)
- Valid signature accepted, invalid rejected.
- `decision=deny` requires `support_flag=none`.
- `decision=accept` allows `none|anesthesist|anesthesist_icu` only.
- Correct next job enqueued by decision branch.

## Implementation steps
1. Add raw-body HMAC verifier.
2. Validate payload via Pydantic.
3. Persist decision and enqueue downstream job.

## Verification commands
- `uv run pytest tests/unit/test_hmac_auth.py -q`
- `uv run pytest tests/integration/test_triage_decision_webhook.py -q`
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
