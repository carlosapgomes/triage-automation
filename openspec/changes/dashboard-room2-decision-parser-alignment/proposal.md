# Dashboard Room-2 Decision Parser Alignment

## Why

No dashboard, o resumo da etapa de avaliação (Room-2) usa heurística textual frágil para detectar decisão (`aceitar`/`negar`). Em respostas enviadas por clientes Matrix mobile, o corpo pode incluir citação da mensagem anterior com `decisao: aceitar` e, abaixo, a resposta final com `decisao: negar`. Nesse cenário, o dashboard pode mostrar decisão incorreta no resumo, mesmo quando o worker aplicou a decisão correta.

## What Changes

- Substituir a heurística textual do dashboard por reutilização do parser estrito já usado no worker (`parse_doctor_decision_reply`).
- Ajustar mapeamento de decisão para o rótulo exibido no resumo (`ACEITAR`/`NEGAR`/`INDEFINIDA`).
- Adicionar teste cobrindo mensagem com citação e decisão final divergente.

## Capabilities

### Modified Capabilities

- `dashboard-room2-thread-summary`: passa a derivar decisão do mesmo parser canônico do worker, mantendo comportamento consistente entre processamento e visualização.

## Impact

- Código afetado: `src/triage_automation/infrastructure/http/dashboard_router.py`.
- Testes afetados: `tests/integration/test_dashboard_pages.py`.
- Sem mudanças de schema, migração de banco ou alteração de workflow clínico.
