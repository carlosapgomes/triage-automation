# Design: Autoaceite de convites Matrix para salas configuradas

## Context

O runtime `bot-matrix` já consome `/sync` continuamente e roteia eventos de timeline para serviços de aplicação. Atualmente, convites de sala não são processados para autoentrada do bot; por isso, a operação precisa aceitar manualmente o invite (UI ou API), o que cria atrito e risco de indisponibilidade funcional quando a sala oficial é criada ou recriada.

Restrições e decisões já confirmadas com stakeholders:

- autoaceite deve ficar ativo por padrão (sem feature flag)
- whitelist estrita: apenas `ROOM1_ID`, `ROOM2_ID`, `ROOM3_ID`, `ROOM4_ID`
- convites fora da whitelist devem ser ignorados
- falhas devem ser logadas e reprocessadas automaticamente nos polls seguintes
- logs de sucesso em `INFO` e falha em `WARNING` com `room_id` e motivo
- se o bot sair/for removido e receber novo convite para sala permitida, deve aceitar novamente

## Goals / Non-Goals

**Goals:**

- Eliminar etapa manual de aceite de convite para salas oficiais configuradas.
- Garantir autoaceite determinístico e restrito aos quatro `room_id` do ambiente.
- Preservar arquitetura atual (adapters simples, regra de negócio no runtime/application).
- Manter observabilidade operacional clara por logs.

**Non-Goals:**

- Não aceitar convites para salas fora da whitelist configurada.
- Não introduzir configuração de wildcard ou lista dinâmica adicional.
- Não adicionar backoff/limite de tentativas nesta entrega.
- Não alterar semântica clínica dos fluxos Room-1/2/3/4 além do onboarding de membership.

## Decisions

### Decision 1: Tratar convites dentro do loop de sync existente

- Escolha: estender `apps/bot_matrix/main.py` para extrair convites de `rooms.invite` e decidir autojoin no mesmo ciclo de polling.
- Racional: reaproveita infraestrutura existente de tolerância a falhas e evita processo paralelo.
- Alternativas consideradas:
  - processo separado só para membership
  - aceitar convite via tarefa operacional externa
- Motivo da rejeição:
  - processo separado aumenta complexidade operacional
  - tarefa externa mantém atrito manual que o change busca remover

### Decision 2: Whitelist fixa derivada de configuração já existente

- Escolha: construir conjunto permitido com `{ROOM1_ID, ROOM2_ID, ROOM3_ID, ROOM4_ID}` no runtime.
- Racional: menor superfície de erro e aderência à política de menor privilégio.
- Alternativas consideradas:
  - wildcard por domínio do room id
  - variável com lista adicional de salas autorizadas
- Motivo da rejeição:
  - wildcard/lista dinâmica aumenta risco de autoentrada indevida e custo de governança

### Decision 3: Autoaceite sempre ativo (sem feature flag)

- Escolha: comportamento padrão e obrigatório em runtime.
- Racional: reduz chance de ambiente ficar disfuncional por flag desligada e simplifica operação.
- Alternativa considerada: `AUTO_ACCEPT_CONFIGURED_ROOM_INVITES`.
- Motivo da rejeição: adiciona estado de configuração extra sem necessidade operacional neste contexto.

### Decision 4: Join via adapter Matrix HTTP dedicado

- Escolha: adicionar operação `join_room(room_id)` em `MatrixHttpClient` usando `POST /_matrix/client/v3/rooms/{roomId}/join`.
- Racional: mantém responsabilidades do adapter (I/O HTTP) e evita lógica de protocolo no runtime.
- Alternativas consideradas:
  - invocar endpoint por helper ad-hoc no `bot-matrix/main.py`
- Motivo da rejeição:
  - quebraria encapsulamento do adapter e duplicaria tratamento de erro/autorização

### Decision 5: Política de erro e reprocessamento sem backoff explícito

- Escolha: em falha de join, logar `WARNING` e tentar novamente em próximos polls se o convite ainda existir.
- Racional: garante visibilidade e evita falha silenciosa; atende requisito operacional de insistência contínua.
- Alternativas consideradas:
  - limitar tentativas por sala
  - backoff exponencial
- Motivo da rejeição:
  - pode mascarar estado disfuncional e retardar recuperação quando dependência volta

### Decision 6: Logging operacional explícito por resultado

- Escolha:
  - `INFO`: convite aceito em sala permitida
  - `WARNING`: falha ao aceitar convite em sala permitida
  - `DEBUG`/`INFO`: convite ignorado por sala não permitida (a definir no nível final durante implementação)
- Racional: suporte rápido a troubleshooting em produção com trilha mínima necessária.
- Alternativa considerada: logs somente em falha.
- Motivo da rejeição: reduz rastreabilidade de sucesso e confirmação de onboarding automático.

## Risks / Trade-offs

- [Risk] Configuração incorreta de `ROOM*_ID` pode levar o bot a entrar na sala errada.
  - Mitigação: manter whitelist estrita, revisar `.env`/inventário e reforçar runbook operacional.
- [Risk] Falhas repetidas podem gerar ruído de log.
  - Mitigação: manter formato de log estruturado por `room_id` e revisar nível em observabilidade central.
- [Trade-off] Sem backoff, haverá novas tentativas a cada poll enquanto convite persistir.
  - Mitigação: comportamento intencional para não ocultar disfunção e acelerar recuperação.

## Migration Plan

1. Implementar parser/helper para extrair `room_id` de convites em payload `/sync`.
2. Adicionar método `join_room` no adapter `MatrixHttpClient` com tratamento padronizado de erro.
3. Integrar fluxo de autoaceite no loop do `bot-matrix` com whitelist derivada de `Settings`.
4. Adicionar testes unitários/integrados para sucesso, ignore e falha com retry implícito em novo poll.
5. Atualizar documentação operacional (`docs/` e espelho `docs/en/`).
6. Rollout: deploy normal do runtime; sem migração de banco.
7. Rollback: retornar versão anterior do `bot-matrix` (remove autoaceite); operação volta ao aceite manual.

## Open Questions

- Não há questões abertas no momento; decisões funcionais foram confirmadas com o solicitante.
