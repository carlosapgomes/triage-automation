# Design

## Context

O sistema já possui autenticação por sessão/token, papéis `admin`/`reader`,
auditoria de autenticação (`auth_events`) e shell web com navegação por papel.
Atualmente, a gestão de usuários depende de operações manuais fora da UI.

Este change adiciona gestão de usuários no dashboard administrativo, mantendo
o modelo arquitetural atual (`adapters -> application -> domain ->
infrastructure`) e reutilizando padrões já existentes na gestão de prompts
(rotas HTML server-rendered + ações `POST` e validação por `auth_guard`).

Restrições principais:

- `reader` não pode acessar área de usuários.
- `admin` pode gerenciar `reader` e `admin`.
- não pode haver auto-bloqueio/auto-remoção.
- não pode haver estado sem nenhum `admin` ativo.
- bloqueio, reativação e remoção devem gerar trilha de auditoria.

## Goals / Non-Goals

**Goals:**

- Entregar UI administrativa em `/admin/users` para listar e executar ações de
  criação, bloqueio, reativação e remoção.
- Garantir separação semântica entre bloqueio (reversível) e remoção
  (desativação administrativa terminal).
- Invalidar sessões/tokens do usuário alvo sempre que a conta deixar de estar
  ativa.
- Reforçar invariantes de segurança para evitar lockout administrativo.
- Manter consistência visual com o shell operacional existente.

**Non-Goals:**

- Fluxo de auto-registro de usuários.
- Recuperação de senha por e-mail.
- Gestão de permissões granular além de `admin` e `reader`.
- API pública externa para automação de IAM hospitalar.

## Decisions

### 1) Introduzir estado explícito de ciclo de vida do usuário

#### Decisão

Adicionar coluna de estado de conta no `users` para distinguir ações:

- `active`
- `blocked`
- `removed`

`is_active` permanece por compatibilidade de leitura/autenticação e passa a ser
derivado/atualizado conforme o estado (`active=true`, demais=false).

#### Racional

Somente `is_active` não diferencia bloqueio de remoção, o que enfraquece
auditoria, UX e regras de reativação.

#### Alternativas consideradas

- Reusar apenas `is_active` e distinguir por `auth_events`: descartada por gerar
  semântica implícita e consultas mais frágeis.
- Hard delete: descartada por perda de rastreabilidade e conflito com requisito
  de soft delete.

### 2) Padronizar ações administrativas e regras de transição

#### Decisão

Definir transições válidas:

- criar usuário -> `active`
- bloquear -> `blocked`
- reativar -> `active` (somente quando `blocked`)
- remover -> `removed` (terminal)

Ao bloquear/remover:

- revogar todos os tokens ativos do usuário alvo.

Ao remover:

- preservar registro para auditoria (soft delete), sem exclusão física.

#### Racional

A transição explícita evita ambiguidades operacionais e melhora previsibilidade
de comportamento na UI.

#### Alternativas consideradas

- Permitir reativação de `removed`: descartada para manter significado de
  “remoção administrativa” como ação terminal.

### 3) Aplicar guardrails de segurança em camada de aplicação

#### Decisão

Implementar validações em serviço de aplicação (não em adapter):

- proibir auto-bloqueio e auto-remoção;
- proibir transição que deixe `0` admins ativos;
- validar e-mail normalizado único;
- manter política de senha já existente para criação de conta.

As validações de “último admin ativo” devem ocorrer em operação transacional
atômica para evitar condição de corrida.

#### Racional

Essas regras são invariantes de negócio e devem ficar centralizadas na camada
de aplicação para uso consistente por HTML/API.

#### Alternativas consideradas

- Validar apenas na UI: descartada por bypass via chamadas diretas.
- Validar apenas por constraint de banco: insuficiente para regra contextual
  (self-action e contagem dinâmica de admins ativos).

### 4) Reutilizar padrão de superfície HTML administrativa existente

#### Decisão

Seguir o padrão de `prompt_management_router`:

- página server-rendered `GET /admin/users`
- ações por `POST` com redirect `303` e mensagens de feedback

Rotas iniciais:

- `GET /admin/users`
- `POST /admin/users` (create)
- `POST /admin/users/{user_id}/block`
- `POST /admin/users/{user_id}/activate`
- `POST /admin/users/{user_id}/remove`

`reader` recebe `403` para páginas/ações de administração de usuários.

#### Racional

Reduz complexidade, mantém consistência visual/comportamental e reaproveita
infra já testada (auth guard, shell context, templates).

#### Alternativas consideradas

- Construir API JSON-first + frontend separado: descartada para este change por
  aumentar escopo e tempo sem ganho operacional imediato.

### 5) Expandir shell role-aware para navegação de usuários

#### Decisão

Adicionar sinalizador no contexto do shell para exibir navegação “Usuários”
somente para `admin`, mantendo ocultação para `reader`.

#### Racional

Mantém coerência com o padrão já usado para “Prompts” e evita descoberta de
rotas sensíveis por usuários sem privilégio.

#### Alternativas consideradas

- Mostrar item para todos e bloquear no clique: descartada por UX ruim e menor
  clareza de permissões.

### 6) Auditar ações de gestão de usuários em `auth_events`

#### Decisão

Registrar eventos dedicados com ator (`user_id` do admin) e alvo em payload:

- `user_created`
- `user_blocked`
- `user_reactivated`
- `user_removed`

Payload mínimo: `target_user_id`, `target_email`, `target_role`,
`previous_status`, `new_status`.

#### Racional

Permite investigação operacional e compliance usando mecanismo de auditoria já
existente.

#### Alternativas consideradas

- Tabela nova de auditoria de usuários: descartada neste ciclo para evitar
  duplicação de trilha e manter simplicidade.

## Risks / Trade-offs

- [Condição de corrida ao desativar admins simultaneamente] -> Executar checagem
  “último admin ativo” e atualização em transação única com lock adequado.
- [Confusão operacional entre bloqueio e remoção] -> Expor labels/descrições
  claras na UI e impedir reativação de removidos.
- [Revogação incompleta de sessão] -> Implementar método explícito de revogação
  em lote de `auth_tokens` e cobrir com testes de integração.
- [Mudança de schema em ambiente existente] -> Migration backward-compatible
  preservando dados atuais e mapeando usuários ativos para estado `active`.

## Migration Plan

1. Criar migration adicionando coluna de estado de conta em `users` e preencher
   valor inicial (`active` para registros atuais ativos, `blocked` para
   inativos), mantendo `is_active` compatível.
2. Adicionar portas/repositórios para operações de gestão de usuários e
   revogação de tokens por usuário.
3. Implementar serviço de aplicação com regras de transição e guardrails
   administrativos.
4. Implementar router/template de `/admin/users` e incluir item de navegação no
   shell para `admin`.
5. Adicionar eventos de auditoria para todas as ações administrativas.
6. Atualizar testes unitários/integrados e runbook manual E2E.

Rollback:

- rollback de código para versão anterior;
- rollback de migration (se permitido pela janela operacional) ou desativação
  das rotas novas mantendo compatibilidade com colunas adicionais.

## Open Questions

- A remoção deve ocultar o usuário por padrão da listagem principal (com filtro
  “mostrar removidos”) ou permanecer sempre visível com badge de estado?
- O campo opcional de nome de exibição deve ser obrigatório para papel `admin`
  por padrão de operação hospitalar, ou permanecer opcional para todos?
