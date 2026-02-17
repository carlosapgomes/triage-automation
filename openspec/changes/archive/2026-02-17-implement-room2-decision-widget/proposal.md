## Why

Hoje a decisão médica no Room-2 depende de copiar JSON/manual curl, o que aumenta erro operacional, reduz rastreabilidade da ação humana e atrasa testes manuais. Precisamos de um widget operacional para que o médico decida no fluxo normal, sem alterar a máquina de estados existente.

## What Changes

- Introduzir um widget de decisão para Room-2 com UX mínima (aceitar/negar, suporte, motivo) orientada ao contrato atual de decisão.
- Expor endpoints backend para bootstrap do caso no widget e submissão de decisão autenticada, reutilizando os serviços de aplicação já existentes.
- Reutilizar o modelo de autenticação atual (token opaco + role `admin`) para proteger submissão do widget.
- Manter o callback HMAC atual (`/callbacks/triage-decision`) intacto para compatibilidade operacional e testes existentes.
- Atualizar a postagem de Room-2 para incluir instrução/URL de abertura do widget, preservando mensagem de ack e trilha de auditoria.
- Adicionar cobertura TDD (unit + integração) e checklist de validação manual para o fluxo do widget.

## Capabilities

### New Capabilities
- `room2-decision-widget`: Interface e backend de decisão médica no Room-2, com submissão segura e compatível com o contrato de decisão vigente.

### Modified Capabilities
- `runtime-orchestration`: ampliar `bot-api` para servir endpoints/asset do widget sem alterar contratos já existentes.
- `manual-e2e-readiness`: incluir validação manual do widget no fluxo de runtime local/túnel.

## Impact

- Affected code:
  - `apps/bot_api/main.py`
  - `src/triage_automation/infrastructure/http/**`
  - `src/triage_automation/application/services/handle_doctor_decision_service.py` (reuso sem mudança de regra)
  - `src/triage_automation/application/services/post_room2_widget_service.py`
  - `src/triage_automation/infrastructure/matrix/message_templates.py`
  - novos arquivos de widget estático (ex.: `apps/bot_api/static/**`)
  - `docs/manual_e2e_runbook.md` e `.env.example`
- API/runtime surface:
  - novos endpoints do widget no `bot-api` (bootstrap/submissão autenticada)
  - callback HMAC existente permanece ativo
- Dependencies/systems:
  - Matrix Room-2 para distribuição da URL do widget
  - autenticação opaca já implementada
  - ambiente de publicação do `WEBHOOK_PUBLIC_URL`/URL pública do bot-api para abrir o widget
