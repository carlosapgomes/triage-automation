# Design

## Context

O fluxo atual do Room-2 publica um resumo técnico que ainda inclui grande volume de campos estruturados de LLM1 e LLM2 em formato textual achatado.
Nos casos reais analisados, isso gera três problemas operacionais:

- leitura lenta para decisão médica;
- excesso de detalhe não acionável no momento da triagem;
- risco de inconsistência percebida quando a decisão reconciliada (`sugestao`) não fica claramente alinhada ao texto narrativo longo.

Restrições técnicas e de escopo desta mudança:

- não alterar schemas de LLM1/LLM2;
- não alterar prompts de extração/sugestão;
- não alterar parser de decisão estruturada do médico no Room-2;
- preservar persistência de artefatos (`structured_data_json`, `summary_text`, `suggested_action_json`).

Stakeholders principais:

- médicos da Room-2 (consumo do parecer e decisão);
- operação clínica (tempo de leitura e clareza);
- engenharia (rastreabilidade e reversibilidade).

## Goals / Non-Goals

**Goals:**

- Entregar mensagem de parecer ao médico em formato curto e acionável.
- Manter `Resumo clínico` obrigatório em 2 a 4 linhas para contexto rápido do caso.
- Exibir explicitamente e em bloco próprio:
  - `decisão sugerida`
  - `suporte recomendado`
  - `motivo objetivo`
- Exibir somente achados e pendências críticas de exames que impactam conduta imediata.
- Exibir conduta sugerida em bullets curtos.
- Garantir consistência textual entre decisão exibida e motivo exibido.
- Preservar rastreabilidade técnica no banco e trilhas de auditoria.

**Non-Goals:**

- Redefinir regras clínicas de triagem ou reconciliação de política.
- Reprojetar workflow de estados do caso.
- Alterar conteúdo persistido do DJSON.
- Alterar mensagens de instrução/template de resposta estruturada do médico.

## Decisions

### Decision 1: Substituir o bloco extenso de `Dados extraídos` por bloco clínico objetivo

Choice:

- Atualizar apenas os builders de mensagem de resumo do Room-2 (`text` e `formatted_html`) para novo formato compacto.
- Manter os tipos de mensagem (`room2_case_summary`) e fluxo de postagem inalterados.

Rationale:

- Reduz tamanho sem impacto em contratos de publicação/transcrição existentes.

Alternatives considered:

- Criar mensagem adicional e manter a atual em paralelo.
  - Rejeitada por duplicar ruído no Room-2 e não resolver a dor de leitura.

### Decision 2: Definir estrutura fixa de parecer em sete blocos

Choice:

- Estrutura de saída:
  1. Resumo clínico (2 a 4 linhas)
  2. Achados críticos
  3. Pendências críticas
  4. Decisão sugerida
  5. Suporte recomendado
  6. Motivo objetivo
  7. Conduta sugerida

Rationale:

- Sequência orientada para tomada de decisão clínica rápida.

Alternatives considered:

- Mostrar decisão/suporte no topo antes do contexto.
  - Rejeitada por aumentar risco de leitura sem contexto mínimo.

### Decision 3: Implementar seleção determinística de achados e pendências

Choice:

- Mapear campos críticos do DJSON para exibição curta, priorizando:
  - `labs`: Hb, plaquetas, INR
  - `ecg`: presença de laudo e sinal de alerta
  - `policy_precheck`: `labs_pass`, `ecg_present`, `labs_failed_items`
  - `extraction_quality.missing_fields` quando relevante
- Aplicar fallback explícito para ausência de dado (`não informado`).

Rationale:

- Evita texto prolixo e garante que só informação de impacto imediato seja mostrada.

Alternatives considered:

- Continuar exibindo todos os campos com flatten.
  - Rejeitada por manter o problema atual de volume e baixa legibilidade.

### Decision 4: Garantir coerência entre decisão exibida e motivo objetivo

Choice:

- A decisão e o suporte exibidos serão sempre derivados de `suggested_action_json` já reconciliado.
- O motivo objetivo será resumido em 1-2 linhas com foco nos condicionantes críticos (exames ausentes/alterados, risco, urgência), evitando replicar integralmente `rationale.details`.

Rationale:

- Reduz ambiguidade quando o texto narrativo longo diverge da sugestão final reconciliada.

Alternatives considered:

- Exibir `rationale.details` completo.
  - Rejeitada por verbosidade e por potencial inconsistência semântica percebida.

### Decision 5: Preservar contratos técnicos e rastreabilidade integral

Choice:

- Não alterar persistência de artefatos LLM, auditoria e transcritos.
- Mudança limitada à camada de apresentação textual do resumo do Room-2.

Rationale:

- Garante rollback simples por código e zero migração de banco.

Alternatives considered:

- Persistir também uma versão resumida separada.
  - Rejeitada nesta fase por aumentar superfície de mudança sem necessidade.

## Risks / Trade-offs

- [Risco] Resumo curto omitir nuance clínica útil em casos complexos.
  Mitigação: manter resumo clínico obrigatório e bloco de pendências críticas, com fonte completa ainda disponível no PDF e no histórico do caso.

- [Risco] Regras de compactação podem gerar texto excessivamente genérico em dados incompletos.
  Mitigação: usar fallback explícito por campo e destacar pendências como ação.

- [Risco] Regressão em testes que validam conteúdo textual antigo.
  Mitigação: atualizar testes unitários/integrados para o novo contrato de mensagem enxuta.

- [Trade-off] Menos detalhe no corpo da mensagem pode exigir consulta eventual ao relatório original.
  Mitigação: garantir que o resumo preserve contexto clínico suficiente em 2-4 linhas.

## Migration Plan

1. Implementar novos builders de resumo Room-2 (texto e HTML) com formato compacto.
2. Adicionar/atualizar testes unitários de templates cobrindo:
   - presença dos sete blocos;
   - ausência do bloco extenso de dados achatados;
   - consistência entre decisão, suporte e motivo objetivo.
3. Ajustar testes de integração de postagem Room-2 para novo contrato textual.
4. Executar gates de verificação do slice (pytest, ruff, mypy, markdownlint quando aplicável).
5. Deploy sem migração de banco.

Rollback strategy:

1. Reverter commit da mudança de builders e testes.
2. Reexecutar suíte alvo de Room-2 para validar retorno ao formato anterior.
3. Confirmar em ambiente que:
   - `room2_case_summary` voltou ao padrão antigo;
   - fluxo de decisão estruturada permaneceu íntegro.

## Open Questions

- Decisões aprovadas para esta mudança:
  - `conduta sugerida` com alvo de 3 bullets e máximo rígido de 4.
  - casos de sangramento ativo com instabilidade documentada devem incluir frase padrão de prioridade emergente.
