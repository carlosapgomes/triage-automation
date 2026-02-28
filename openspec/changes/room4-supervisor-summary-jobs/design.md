# Room-4 Supervisor Periodic Summaries Design

## Context

O ATS já possui arquitetura orientada a fila (`jobs`) com execução no `worker` e integração Matrix consolidada no adapter HTTP. A demanda é enviar resumos operacionais para uma nova sala de supervisão (Room-4) duas vezes ao dia, com janelas fixas de 12 horas no timezone `America/Bahia`.

Restrições importantes:

- Manter o padrão arquitetural (`adapters -> application -> domain -> infrastructure`).
- Não introduzir lógica de negócio no adapter Matrix.
- Reaproveitar semântica atual de fila/retry/dead-letter do `worker`.
- Evitar postagem duplicada em reexecução manual da mesma janela.

## Goals / Non-Goals

**Goals:**

- Implementar o modelo `scheduler enfileira + worker publica` para resumos da Room-4.
- Garantir dois cortes diários: 07:00 e 19:00 (`America/Bahia`), cobrindo sempre as 12 horas anteriores.
- Publicar mensagem com métricas mínimas obrigatórias:
  - pacientes recebidos
  - relatórios processados
  - casos avaliados
  - desfechos finais (aceitos/recusados)
- Garantir idempotência por janela para evitar duplicidade em reexecução manual.
- Preservar observabilidade e trilha auditável do envio.

**Non-Goals:**

- Não criar nova API pública HTTP para disparo de resumo.
- Não alterar fluxo clínico principal (estados, decisões, parsing de mensagens).
- Não substituir scheduler externo/orquestrador por cron embutido no processo principal.
- Não incluir analytics avançado (quebras por profissional, tempos médios, gráficos) neste MVP.

## Decisions

### Decision 1: Scheduler mínimo dedicado apenas ao enfileiramento

- Escolha: criar um entrypoint leve de scheduler (CLI/processo curto) que calcula a janela e enfileira `post_room4_summary`.
- Racional: separa claramente responsabilidade de agenda (quando) da execução de negócio/publicação (como), mantendo o padrão da solução.
- Alternativas consideradas:
  - cron chamando endpoint HTTP interno
  - lógica de agendamento dentro do `worker`
- Motivo da rejeição:
  - endpoint interno aumenta superfície de segurança e acoplamento ao `bot-api`
  - agendamento dentro do `worker` mistura polling de jobs com relógio de negócio

### Decision 2: Job `post_room4_summary` como unidade de execução no worker existente

- Escolha: adicionar novo `job_type` no mapa de handlers do `worker`, sem criar um worker separado.
- Racional: reaproveita retry/backoff/dead-letter já implementados e reduz complexidade operacional.
- Alternativa considerada: worker dedicado por tipo de job.
- Motivo da rejeição: exigiria nova estratégia de particionamento/claim de fila sem ganho claro para este escopo.

### Decision 3: Janela fechada-aberta em UTC com origem local fixa

- Escolha: calcular cortes em horário local `America/Bahia` e persistir/executar janelas em UTC no formato `[window_start, window_end)`.
- Racional: evita ambiguidade de fronteira temporal, facilita queries SQL e mantém semântica estável em reprocessamento.
- Alternativa considerada: usar apenas horário local em todas as camadas.
- Motivo da rejeição: aumenta risco de inconsistência em persistência/consulta e dificulta comparação determinística.

### Decision 4: Idempotência por janela via registro dedicado de despacho

- Escolha: introduzir armazenamento de controle por janela (ex.: `supervisor_summary_dispatches`) com restrição única por `(room_id, window_start, window_end)`.
- Racional: impede reenvio do mesmo período em reexecução manual e oferece rastreabilidade explícita (`sent_at`, `matrix_event_id`, erro).
- Alternativa considerada: deduplicar apenas na fila `jobs`.
- Motivo da rejeição: fila pode conter jobs repetidos legítimos; dedupe no envio é o ponto correto de garantia funcional.

### Decision 5: Definição operacional das métricas do resumo

- Escolha:
  - pacientes recebidos: `cases.created_at` na janela
  - relatórios processados: `case_report_transcripts.captured_at` na janela
  - casos avaliados: `cases.doctor_decided_at` na janela
  - aceitos (desfecho final): `cases.appointment_status = 'confirmed'` com `appointment_decided_at` na janela
  - recusados (desfecho final): soma de
    - `cases.doctor_decision = 'deny'` com `doctor_decided_at` na janela
    - `cases.appointment_status = 'denied'` com `appointment_decided_at` na janela
- Racional: usa marcos temporais explícitos e alinhados ao desfecho real do fluxo.
- Alternativa considerada: contar por `status` corrente do caso.
- Motivo da rejeição: status corrente pode já ter evoluído (`WAIT_R1_CLEANUP_THUMBS`, `CLEANED`) e não representa o momento do desfecho.

### Decision 6: Template de mensagem textual simples e estável

- Escolha: mensagem única de texto no Room-4 contendo identificação da janela local e os cinco totais.
- Racional: legibilidade alta para supervisão e implementação de baixo risco.
- Alternativa considerada: payload rico HTML/tabela ou arquivo anexo.
- Motivo da rejeição: complexidade maior sem necessidade para o MVP.

## Risks / Trade-offs

- [Risk] Cálculo incorreto de janela por timezone/corte de horário.
  - Mitigação: testes unitários de janela para execuções às 07:00 e 19:00 em `America/Bahia`, incluindo reprocessamento determinístico.
- [Risk] Duplicação por reexecução manual concorrente.
  - Mitigação: chave única por janela + verificação transacional antes de enviar ao Matrix.
- [Risk] Divergência de interpretação de “resultado final recusado”.
  - Mitigação: congelar definição nas specs (negação médica + negativa de agendamento) e cobrir com testes de consulta.
- [Trade-off] Métricas baseadas em timestamps de eventos, não em “estado atual”.
  - Mitigação: explicitar janela e semântica no texto do resumo.
- [Trade-off] Reuso do `worker` central aumenta acoplamento de carga no mesmo processo.
  - Mitigação: job curto/leve e controlável por frequência baixa (2x/dia).

## Migration Plan

1. Adicionar configuração para Room-4 e timezone/frequência de resumo.
2. Criar migração de banco para tabela de idempotência/rastreio de dispatch de resumo.
3. Implementar serviço de scheduler para enfileirar `post_room4_summary` com janela calculada.
4. Implementar serviço de agregação/publicação no `worker` + handler do novo job.
5. Validar testes unitários e integração (janela, métricas, idempotência e publicação).
6. Publicar em produção com cron/orquestrador chamando scheduler às 07:00 e 19:00 (`America/Bahia`).
7. Rollback: desativar scheduler e manter código inerte (sem novos enfileiramentos).

## Open Questions

- Não há questões abertas para este artefato; decisões de janela, timezone, métricas e idempotência foram confirmadas.
