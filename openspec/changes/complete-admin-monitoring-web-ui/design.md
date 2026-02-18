# Design

## Context

O `bot-api` já entrega páginas de dashboard em HTML server-rendered e endpoints administrativos de prompts, mas o acesso atual foi pensado para uso técnico com Bearer token manual. Para operação real por times clínicos e suporte, precisamos de um portal web consistente, com autenticação simples e autorização por papel sem depender de ferramentas externas (Postman/cURL/browser plugin).

Também já existe fundação de auth: `users`, `auth_tokens`, `AuthService` e guardas `reader`/`admin`. O design deve reutilizar essa base e evitar duplicar mecanismo de identidade.

## Goals / Non-Goals

**Goals:**

- Entregar experiência web completa com landing/login/logout.
- Unificar dashboard e admin prompts em shell visual único.
- Garantir homogeneidade estética com linguagem visual compatível com uso hospitalar.
- Garantir autorização por papel: `admin` acessa tudo, `reader` apenas dashboard.
- Manter compatibilidade com autenticação por Bearer para APIs e testes existentes.

**Non-Goals:**

- Implementar recuperação de senha por e-mail, MFA ou SSO.
- Alterar modelo de dados de usuários/roles além do necessário para sessão web.
- Substituir endpoints atuais de API por endpoints exclusivamente HTML.

## Decisions

### Decision 1: Reutilizar `auth_tokens` para sessão web

- Choice: usar o mesmo token opaco emitido no login e armazená-lo em cookie `HttpOnly`.
- Rationale: reduz duplicação, evita nova tabela de sessão e reaproveita expiração/revogação já existentes.
- Alternative considered: criar tabela separada de sessões web.
  - Rejected por aumentar complexidade sem ganho funcional imediato.

### Decision 2: Introduzir rotas web de sessão sem quebrar API

- Choice: adicionar `GET /`, `GET /login`, `POST /login`, `POST /logout` mantendo `POST /auth/login`.
- Rationale: permite UX web completa enquanto preserva integração atual por API.
- Alternative considered: substituir `POST /auth/login` por fluxo apenas de formulário.
  - Rejected por quebrar testes, automações e contratos existentes.

### Decision 3: Guardas aceitam cookie e Bearer

- Choice: resolver autenticação em ordem: Bearer explícito (quando presente), senão cookie de sessão.
- Rationale: mantém retrocompatibilidade e permite chamadas server-rendered sem header manual.
- Alternative considered: aceitar somente cookie para páginas e somente Bearer para APIs.
  - Rejected por duplicar lógica de guardas e aumentar chance de inconsistência.

### Decision 4: Shell único com navegação orientada por papel

- Choice: criar base Jinja2 compartilhada para páginas web com menu condicional:
  - `admin`: Dashboard + Prompts
  - `reader`: Dashboard
- Rationale: consistência visual e clareza operacional.
- Alternative considered: layouts separados para dashboard e admin.
  - Rejected por fragmentar UX e aumentar custo de manutenção.

### Decision 5: Definir design system clínico para todas as páginas web

- Choice: adotar tokens visuais únicos (cores, tipografia, espaçamento, componentes) com estética institucional hospitalar aplicada a dashboard e admin.
- Rationale: reduz carga cognitiva, melhora legibilidade em uso contínuo e evita interfaces heterogêneas entre áreas operacionais.
- Alternative considered: manter estilos livres por página.
  - Rejected por risco de inconsistência visual e pior usabilidade operacional.

### Decision 6: Admin prompts com HTML + API existente

- Choice: construir páginas HTML sobre o serviço de prompt management já existente.
- Rationale: reduz risco ao reusar regras de negócio e trilha de auditoria já implementadas.
- Alternative considered: mover toda lógica para novo fluxo frontend-only.
  - Rejected por risco de regressão e retrabalho.

## Risks / Trade-offs

- [Risco] Cookie mal configurado em ambiente de produção pode reduzir segurança.
  Mitigation: configurar `HttpOnly`, `SameSite` e `Secure` quando TLS estiver presente.
- [Risco] Misturar suporte Bearer + cookie pode introduzir ambiguidades.
  Mitigation: ordem de resolução explícita e testes de precedência.
- [Risco] Leitura indevida de páginas admin por `reader`.
  Mitigation: guardas de papel no backend e testes de autorização para rotas HTML e API.
- [Risco] Regressão visual com introdução de shell.
  Mitigation: migrar páginas existentes incrementalmente e manter testes de renderização.
- [Risco] Paleta/tipografia inadequadas para contexto clínico.
  Mitigation: padronizar design tokens explícitos no shell base e revisar todas as telas com checklist de consistência.

## Migration Plan

1. Criar rotas de sessão web e utilitário de cookie.
2. Implementar design system clínico no shell base e migrar páginas de dashboard para a nova base.
3. Implementar páginas HTML de admin prompts.
4. Aplicar guardas por papel em todas as rotas web/admin.
5. Atualizar documentação de uso web (landing/login/logout) e matriz de acesso.
6. Validar com testes de integração para login, navegação por papel e mutação admin.

Rollback strategy:

- Reverter rotas web novas e manter somente fluxo atual por Bearer/API.
- Preservar compatibilidade de dados, já que não há migração destrutiva prevista.

## Open Questions

- Devemos expor um aviso visual de expiração iminente de sessão no frontend?
- No primeiro release, o menu admin deve incluir apenas prompts ou já reservar placeholders para futuras áreas?
