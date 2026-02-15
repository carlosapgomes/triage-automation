# Slice 10 - Record Number Extraction and Stripping

## Goal
Extract most frequent 5-digit agency record number and strip it from text before LLM.

## Scope boundaries
Included: regex tokenization, frequency selection, text stripping.
Excluded: prior lookup and Room-2 payload.

## Files to create/modify
- `src/triage_automation/domain/record_number.py`
- `src/triage_automation/application/services/process_pdf_case_service.py`
- `tests/unit/test_record_number_extraction.py`
- `tests/integration/test_process_pdf_case_record_strip.py`

## Tests to write FIRST (TDD)
- Most frequent token chosen.
- All occurrences of selected token removed.
- Tie-break rule deterministic.
- No valid 5-digit token -> retriable `record_extract` failure.

## Implementation steps
1. Implement pure extraction function.
2. Persist `agency_record_number` and extraction timestamp.
3. Store cleaned text for downstream LLM steps.

## Verification commands
- `uv run pytest tests/unit/test_record_number_extraction.py -q`
- `uv run pytest tests/integration/test_process_pdf_case_record_strip.py -q`
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
