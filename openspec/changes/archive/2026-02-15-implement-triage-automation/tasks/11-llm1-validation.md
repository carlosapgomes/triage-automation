# Slice 11 - LLM1 Integration and Contract Validation

## Goal
Call LLM1, validate schema v1.1, persist structured data and summary.

## Scope boundaries
Included: prompt wrapper, JSON parsing, schema validation, persistence.
Excluded: LLM2 and policy cross-check logic.

## Files to create/modify
- `src/triage_automation/application/dto/llm1_models.py`
- `src/triage_automation/infrastructure/llm/llm_client.py`
- `src/triage_automation/application/services/llm1_service.py`
- `src/triage_automation/application/services/process_pdf_case_service.py`
- `tests/unit/test_llm1_validation.py`
- `tests/integration/test_process_pdf_case_llm1.py`

## Tests to write FIRST (TDD)
- Valid LLM1 response persists.
- Invalid schema is retriable `llm1` failure.
- Non-JSON response rejected.
- `agency_record_number` is injected exactly.

## Implementation steps
1. Add Pydantic model for LLM1 schema.
2. Add LLM call adapter and prompt templates.
3. Persist `structured_data_json` and `summary_text`.

## Verification commands
- `uv run pytest tests/unit/test_llm1_validation.py -q`
- `uv run pytest tests/integration/test_process_pdf_case_llm1.py -q`
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
