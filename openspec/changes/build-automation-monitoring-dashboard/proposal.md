# Proposal

## Why

A operação precisa de rastreabilidade completa por caso para auditoria, investigação de bugs e melhoria contínua dos prompts/fluxos. O modelo atual registra metadados importantes, mas não preserva de forma íntegra e consultável todo o conteúdo textual trocado entre PDF, LLMs e mensagens Matrix.

## What Changes

- Criar dashboard de monitoramento para listar casos processados e abrir visão em linha do tempo (thread) por caso.
- Fixar stack do dashboard em tecnologia "boring" sem build step frontend:
  - backend e renderização: `FastAPI` + `Jinja2`,
  - UI/CSS: `Bootstrap 5.3`,
  - navegação parcial/interações HTML-first: `Unpoly`,
  - JavaScript adicional: `vanilla` somente quando necessário.
- Exibir, por evento da thread, sala/origem, data-hora, ator/autor, tipo da mensagem e conteúdo integral (incluindo ACKs).
- Introduzir diferenciação de acesso:
  - Perfil `reader`: consulta/monitoramento.
  - Perfil `admin`: todas as capacidades de `reader` + gestão de prompts (listar versões, ativar versão, histórico e auditoria).
- Persistir trilha textual completa para auditoria técnica:
  - texto extraído integral do relatório inicial,
  - payload enviado ao LLM1 e resposta recebida,
  - payload enviado ao LLM2 e resposta recebida,
  - mensagens enviadas às salas 1/2/3,
  - respostas dos usuários nessas salas,
  - mensagens de ACK e re-prompts.
- Incluir migrações de banco para suportar armazenamento e consulta eficiente desse histórico completo.
- **BREAKING**: aumento intencional de persistência de dados textuais (impacto de volume/retention e requisitos de segurança/privacidade operacionais).

## Capabilities

### New Capabilities

- `case-thread-monitoring-dashboard`: visualização operacional por caso com timeline completa de eventos e mensagens multi-sala.
- `full-transcript-persistence`: persistência integral e consultável de entradas/saídas de LLM e mensagens humanas/bot por caso.
- `prompt-management-admin`: gestão de prompts por perfil `admin` (versões, ativação, trilha de auditoria).

### Modified Capabilities

- `runtime-orchestration`: ampliar o escopo do `bot-api` para suportar endpoints de monitoramento/admin e exposição segura dessas funcionalidades.
- `manual-e2e-readiness`: adicionar validações manuais de trilha auditável ponta a ponta e controle de acesso reader/admin.

## Impact

- Banco de dados: novas tabelas/colunas/índices e migrações para persistência textual integral e consultas por timeline.
- Backend `bot-api`: novos endpoints de monitoramento e administração de prompts com guardas de role.
- Camada de aplicação/infra: captura explícita de payloads LLM, mensagens Matrix e ACKs com associação por `case_id`.
- Frontend administrativo: painel server-rendered no `bot-api` (Jinja2 + Bootstrap + Unpoly), sem pipeline de build frontend dedicado.
- Segurança e operação: revisão de retenção, mascaramento e acesso a conteúdo sensível em ambiente hospitalar.
