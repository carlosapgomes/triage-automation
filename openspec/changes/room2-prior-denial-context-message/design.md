# Room-2 Prior Denial Context Design

## Context

O ATS já teve planejamento e implementação inicial de lookup de contexto prévio em 7 dias durante a fase de Room-2 baseada em widget. Com a evolução para o fluxo canônico atual (mensagens I/II/III em Matrix reply estruturado + resumo clínico conciso), o contexto de negativa recente deixou de aparecer para o médico na mensagem II.

Na base atual:

- existe adaptador de consulta de casos prévios (`prior_case_queries`) e evento de auditoria de lookup;
- o resumo clínico de Room-2 (mensagem II) é gerado por builders enxutos, sem bloco de histórico recente;
- a semântica de lookup vigente usa `created_at` como janela e devolve caso prévio mais recente, mesmo quando esse caso não é negativa.

Restrições de arquitetura e comportamento:

- preservar direção `adapters -> application -> domain -> infrastructure`;
- não introduzir lógica de negócio em adapters Matrix;
- não alterar máquina de estados de decisão médica;
- não alterar parser estrito de resposta médica em Room-2;
- manter formato conciso da mensagem II.

Stakeholders principais:

- médicos da Room-2 (decisão clínica com contexto);
- operação/supervisão (rastreabilidade do motivo de negativa recente);
- engenharia (consistência com workflow atual e baixo risco de regressão).

## Goals / Non-Goals

**Goals:**

- Reintroduzir no fluxo atual de Room-2 um sinal confiável de negativa recente (7 dias) para o mesmo `agency_record_number`.
- Exibir no resumo ao médico (mensagem II) bloco opcional curto com data/tipo/motivo da negativa mais recente.
- Garantir semântica determinística de janela e seleção da negativa exibida.
- Cobrir comportamento com testes unitários e de integração no pipeline atual.

**Non-Goals:**

- Não reativar UX antiga de widget como caminho padrão de decisão.
- Não alterar schema de LLM1/LLM2, prompts ou reconciliação de política.
- Não alterar contratos de parser/validação das mensagens de decisão médica.
- Não introduzir migração de banco para MVP desta mudança.

## Decisions

### Decision 1: Lookup de negativa recente permanece no serviço de postagem Room-2

- Escolha: manter a consulta de histórico no `PostRoom2WidgetService` (serviço responsável por montar/publicar mensagem II no fluxo atual), repassando contexto já normalizado para os builders de resumo.
- Racional: centraliza a decisão de exibição no mesmo boundary da postagem clínica, evitando duplicação de regra em adapters ou em múltiplos serviços.
- Alternativas consideradas:
  - consultar histórico dentro do builder de template;
  - consultar histórico antecipadamente no estágio de LLM2.
- Motivo da rejeição:
  - builder deve ser puro (sem I/O);
  - injetar em LLM2 aumenta acoplamento e não garante exibição determinística no texto final.

### Decision 2: Semântica de janela baseada em timestamp de desfecho da negativa

- Escolha: considerar negativa recente quando o timestamp do evento de negativa estiver na janela de 7 dias:
  - `doctor_decided_at` para negativa médica (`doctor_decision='deny'`),
  - `appointment_decided_at` para negativa de agendamento (`appointment_status='denied'`).
- Racional: a pergunta operacional é sobre "foi negado recentemente", portanto o marco temporal deve refletir o momento da negativa, não a criação do caso.
- Alternativa considerada: janela por `cases.created_at`.
- Motivo da rejeição: pode incluir/excluir casos incorretamente e perder precisão clínica quando o caso foi criado antes da decisão.

### Decision 3: Exibição somente quando houver negativa, não apenas caso prévio

- Escolha: renderizar bloco de histórico na mensagem II apenas se houver pelo menos uma negativa na janela; selecionar a negativa mais recente por timestamp de desfecho.
- Racional: evita ruído de casos aceitos e mantém o resumo conciso.
- Alternativas consideradas:
  - mostrar sempre o "caso prévio mais recente", mesmo aceito;
  - mostrar histórico completo de todos os casos da janela.
- Motivo da rejeição:
  - primeiro gera falso contexto para decisão;
  - segundo quebra objetivo de mensagem curta e acionável.

### Decision 4: Bloco textual curto e determinístico no resumo clínico

- Escolha: adicionar seção opcional no corpo da mensagem II com estrutura fixa quando houver negativa recente, contendo:
  - indicação de negativa recente em 7 dias,
  - data/hora da negativa (BRT),
  - tipo (`negado na triagem` ou `negado no agendamento`),
  - motivo/justificativa (ou fallback `não informado`).
- Racional: melhora leitura rápida pelo médico sem descaracterizar o layout conciso já aprovado.
- Alternativas consideradas:
  - inserir apenas contagem numérica de negativas;
  - enviar histórico em mensagem separada.
- Motivo da rejeição:
  - contagem isolada não explica conduta anterior;
  - mensagem separada piora contexto e rastreabilidade da análise em thread.

### Decision 5: Auditoria e observabilidade preservadas com semântica alinhada

- Escolha: manter evento `PRIOR_CASE_LOOKUP_COMPLETED`, mas alinhar payload para sinalizar explicitamente se houve `recent_denial_found`, qual `recent_denial_case_id` e total de negativas na janela.
- Racional: mantém continuidade operacional e facilita diagnóstico quando bloco não aparece.
- Alternativa considerada: criar novo evento de auditoria específico.
- Motivo da rejeição: aumenta cardinalidade de eventos sem ganho funcional imediato para MVP.

## Risks / Trade-offs

- [Risk] Divergência de timezone na data exibida ao médico.
  - Mitigação: padronizar renderização em BRT no template e cobrir com teste determinístico de formatação.
- [Risk] Casos legados sem motivo preenchido causarem mensagem incompleta.
  - Mitigação: fallback explícito `não informado` e teste dedicado.
- [Risk] Regressão do layout conciso da mensagem II.
  - Mitigação: testes de template garantindo seção opcional apenas quando aplicável e preservação dos blocos mandatórios existentes.
- [Trade-off] Mais lógica de seleção no serviço Room-2 em vez de no LLM.
  - Mitigação: lógica deterministicamente testável e desacoplada de variabilidade de modelo.

## Migration Plan

1. Ajustar porta/consulta de histórico para retornar contexto orientado a negativa recente (janela por timestamps de decisão).
2. Atualizar serviço de postagem Room-2 para usar o novo contexto na montagem da mensagem II.
3. Atualizar builders texto/HTML do resumo para bloco opcional de negativa recente.
4. Adicionar/ajustar testes unitários e integrados (lookup, seleção da negativa, renderização, fluxo sem negativa).
5. Validar com `pytest`, `ruff`, `mypy` e `markdownlint-cli2` nos artefatos alterados.
6. Rollback: reverter mudanças de consulta/renderização, sem necessidade de migração de banco.

## Open Questions

- O padrão textual da data/hora em BRT deve ser somente data (`DD/MM/YYYY`) ou data+hora (`DD/MM/YYYY HH:MM`)?
- Devemos incluir também o `case_id` da negativa recente na mensagem médica (para auditoria humana) ou manter esse dado somente em eventos/auditoria para reduzir ruído visual?
