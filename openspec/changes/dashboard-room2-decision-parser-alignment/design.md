# Dashboard Room-2 Decision Parser Alignment Design

## Context

O worker de Room-2 já usa parser estrito (`parse_doctor_decision_reply`) para validar campos estruturados e ignorar citação de replies Matrix (`>`). Já o dashboard extrai a decisão com busca de substring em texto livre, o que permite falso positivo quando há múltiplos blocos de decisão no mesmo corpo.

## Goals / Non-Goals

**Goals:**

- Reutilizar no dashboard o parser canônico do worker para extrair decisão de `room2_doctor_reply`.
- Garantir que respostas com citação de mensagem anterior exibam a decisão final correta no resumo da etapa.
- Manter fallback determinístico para `INDEFINIDA` quando o payload não puder ser parseado.

**Non-Goals:**

- Não alterar o parser de domínio do worker.
- Não alterar regras de transição de estado, idempotência ou enfileiramento.
- Não alterar contratos de mensagens Matrix já persistidas.

## Decisions

### Decision 1: Reuso direto do parser de domínio no dashboard

- Escolha: importar `parse_doctor_decision_reply` no `dashboard_router` para extração da decisão do resumo de Room-2.
- Racional: evita divergência de heurística e reduz risco de inconsistência entre decisão aplicada e decisão exibida.
- Alternativa considerada: reimplementar parser simplificado no dashboard.
- Motivo da rejeição: duplicação de regra crítica e risco de drift.

### Decision 2: Fallback explícito para `INDEFINIDA` em erro de parse

- Escolha: quando o parser lançar erro, retornar `INDEFINIDA`.
- Racional: preserva robustez da página mesmo com registros legados ou conteúdo não estruturado.
- Alternativa considerada: fallback para busca textual.
- Motivo da rejeição: reintroduz heurística frágil e resultados conflitantes.

## Risks / Trade-offs

- [Risco] Registros legados sem template estruturado deixarão de ser classificados por substring.
  - Mitigação: exibir `INDEFINIDA`, que é estado honesto para conteúdo inválido.
- [Trade-off] Dependência do módulo HTTP em parser de domínio.
  - Mitigação: dependência é unidirecional (infrastructure -> domain) e compatível com arquitetura atual.

## Migration Plan

1. Escrever teste de integração do dashboard com mensagem `room2_doctor_reply` contendo citação e decisão final divergente (red).
2. Implementar extração via parser canônico no `dashboard_router` (green).
3. Executar validações alvo (`pytest`, `ruff`, `mypy`, `markdownlint`).

## Open Questions

- Nenhuma para este slice.
