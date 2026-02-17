# Slice 07: Closeout and Quality Gates

## Goal
Finalize change with full quality verification and implementation readiness.

## Scope Boundaries
- In: full test/lint/type pass and final checklist.
- Out: new functional changes.

## Files to Create/Modify
- `openspec/changes/implement-room2-decision-widget/tasks.md` (mark done progressively)
- optional closeout notes if project policy requires

## Tests to Write FIRST
- N/A (verification slice)

## Implementation Steps
1. Run complete verification suite.
2. Confirm no pending TODOs in widget-related files.
3. Ensure all slice tasks are marked completed only after evidence.

## Refactor Steps
- Cleanup dead helpers/imports introduced during widget slices.

## Verification Commands
- `uv run pytest -q`
- `uv run ruff check .`
- `uv run mypy src apps`

## Mandatory Checklist
- [x] Behavior parity maintained for callback and state machine
- [x] Docstrings/types comply with ratchet scope
- [x] Manual runbook updated and reviewed

## STOP RULE
Stop and request implementation approval once all gates pass.
