# Proposal

## Why

O sistema já possui dashboard HTML e APIs administrativas, mas não possui experiência web completa para operação diária: não há landing/login por navegador e a autenticação depende de envio manual de Bearer token. Isso torna a operação frágil para equipes não técnicas e impede uma experiência consistente de portal.

## What Changes

- Implementar landing page simples com fluxo de login/logout web.
- Introduzir sessão web via cookie seguro (`HttpOnly`) para navegação autenticada sem exigir header manual.
- Criar shell visual único (layout, navegação e convenções de UI) compartilhado por dashboard e páginas administrativas.
- Definir linguagem visual hospitalar para o portal:
  - paleta institucional neutra/clínica,
  - tipografia legível para leitura contínua,
  - hierarquia e espaçamento consistentes para uso operacional em desktop e mobile.
- Implementar páginas HTML para administração de prompts (lista de versões, versão ativa, ativação).
- Manter APIs atuais (`/monitoring/*`, `/dashboard/*`, `/admin/prompts/*`) e adicionar camada de UX web acima delas.
- Aplicar matriz de autorização explícita:
  - `admin`: acesso ao dashboard e ao admin de prompts.
  - `reader`: acesso somente ao dashboard.
- Preservar fallback de autenticação por Bearer para chamadas de API e testes automatizados.

## Capabilities

### New Capabilities

- `web-login-session`: autenticação web com página de login, criação de sessão por cookie e logout.
- `operations-web-shell`: layout/base de navegação compartilhado com menus condicionados por papel e experiência consistente entre páginas.

### Modified Capabilities

- `case-thread-monitoring-dashboard`: migrar acesso principal para sessão web, mantendo leitura para `reader` e `admin` dentro do novo shell.
- `prompt-management-admin`: adicionar superfície HTML de administração de prompts, mantendo mutação restrita a `admin` e bloqueio para `reader`.

## Impact

- Backend `bot-api`: novas rotas web de sessão (`GET/POST /login`, `POST /logout`, `GET /`) e utilitários de sessão por cookie.
- Templates Jinja2: criação de shell único e telas administrativas de prompts.
- UI/UX operacional: adoção de design system clínico único para todas as telas web do portal.
- Guardas de autenticação/autorização: suporte a cookie de sessão sem remover Bearer token existente.
- Testes: novos testes de integração para login web, navegação por papel e bloqueio `reader` em admin prompts.
- Documentação operacional: atualização de setup/runbook para fluxo de acesso web completo.
