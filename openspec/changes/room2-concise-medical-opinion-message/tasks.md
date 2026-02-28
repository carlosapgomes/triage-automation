# Tasks

## 1. Contrato de mensagem concisa do Room-2

- [x] 1.1 Atualizar os builders de resumo do Room-2 (`text` e `formatted_html`) para remover o dump achatado completo de LLM1/LLM2.
- [x] 1.2 Implementar layout obrigatório com sete blocos na ordem definida: resumo clínico, achados críticos, pendências críticas, decisão sugerida, suporte recomendado, motivo objetivo e conduta sugerida.
- [x] 1.3 Garantir que o `Resumo clínico` seja renderizado em formato curto (2 a 4 linhas) usando `summary_text` como base.

## 2. Regras de coerência e priorização clínica

- [x] 2.1 Exibir `Decisão sugerida` e `Suporte recomendado` exclusivamente a partir de `suggested_action_json` reconciliado.
- [x] 2.2 Gerar `Motivo objetivo` curto (1 a 2 linhas) coerente com decisão e suporte exibidos.
- [x] 2.3 Implementar seleção determinística de achados/pêndencias críticas (Hb, plaquetas, INR, ECG e flags de precheck) com fallback `não informado`.
- [x] 2.4 Implementar regra editorial para incluir frase padrão de prioridade emergente em casos de sangramento ativo com instabilidade hemodinâmica documentada.
- [x] 2.5 Limitar `Conduta sugerida` para alvo de 3 bullets acionáveis, com máximo rígido de 4.

## 3. Testes e validação

- [x] 3.1 Atualizar testes unitários de templates Room-2 para validar presença dos sete blocos obrigatórios e ausência do bloco extenso anterior.
- [ ] 3.2 Adicionar testes para coerência entre decisão/suporte/motivo e para regra de prioridade emergente.
- [ ] 3.3 Atualizar testes de integração de postagem Room-2 para o novo contrato textual da mensagem `room2_case_summary`.
- [ ] 3.4 Executar verificações obrigatórias do slice: `uv run pytest` (alvos), `uv run ruff check` (paths alterados), `uv run mypy` (paths alterados) e `markdownlint-cli2` (artefatos OpenSpec alterados).

## 4. Encerramento do slice

- [ ] 4.1 Atualizar este checklist marcando itens concluídos conforme implementação.
- [ ] 4.2 Registrar observações de desvio/limitação no próprio `tasks.md`, caso ocorram.
- [ ] 4.3 Commitar e publicar alterações do slice com mensagem alinhada ao escopo da change.
