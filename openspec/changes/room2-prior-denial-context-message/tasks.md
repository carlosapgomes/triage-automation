# Tasks

## 1. Semântica de lookup de negativa recente (7 dias)

- [x] 1.1 Adicionar/ajustar testes unitários de `prior_case_queries` para falhar (red) quando a janela usar `created_at` em vez de timestamps de negativa (`doctor_decided_at`/`appointment_decided_at`).
- [x] 1.2 Implementar query e normalização para considerar apenas negativas na janela de 7 dias, excluindo o caso atual e classificando `deny_triage` vs `deny_appointment`.
- [x] 1.3 Garantir fallback determinístico de motivo (`não informado`) e seleção da negativa mais recente por timestamp de desfecho.
- [x] 1.4 Cobrir contagem de negativas na janela (triagem + agendamento) com testes de borda (sem negativas, múltiplas negativas, motivo ausente).

## 2. Exibição no fluxo atual da Room-2 (mensagem II)

- [x] 2.1 Adicionar testes de integração para falhar (red) quando existir negativa recente e a mensagem II não incluir bloco dedicado com data/tipo/motivo.
- [x] 2.2 Adicionar teste de integração garantindo omissão do bloco quando não houver negativa recente na janela.
- [x] 2.3 Atualizar `PostRoom2WidgetService` para propagar contexto de negativa recente para o builder de resumo sem alterar máquina de estados nem contratos de parser.
- [x] 2.4 Atualizar templates de resumo (texto + HTML) para renderizar bloco opcional curto e determinístico de histórico recente, mantendo layout conciso existente.
- [x] 2.5 Garantir formatação temporal estável (BRT) no bloco exibido ao médico e validar com testes determinísticos.

## 3. Auditoria, regressão e validação final

- [x] 3.1 Ajustar/validar evento de auditoria `PRIOR_CASE_LOOKUP_COMPLETED` para refletir `recent_denial_found`, caso selecionado e contagem da janela.
- [x] 3.2 Executar testes alvo (`uv run pytest tests/unit/test_prior_case_lookup.py tests/integration/test_post_room2_widget.py -q`) e corrigir regressões.
- [x] 3.3 Executar `uv run ruff check` e `uv run mypy src apps` nos paths alterados.
- [ ] 3.4 Executar `markdownlint-cli2 "openspec/changes/room2-prior-denial-context-message/**/*.md"` e registrar observações de rollout/rollback no próprio tasks.md quando necessário.
