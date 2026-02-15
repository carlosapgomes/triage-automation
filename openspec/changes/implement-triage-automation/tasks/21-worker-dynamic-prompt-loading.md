# Slice 21 - Worker Dynamic Prompt Loading and Prompt Version Audit

## Goal
Make LLM1/LLM2 worker paths load active prompts dynamically from DB and audit which prompt version was used.

## Scope boundaries
Included: worker LLM service wiring and audit payload enrichment.
Excluded: prompt editing APIs or UI.

## Files to create/modify
- `src/triage_automation/application/services/llm1_service.py`
- `src/triage_automation/application/services/llm2_service.py`
- `src/triage_automation/application/services/process_pdf_case_service.py`
- `tests/integration/test_llm_prompt_loading_runtime.py`
- `tests/unit/test_llm_prompt_version_audit_payload.py`

## Tests to write FIRST (TDD)
- LLM1 loads active prompt by configured prompt name.
- LLM2 loads active prompt by configured prompt name.
- If active prompt missing, job fails explicitly and is retriable.
- Audit event payload includes prompt name and version used.
- Default configured prompt names resolve to seeded rows: `llm1_system`, `llm1_user`, `llm2_system`, `llm2_user`.

## Implementation steps
1. Inject prompt template service into LLM services.
2. Replace static prompt source with active DB prompt retrieval.
3. Append prompt version metadata in audit events.
4. Wire default prompt-name config to seeded names.

## Refactor steps
- Move prompt loading into shared helper to avoid duplication.

## Verification commands
- `uv run pytest tests/unit/test_llm_prompt_version_audit_payload.py -q`
- `uv run pytest tests/integration/test_llm_prompt_loading_runtime.py -q`
- `uv run ruff check .`
- `uv run mypy src apps`

## Mandatory checklist
- [ ] spec section referenced
- [ ] failing tests written
- [ ] edge cases included
- [ ] minimal implementation
- [ ] tests pass
- [ ] lint passes
- [ ] type checks pass
- [ ] no triage workflow behavior change

## STOP RULE
- [ ] stop here and do not start next slice
