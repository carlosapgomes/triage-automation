## Context

Atualmente o Room-2 publica um payload JSON em texto e a decisão médica é acionada por callback manual assinado, normalmente via curl. Isso é funcional para validação técnica, mas frágil para operação real: aumenta risco de erro humano, gera atrito de uso e dificulta adoção do fluxo por médicos.

O projeto já possui base de autenticação com usuário/role/token opaco e já possui serviço idempotente para decisão (`HandleDoctorDecisionService`) com regras críticas de estado (`WAIT_DOCTOR`) e enfileiramento de próximos jobs. O objetivo desta mudança é adicionar a camada de interação (widget) sem alterar regras de negócio.

Constraints non-negotiable for this design:
- Não alterar state machine nem semântica de transições.
- Não alterar contrato de callback HMAC existente.
- Não mover lógica de negócio para adapters/frontend.
- Manter TDD e slices pequenos.

## Goals / Non-Goals

**Goals:**
- Entregar widget de decisão Room-2 utilizável em ambiente manual/local.
- Permitir submissão de decisão com autenticação e autorização explícitas (`admin`).
- Reutilizar serviço atual de decisão para preservar comportamento, idempotência e auditoria.
- Manter mensagens de Room-2 e callback existente compatíveis.

**Non-Goals:**
- Redesenhar triagem clínica/políticas de decisão.
- Construir painel administrativo amplo.
- Substituir/remover o callback HMAC atual.
- Alterar fluxo de Room-3 ou cleanup.

## Decisions

### Decision 1: Add dedicated widget backend endpoints, keep callback endpoint unchanged
- Choice: adicionar endpoints específicos de widget (bootstrap + submit) no `bot-api`, protegidos por autenticação/role.
- Rationale: o browser não deve receber segredo HMAC; manter callback atual evita quebra de integração e risco de regressão.
- Alternative considered: submeter direto em `/callbacks/triage-decision` com HMAC no cliente.
  - Rejected because expõe segredo e viola segurança operacional.

### Decision 2: Reuse `HandleDoctorDecisionService` as single decision business path
- Choice: endpoint de submit do widget chama o mesmo serviço de decisão já usado no callback.
- Rationale: garante paridade de regras, idempotência e eventos de auditoria.
- Alternative considered: criar novo serviço específico para widget.
  - Rejected because duplicaria regra de estado e aumentaria risco de drift.

### Decision 3: Gate widget submit by opaque token + explicit role guard
- Choice: exigir token opaco válido e role `admin` para submeter decisão.
- Rationale: infraestrutura de auth já existe e atende o requisito de trilha auditável de autenticação.
- Alternative considered: endpoint sem auth confiando apenas em `doctor_user_id` no payload.
  - Rejected because não autentica o ator real.

### Decision 4: Keep Room-2 posting backward compatible while introducing widget launch
- Choice: manter mensagem/payload atual e adicionar dados de lançamento do widget (URL + metadados de caso).
- Rationale: reduz risco operacional durante transição e permite fallback manual.
- Alternative considered: substituir totalmente a mensagem atual por formato novo.
  - Rejected because aumenta risco de perda de observabilidade e troubleshooting.

## Risks / Trade-offs

- [Widget URL reachability in local environments] -> Mitigation: documentação de túnel/URL pública e healthcheck explícito no runbook.
- [Token expiration during long clinical session] -> Mitigation: UX com erro claro + fluxo de re-login rápido.
- [Role/user mapping mismatch with Matrix identity] -> Mitigation: registrar `doctor_user_id` explícito no submit e auditar origem/auth metadata.
- [Compatibility variance across Matrix clients for widget launch UX] -> Mitigation: manter fallback textual com instruções e link direto.

## Migration Plan

1. Introduzir contratos/DTOs e testes para endpoints de widget (RED).
2. Implementar routes widget + guards + integração com serviço de decisão (GREEN).
3. Atualizar postagem Room-2 para incluir contexto de lançamento do widget.
4. Adicionar assets estáticos mínimos do widget e testes de integração.
5. Atualizar runbook manual com validações positivas/negativas.
6. Deploy gradual em ambiente de teste; manter callback HMAC como fallback operacional.

Rollback strategy:
- Desabilitar uso do widget no Room-2 (feature/config toggle) e voltar para operação manual via callback sem reverter schema de dados.

## Open Questions

- Devemos publicar widget como embedding nativo Matrix (state event) já nesta mudança ou manter link externo como entrega inicial?
- Precisamos de TTL curto para contexto de caso no endpoint de bootstrap (ex.: 15 min) ou podemos usar leitura on-demand por case_id com guard de role?
- A equipe clínica quer obrigatoriedade de `reason` para `deny` no widget (hoje opcional)?
