# Proposal

## Why

O planejamento original da automação já previa lookup de contexto prévio em 7 dias para Room-2, mas esse contexto deixou de aparecer no fluxo médico atual após a migração para respostas estruturadas Matrix e para o resumo clínico conciso.
Sem esse sinal no parecer enviado ao médico, a equipe pode reavaliar casos sem visibilidade de negativa recente (data + justificativa), aumentando retrabalho e risco de decisão inconsistente.

## What Changes

- Reintroduzir no fluxo atual de Room-2 a consulta de negativas recentes por `agency_record_number`, com janela de 7 dias e exclusão do caso atual.
- Definir semântica de negativa recente considerando:
  - negativa médica (`doctor_decision=deny`), e
  - negativa de agendamento (`appointment_status=denied`).
- Exibir no resumo ao médico (mensagem II) um bloco curto e explícito quando houver histórico recente, incluindo no mínimo:
  - indicador de que já houve negativa recente,
  - data/hora da negativa mais recente,
  - tipo de negativa (triagem/agendamento),
  - justificativa/motivo (com fallback determinístico quando ausente).
- Exibir opcionalmente o total de negativas na janela (`últimos 7 dias`) para contexto operacional.
- Manter o comportamento atual quando não houver negativa recente (sem bloco extra), preservando formato conciso.
- Cobrir o comportamento com testes unitários/integrados para lookup, seleção da negativa exibida e renderização textual do bloco no Room-2.
- Não alterar máquina de estados, parser de decisão estruturada, contratos de resposta do médico ou caminho de jobs downstream.

## Capabilities

### New Capabilities

- `room2-prior-denial-context`: Governança do cálculo e normalização de histórico recente de negativas (janela de 7 dias) para consumo no parecer médico da Room-2.

### Modified Capabilities

- `room2-structured-reply-decision`: mensagem II passa a incluir aviso de negativa recente (quando existir) sem alterar o contrato estrutural de decisão do médico.
- `room2-concise-medical-opinion-message`: resumo clínico conciso passa a comportar bloco opcional de histórico recente com data/tipo/motivo de negativa.

## Impact

- Código potencialmente afetado:
  - `src/triage_automation/infrastructure/db/prior_case_queries.py`
  - `src/triage_automation/application/services/post_room2_widget_service.py`
  - `src/triage_automation/infrastructure/matrix/message_templates.py`
  - testes de lookup e de integração de postagem Room-2.
- Sem mudanças de schema de banco obrigatórias para o MVP (reuso de colunas já existentes de decisão/motivo/data).
- Sem mudanças de API externa pública; impacto principal é textual/semântico na mensagem II do Room-2 e na rastreabilidade operacional para decisão médica.
