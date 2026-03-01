# Autoaceite de convites Matrix para salas configuradas

## Why

Hoje a operação exige uma etapa manual para aceitar convites do bot em novas salas, o que aumenta atrito de implantação e pode bloquear fluxos se o convite não for aceito a tempo. Automatizar esse aceite apenas para salas explicitamente configuradas reduz trabalho operacional sem abrir a adesão automática para salas não autorizadas.

## What Changes

- Estender o runtime `bot-matrix` para observar convites em `/sync` e executar `join` automático quando o `room_id` do convite estiver na whitelist de configuração (`ROOM1_ID`, `ROOM2_ID`, `ROOM3_ID`, `ROOM4_ID`).
- Ignorar convites para qualquer sala fora da whitelist, com log explícito para auditoria operacional.
- Adicionar operação de cliente Matrix para `join` de sala via API oficial (`/_matrix/client/v3/rooms/{roomId}/join`).
- Cobrir o comportamento com testes unitários/integrados para:
  - aceite automático em sala permitida;
  - não aceite em sala não permitida;
  - robustez em falhas transitórias de transporte/HTTP.
- Atualizar documentação operacional para deixar explícito que convites para salas configuradas podem ser aceitos automaticamente pelo bot em runtime.

## Capabilities

### New Capabilities

- Nenhuma.

### Modified Capabilities

- `matrix-live-adapters`: ampliar requisitos de roteamento live para incluir tratamento de convites Matrix com autoaceite restrito às salas configuradas no ambiente.

## Impact

- Código afetado (provável):
  - `apps/bot_matrix/main.py` (detecção de convites e fluxo de autoaceite)
  - `src/triage_automation/infrastructure/matrix/http_client.py` (novo método de join de sala)
  - testes de listener/runtime Matrix (`tests/unit/` e/ou `tests/integration/`)
- Configuração:
  - sem novas variáveis obrigatórias para o comportamento base (whitelist derivada de `ROOM1_ID..ROOM4_ID`)
  - possível variável opcional de feature flag se desejarmos habilitação explícita por ambiente
- Operação:
  - reduz necessidade de login manual do usuário bot para aceitar convites nas salas oficiais
  - mantém princípio de menor privilégio, pois convites fora da whitelist continuam recusados/ignorados
- APIs externas:
  - passa a usar endpoint Matrix de join de sala no adapter HTTP já existente
