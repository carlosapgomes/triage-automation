# Room-4 Supervisor Periodic Summaries via Scheduler + Worker

## Why

A equipe de supervisão precisa receber um resumo operacional periódico diretamente em uma sala dedicada (Room-4), sem depender de consulta manual ao dashboard. Hoje o sistema não possui um mecanismo automático, idempotente e auditável para consolidar métricas por janela de tempo e publicar esse resumo no Matrix.

## What Changes

- Introduzir uma capacidade de resumo periódico para supervisão com arquitetura **scheduler enfileira + worker publica**.
- Adicionar suporte de configuração para Room-4 e para execução fixa de **2 resumos por dia** (07:00 e 19:00), cada um cobrindo a janela anterior de 12 horas.
- Criar um runtime de scheduler (processo leve/CLI) que calcula a janela de apuração em `America/Bahia` (UTC-3) e enfileira jobs `post_room4_summary`.
- Estender o worker para consumir `post_room4_summary`, calcular métricas no banco e publicar mensagem consolidada na Room-4.
- Garantir idempotência estrita por janela (inclusive em reexecução manual), evitando envio duplicado do mesmo período e registrando trilha de auditoria do envio.
- Definir template textual padronizado da mensagem de resumo, incluindo janela de referência e métricas mínimas: pacientes recebidos, relatórios processados, casos avaliados e desfechos finais do fluxo (aceitos/recusados).
- Cobrir o fluxo com testes unitários/integrados para cálculo, deduplicação, enfileiramento e publicação Matrix.

## Capabilities

### New Capabilities

- `room4-supervisor-periodic-summary`: Permite gerar e publicar resumos operacionais periódicos na Room-4 com base em dados persistidos, usando scheduler para enfileirar e worker para executar o envio com idempotência por janela.

### Modified Capabilities

- Nenhuma.

## Impact

- Código afetado (provável):
  - `apps/worker/main.py` (novo handler `post_room4_summary`)
  - novo entrypoint de scheduler em `apps/` (ou script dedicado) para enfileiramento periódico
  - `src/triage_automation/application/services/` (serviço de agregação/publicação do resumo)
  - `src/triage_automation/infrastructure/db/` (queries de consolidação + persistência de controle de envio)
  - `src/triage_automation/config/settings.py` e `.env.example` (novas variáveis de configuração)
  - `docker-compose.yml` (serviço do scheduler, se definido no compose)
- Banco de dados: possível nova tabela para controle de idempotência de janelas de resumo e metadados de envio.
- Operação: necessidade de agendamento (cron/orquestrador) para disparo do scheduler às 07:00 e 19:00 no timezone `America/Bahia`.
- APIs externas: sem novas APIs públicas obrigatórias; publicação ocorre via integração Matrix já existente.
- Risco funcional: baixo a moderado, concentrado em timezone/janelas de corte e prevenção de duplicidade.
