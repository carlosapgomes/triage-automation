# Design

## Context

O runtime atual ainda publica uma superfície HTTP legada para decisão médica (`/callbacks/triage-decision` e endpoints de widget em `/widget/room2*`), apesar de o fluxo padrão já ser Matrix-only via resposta estruturada em Room-2. Esse caminho adicional aumenta complexidade operacional, mantém dependências de configuração que não são mais necessárias para a operação padrão e mantém documentação/runbooks ambíguos para suporte.

A mudança será feita antes de provisionamento produtivo, portanto sem requisito de compatibilidade retroativa para integrações externas.

## Goals

- Remover completamente endpoints HTTP legados de decisão médica (callback e widget).
- Consolidar o `bot-api` para manter apenas superfícies HTTP necessárias ao escopo atual (ex.: auth/admin foundation).
- Atualizar specs e documentação para refletir runtime Matrix-only sem fallback HTTP operacional.
- Garantir que testes cubram ausência da superfície legada e preservação do fluxo Matrix estruturado.

## Non-Goals

- Redesenhar máquina de estados do workflow clínico.
- Alterar contratos de decisão estruturada no Matrix (template, validação, idempotência).
- Introduzir nova alternativa de fallback fora do Matrix.

## Decisions

### Decision 1: Hard removal dos endpoints legados (sem fase de deprecação em runtime)

- Choice: remover registro de rota para `/callbacks/triage-decision` e todo roteador/widget asset HTTP relacionado (`/widget/room2`, `/widget/room2/bootstrap`, `/widget/room2/submit`, `app.js`, `styles.css`).
- Rationale: sistema ainda não está em produção; remover direto reduz superfície de ataque e evita custo de manutenção duplicada.
- Alternative considered: manter endpoint retornando `410 Gone` por um ciclo.
  - Rejected porque não há consumidores produtivos e adiciona código transitório desnecessário.

### Decision 2: Remover wiring e dependências de callback/widget do `create_app`

- Choice: retirar do `apps.bot_api.main` o wiring de callback HMAC e o include do widget router, além de imports/dtos/services exclusivos desse caminho.
- Rationale: evita dependências mortas no runtime e simplifica composição de aplicação.
- Alternative considered: manter wiring interno sem expor rota.
  - Rejected por gerar acoplamento oculto e risco de regressão futura.

### Decision 3: Alinhar specs/runbooks para eliminar ambiguidade operacional

- Choice: atualizar `runtime-orchestration` e `manual-e2e-readiness` removendo requisitos de callback/túnel para decisão médica.
- Rationale: contrato de produto deve refletir prática operacional real (Matrix-only).
- Alternative considered: manter texto de “emergency-only callback”.
  - Rejected por contradição com remoção direta solicitada.

### Decision 4: Preservar somente capacidades de auth que não dependem de widget/callback

- Choice: manter `/auth/login` e serviços de auth/roles sem alteração comportamental.
- Rationale: esses componentes são base do dashboard/admin planejado e independem da decisão médica por callback.
- Alternative considered: reduzir `bot-api` ao mínimo removendo também auth.
  - Rejected por bloquear roadmap imediato de monitoramento/admin.

## Risks / Trade-offs

- [Dependência oculta de callback em testes/scripts locais] → Mitigation: varrer suites/docs por `/callbacks/triage-decision` e substituir por validações Matrix-only.
- [Sobras de configuração legada no `.env` e docs] → Mitigation: remover variáveis e referências legadas, além de validar bootstrap com `uvicorn`/compose após limpeza.
- [Perda do atalho HTTP para testes manuais] → Mitigation: reforçar runbook Matrix-only com checklist operacional equivalente e cenários negativos.
- [Remoção de arquivos estáticos sem limpar importações] → Mitigation: executar lint/type/tests focados em `apps/bot_api` e `infrastructure/http` para garantir ausência de referências órfãs.

## Migration Plan

1. Remover wiring de callback/widget no `bot-api` e limpar imports/dtos/código morto associado ao caminho HTTP de decisão.
2. Atualizar specs afetadas (`runtime-orchestration`, `manual-e2e-readiness`) para contrato Matrix-only.
3. Atualizar runbooks e docs operacionais removendo seções de webhook HMAC e túnel para decisão médica.
4. Atualizar testes (integração/unidade) para refletir ausência de endpoints legados e preservar comportamento do fluxo Matrix.
5. Rodar quality gates (`pytest`, `ruff`, `mypy`) e smoke local (`uvicorn` + worker/bot-matrix) com cenários Matrix-only.

Rollback strategy:

- Reverter o commit da mudança para restaurar callback/widget routes se houver bloqueio inesperado em ambiente de homologação.
- Como não há migração de dados nessa change, rollback é puramente de código e documentação.

## Open Questions

- Nenhuma decisão funcional pendente para esta change. A expectativa é execução direta conforme escopo aprovado.
