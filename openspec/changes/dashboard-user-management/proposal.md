# Proposal

## Why

O dashboard já possui autenticação e autorização por papéis, mas ainda depende de
operações manuais/CLI para gestão de contas. Para uso operacional no hospital,
o `admin` precisa conseguir gerenciar usuários diretamente pela interface web,
com trilha de auditoria e controles de segurança para evitar lockout
administrativo.

## What Changes

- Adicionar uma superfície administrativa web para gestão de usuários em
  `GET /admin/users`.
- Permitir que usuários `admin` criem contas com papel `reader` ou `admin`.
- Permitir ações administrativas sobre contas: bloquear (desativar), reativar e
  remover.
- Definir remoção como **soft delete** (`is_active=false`) com invalidação de
  sessões/tokens ativos do usuário alvo.
- Aplicar proteções de segurança operacionais:
  - impedir que um `admin` remova ou bloqueie a própria conta;
  - impedir que o sistema fique sem nenhum `admin` ativo.
- Manter restrição de acesso: `reader` continua com acesso apenas ao dashboard,
  sem acesso a prompts e sem acesso à administração de usuários.
- Registrar auditoria de gestão de usuários com ator, alvo, ação e timestamp
  (incluindo criação, bloqueio, reativação e remoção).

## Capabilities

### New Capabilities

- `user-management-admin`: gestão de usuários via interface administrativa e API
  interna para criação, bloqueio, reativação e remoção, com políticas de
  segurança e auditoria.

### Modified Capabilities

- `operations-web-shell`: expandir navegação role-aware para incluir a seção de
  administração de usuários para `admin`, mantendo ocultação para `reader`.
- `manual-e2e-readiness`: incluir validações de E2E manual para fluxo de gestão
  de usuários (permissões por papel, efeitos de bloqueio/reativação/remoção e
  eventos de auditoria).

## Impact

- Backend HTTP: novas rotas server-rendered e ações `POST` sob `/admin/users`.
- Camada de aplicação/domínio: novos casos de uso de gestão de usuário e
  validações de segurança para auto-gestão/admin mínimo.
- Persistência: atualização de estado em `users`, invalidação de `auth_tokens`
  do usuário alvo e novos eventos de auditoria.
- UI operacional: nova página administrativa de usuários integrada ao shell
  visual existente.
- Testes: cobertura unitária/integrada para autorização por papel, regras de
  segurança, mutações de usuário e trilha de auditoria.
- Documentação/runbook: atualização de fluxo operacional para gestão de usuários
  pelo dashboard.
