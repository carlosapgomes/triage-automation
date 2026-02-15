# Slice 09 - PDF Download and Text Extraction

## Goal
Implement first half of `process_pdf_case`: MXC download and raw text extraction.

## Scope boundaries
Included: status updates, extraction errors, audit hooks.
Excluded: record-number extraction and LLM calls.

## Files to create/modify
- `src/triage_automation/application/services/process_pdf_case_service.py`
- `src/triage_automation/infrastructure/matrix/mxc_downloader.py`
- `src/triage_automation/infrastructure/pdf/text_extractor.py`
- `tests/unit/test_text_extractor.py`
- `tests/integration/test_process_pdf_case_download_extract.py`

## Tests to write FIRST (TDD)
- Successful extraction from valid PDF bytes.
- Download failure mapped as retriable `download` cause.
- Extraction failure mapped as retriable `extract` cause.
- Empty extracted text treated as failure.

## Implementation steps
1. Add downloader and extractor adapters.
2. Wire handler steps with audit events.
3. Persist extraction artifacts and status transitions.

## Verification commands
- `uv run pytest tests/unit/test_text_extractor.py -q`
- `uv run pytest tests/integration/test_process_pdf_case_download_extract.py -q`
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
