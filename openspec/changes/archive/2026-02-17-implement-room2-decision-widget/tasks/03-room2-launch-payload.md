# Slice 03: Room-2 Launch Payload

## Goal
Extend Room-2 widget post to include widget launch context while preserving ack/audit/state behavior.

## Scope Boundaries
- In: post service/template updates for widget launch URL/context.
- Out: frontend rendering internals and scheduler/final-reply paths.

## Files to Create/Modify
- `src/triage_automation/application/services/post_room2_widget_service.py`
- `src/triage_automation/infrastructure/matrix/message_templates.py`
- `tests/integration/test_post_room2_widget.py`

## Tests to Write FIRST
- Posted Room-2 content contains widget launch contract fields.
- Ack message is still posted and tracked as `bot_ack`.
- Status transition still ends at `WAIT_DOCTOR`.

## Implementation Steps
1. Add widget URL/context builder in service.
2. Update message template text in pt-BR with deterministic format.
3. Keep audit event types unchanged unless new explicit events are needed.

## Refactor Steps
- Centralize payload-to-message rendering helpers.

## Verification Commands
- `uv run pytest tests/integration/test_post_room2_widget.py -q`
- `uv run ruff check .`
- `uv run mypy src apps`

## Mandatory Checklist
- [x] Room-2 ack reaction semantics unchanged (audit-only)
- [x] No state-machine transition changes
- [x] Prior-case payload semantics preserved

## STOP RULE
Stop after Room-2 posting parity is validated; do not implement static widget UI yet.
