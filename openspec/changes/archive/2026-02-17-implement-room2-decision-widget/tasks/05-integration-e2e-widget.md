# Slice 05: Widget Integration E2E

## Goal
Prove widget flow end-to-end from Room-2 posting to case decision/job enqueue outcomes.

## Scope Boundaries
- In: integration tests for accept/deny and auth negative paths.
- Out: production deployment automation.

## Files to Create/Modify
- `tests/integration/test_room2_widget_flow.py` (new)
- `tests/e2e/test_full_case_flow.py` (targeted updates if needed)

## Tests to Write FIRST
- Accept via widget reaches `DOCTOR_ACCEPTED` path and enqueues `post_room3_request`.
- Deny via widget reaches `DOCTOR_DENIED` path and enqueues final denial job.
- Reader/unauthenticated submit produces no mutation.

## Implementation Steps
1. Build fixtures for token + role contexts.
2. Exercise widget routes with real repositories.
3. Assert audit event parity with existing callback path.

## Refactor Steps
- Reuse integration helpers between callback and widget tests.

## Verification Commands
- `uv run pytest tests/integration/test_room2_widget_flow.py -q`
- `uv run ruff check .`
- `uv run mypy src apps`

## Mandatory Checklist
- [x] Existing callback integration tests still pass
- [x] Widget path preserves idempotency/race handling
- [x] Audit trail contains actor identity and outcome

## STOP RULE
Stop after integration coverage is green; do not start docs/config updates in this slice.
