# Slice 12 - LLM2 Integration and EDA Policy Cross-Check

## Goal
Call LLM2, validate schema v1.1, apply hard policy consistency rules, store suggestion artifact.

## Scope boundaries
Included: policy cross-check and contradiction audit events.
Excluded: Room-2 posting.

## Files to create/modify
- `src/triage_automation/application/dto/llm2_models.py`
- `src/triage_automation/domain/policy/eda_policy.py`
- `src/triage_automation/application/services/llm2_service.py`
- `src/triage_automation/application/services/process_pdf_case_service.py`
- `tests/unit/test_eda_policy_crosscheck.py`
- `tests/integration/test_process_pdf_case_llm2.py`

## Tests to write FIRST (TDD)
- Excluded request forces deny.
- Foreign body sets `labs_ok` and `ecg_ok` to `not_required`.
- Missing required labs/ecg forces deny-aligned output.
- Contradictions emit `LLM_CONTRADICTION_DETECTED` audit.

## Implementation steps
1. Add Pydantic model for LLM2 schema.
2. Add pure policy reconciliation module.
3. Persist `suggested_action_json` and enqueue `post_room2_widget`.

## Verification commands
- `uv run pytest tests/unit/test_eda_policy_crosscheck.py -q`
- `uv run pytest tests/integration/test_process_pdf_case_llm2.py -q`
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
