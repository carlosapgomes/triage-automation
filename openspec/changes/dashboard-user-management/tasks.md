# Tasks

## 1. Data Model And Persistence Foundations

- [x] 1.1 Criar migration para estado de conta em `users` (`active`/`blocked`/`removed`) mantendo compatibilidade com `is_active`.
- [x] 1.2 Estender portas e repositórios de usuário para listar usuários, criar conta e aplicar transições de estado.
- [x] 1.3 Adicionar operação de revogação em lote de `auth_tokens` por `user_id` para ações de bloqueio/remoção.
- [x] 1.4 Cobrir repositórios/migration com testes focados de persistência e invariantes básicos de estado.

## 2. Application Services And Security Invariants

- [x] 2.1 Implementar serviço de gestão de usuários com casos de uso: listar, criar, bloquear, reativar e remover.
- [x] 2.2 Implementar validações de segurança: proibir auto-bloqueio/auto-remoção e impedir zero admins ativos.
- [x] 2.3 Reutilizar normalização de email e política de senha existente na criação de contas.
- [x] 2.4 Registrar eventos de auditoria (`user_created`, `user_blocked`, `user_reactivated`, `user_removed`) com metadados de ator/alvo.
- [x] 2.5 Adicionar testes unitários do serviço cobrindo fluxos positivos, negações por autorização e regras de segurança.

## 3. Admin HTTP Surface And Shell Navigation

- [x] 3.1 Criar router de administração de usuários com `GET /admin/users` e ações `POST` para create/block/activate/remove.
- [x] 3.2 Implementar página server-rendered de usuários com feedback de sucesso/erro seguindo o shell operacional existente.
- [x] 3.3 Expandir contexto/layout do shell para exibir navegação de usuários apenas para `admin`.
- [x] 3.4 Garantir respostas determinísticas de autorização para `reader` (`403`) nas páginas e ações de user-admin.
- [ ] 3.5 Adicionar testes HTTP/integração para fluxos de sessão e autorização por papel na nova superfície.

## 4. Manual E2E And Operational Documentation

- [ ] 4.1 Atualizar `docs/manual_e2e_runbook.md` com validações de criação, bloqueio, reativação e remoção de usuários.
- [ ] 4.2 Incluir no runbook checagens explícitas de auditoria para eventos de gestão de usuários.
- [ ] 4.3 Atualizar testes de documentação para refletir os novos passos e expectativas de autorização.

## 5. Final Verification

- [ ] 5.1 Executar suíte de testes alvo da feature de gestão de usuários (unit + integração + docs alteradas).
- [ ] 5.2 Executar `uv run ruff check` e `uv run mypy` nos caminhos alterados.
- [ ] 5.3 Executar `markdownlint-cli2` nos artefatos OpenSpec e documentação modificada.
