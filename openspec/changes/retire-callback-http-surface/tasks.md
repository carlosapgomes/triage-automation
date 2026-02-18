# Tasks

## 1. Remove HTTP Decision Surface

- [x] 1.1 Remover a rota `POST /callbacks/triage-decision` de `apps/bot_api/main.py` e limpar imports/dependências de callback HMAC vinculadas a decisão médica.
- [x] 1.2 Remover o `build_widget_router` do wiring do `bot-api` e eliminar dependências exclusivas do fluxo widget HTTP de decisão.
- [x] 1.3 Remover endpoints e assets estáticos legados de widget Room-2 (`/widget/room2*`) que não fazem mais parte da superfície operacional.

## 2. Align Runtime Documentation

- [x] 2.1 Atualizar `docs/runtime-smoke.md` para remover validações de callback/túnel e manter apenas fluxo Matrix structured reply.
- [x] 2.2 Atualizar `docs/setup.md`, `docs/architecture.md` e `README.md` para refletir runtime Matrix-only sem fallback HTTP de decisão.
- [ ] 2.3 Revisar variáveis/configs documentadas e remover referências legadas de callback/widget público para decisão médica.

## 3. Update Tests and Contracts

- [ ] 3.1 Ajustar/criar testes de integração do `bot-api` validando ausência de endpoints legados (`/callbacks/triage-decision` e `/widget/room2*`).
- [ ] 3.2 Atualizar testes que dependiam do caminho callback/widget para validar o comportamento equivalente no fluxo Matrix-only.
- [ ] 3.3 Garantir que os testes do fluxo Room-2 structured reply permaneçam verdes sem regressão de estado/idempotência.

## 4. Verify and Closeout

- [ ] 4.1 Executar quality gates do slice (`uv run pytest <targeted>`, `uv run ruff check <changed-paths>`, `uv run mypy <changed-paths>`).
- [ ] 4.2 Executar validação de Markdown (`markdownlint-cli2 "<changed-markdown-paths>"`) nos artefatos alterados.
- [ ] 4.3 Validar bootstrap do runtime (`bot-api` + `bot-matrix` + `worker`) com checklist Matrix-only e registrar notas de rollback/impacto no fechamento da change.
