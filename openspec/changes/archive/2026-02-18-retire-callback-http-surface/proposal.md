# Proposal

## Why

A rota HTTP de callback e a superfície de widget HTTP não são mais o caminho padrão de decisão médica e hoje adicionam complexidade operacional sem uso real. Como o sistema ainda não foi provisionado em produção, este é o momento mais seguro para remover diretamente essa superfície legada.

## What Changes

- Remover de forma direta a rota `POST /callbacks/triage-decision` do `bot-api`.
- Remover a superfície HTTP de widget Room-2 (`/widget/room2`, `/widget/room2/bootstrap`, `/widget/room2/submit` e assets estáticos relacionados) do fluxo de runtime.
- Consolidar o runtime para um único caminho de decisão de Room-2: resposta estruturada em Matrix.
- Atualizar documentação e runbooks para retirar instruções de callback/túnel associadas a decisão médica.
- Atualizar testes para eliminar contratos legados e garantir que não exista regressão no fluxo Matrix-only.
- **BREAKING**: integrações que ainda chamarem callback/widget HTTP para decisão médica deixarão de funcionar após esta mudança.

## Capabilities

### New Capabilities

- `room2-decision-matrix-only-runtime`: define explicitamente que o runtime de decisão médica usa apenas respostas estruturadas no Matrix, sem fallback HTTP operacional.

### Modified Capabilities

- `runtime-orchestration`: remover requisitos que mantêm callback como compatibilidade de emergência e refletir runtime Matrix-only.
- `manual-e2e-readiness`: substituir validações de callback assinado por validações equivalentes do fluxo Matrix-only.

## Impact

- APIs/rotas afetadas em `apps/bot_api/main.py` e `src/triage_automation/infrastructure/http/widget_router.py`.
- Configuração e docs com menções a callback/widget público (`docs/runtime-smoke.md`, `docs/setup.md`, `README.md`, `openspec/specs/runtime-orchestration/spec.md`).
- Testes de integração do `bot-api` e qualquer suíte que valide callback/widget.
- Operação: reduz superfície externa HTTP e simplifica suporte de runtime.
