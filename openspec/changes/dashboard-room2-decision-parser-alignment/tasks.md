# Tasks

## 1. Dashboard Decision Extraction Alignment

- [x] 1.1 Adicionar/ajustar teste(s) de dashboard para falhar (red) quando houver citação com decisão antiga (`aceitar`) e decisão final (`negar`) no mesmo `room2_doctor_reply`.
- [x] 1.2 Implementar extração de decisão no `dashboard_router` reutilizando `parse_doctor_decision_reply`, mapeando para `ACEITAR`/`NEGAR` e fallback `INDEFINIDA`.
- [x] 1.3 Executar validações do slice (`uv run pytest` alvo, `uv run ruff check` paths alterados, `uv run mypy` paths alterados e `markdownlint-cli2` nos artefatos OpenSpec alterados) e registrar evidências.

## Notes

- TDD (red -> green):
  - `uv run pytest tests/integration/test_dashboard_pages.py -k canonical_parser_for_quoted_mobile_reply -q` (falhou em red antes da implementação, esperando `NEGAR` e recebendo resumo incorreto).
  - `uv run pytest tests/integration/test_dashboard_pages.py -k canonical_parser_for_quoted_mobile_reply -q` (passou após implementação).
- Validações finais executadas com sucesso:
  - `uv run pytest tests/integration/test_dashboard_pages.py -q`
  - `uv run ruff check src/triage_automation/infrastructure/http/dashboard_router.py tests/integration/test_dashboard_pages.py`
  - `uv run mypy src/triage_automation/infrastructure/http/dashboard_router.py tests/integration/test_dashboard_pages.py`
  - `markdownlint-cli2 "openspec/changes/dashboard-room2-decision-parser-alignment/proposal.md" "openspec/changes/dashboard-room2-decision-parser-alignment/design.md" "openspec/changes/dashboard-room2-decision-parser-alignment/specs/**/*.md" "openspec/changes/dashboard-room2-decision-parser-alignment/tasks.md"`
