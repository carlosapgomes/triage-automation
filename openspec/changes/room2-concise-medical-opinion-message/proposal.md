# Proposal

## Why

As mensagens atuais do Room-2 estão longas e excessivamente técnicas para leitura operacional rápida do médico.
O conteúdo mostra praticamente todo o payload estruturado de LLM1/LLM2 em formato achatado, o que aumenta tempo de leitura e eleva risco de perda de contexto clínico relevante.
Precisamos manter segurança de decisão e rastreabilidade sem alterar o DJSON extraído, reduzindo o texto exibido ao médico para um formato de parecer objetivo.

## What Changes

- Reduzir o conteúdo exibido na mensagem de resumo do Room-2 para um formato clínico objetivo e curto.
- Manter `Resumo clínico` obrigatório em 2 a 4 linhas, com foco em contexto do caso para quem não leu o relatório completo.
- Exibir, de forma explícita e destacada:
  - `decisão sugerida`
  - `suporte recomendado`
  - `motivo objetivo` (1 a 2 linhas)
- Exibir bloco objetivo de exames e pendências críticas apenas com itens que impactam conduta imediata.
- Exibir bloco de conduta sugerida com orientações curtas e acionáveis.
- Remover da mensagem ao médico a listagem extensa de campos estruturados achatados (`Dados extraídos` completos).
- Preservar integralmente o DJSON de LLM1 e LLM2 no armazenamento/auditoria/transcritos para rastreabilidade técnica.
- Não alterar schema de LLM1/LLM2, nem prompts de extração, nem reconciliação de política.

## Capabilities

### New Capabilities

- `room2-concise-medical-opinion-message`: apresentação clínica enxuta no Room-2 com foco em contexto, decisão, suporte, motivo objetivo e conduta.

### Modified Capabilities

- `room2-structured-reply-decision`: ajuste de UX textual da mensagem de apoio à decisão sem alterar contrato de resposta estruturada do médico.

## Impact

- Alterações em templates de mensagem do Room-2 (`summary` texto e HTML formatado).
- Ajustes em testes unitários e de integração que validam conteúdo da mensagem publicada no Room-2.
- Sem impacto em schema de extração/sugestão, estados do workflow, parser de resposta estruturada do médico ou persistência de artefatos LLM.

## Rollback Plan

- Reversão funcional por commit único que restaure os builders anteriores de resumo do Room-2.
- Rollback sem migração de banco, pois a mudança é apenas de apresentação textual.
- Garantir que rollback preserve:
  - contratos de mensagens `room2_case_summary`, `room2_case_instructions`, `room2_case_template`
  - persistência de `structured_data_json`, `summary_text` e `suggested_action_json`
  - fluxo de decisão estruturada do Room-2 inalterado.
- Critério de rollback operacional:
  - aumento de ambiguidade clínica reportada por médicos
  - perda de contexto para decisão em casos reais
  - regressão de testes de fluxo Room-2.
