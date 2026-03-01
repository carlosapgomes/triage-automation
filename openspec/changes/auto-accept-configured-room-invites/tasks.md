# Tasks

## 1. Contrato e parser de convites no sync Matrix

- [x] 1.1 Adicionar testes unitários para extração de `room_id` em `rooms.invite` no parser de sync sem regressão no comportamento atual de timeline.
- [x] 1.2 Implementar helper de parsing de convites em `sync_events` com tipagem/docstrings e retorno determinístico para payloads válidos e inválidos.

## 2. Adapter Matrix HTTP para join de sala

- [x] 2.1 Adicionar testes unitários para `MatrixHttpClient.join_room(...)`, cobrindo sucesso, erro HTTP e erro de transporte com normalização de exceções.
- [x] 2.2 Implementar método `join_room(room_id)` usando `POST /_matrix/client/v3/rooms/{roomId}/join` no adapter existente.

## 3. Runtime bot-matrix com autoaceite restrito às salas configuradas

- [x] 3.1 Escrever testes unitários de roteamento para garantir autojoin apenas para `ROOM1_ID..ROOM4_ID`, ignore de salas não permitidas e ausência de mutação de fluxo clínico.
- [x] 3.2 Implementar integração do autoaceite no loop de polling do `bot-matrix`, derivando allowlist de `Settings` e mantendo processamento resiliente.
- [x] 3.3 Adicionar logs operacionais: `INFO` para autojoin bem-sucedido e `WARNING` para falha com `room_id` e motivo.

## 4. Robustez de retry e cenários de reentrada

- [x] 4.1 Adicionar testes para retry automático em polls subsequentes quando join falhar e convite permanecer pendente.
- [x] 4.2 Adicionar teste para reaceite após leave/kick seguido de novo convite em sala permitida.

## 5. Documentação operacional e validação final

- [x] 5.1 Atualizar documentação operacional (`docs/` e `docs/en/`) com comportamento de autoaceite de convites para salas configuradas.
- [x] 5.2 Executar validações do slice: `uv run pytest` (alvos), `uv run ruff check` (paths alterados), `uv run mypy` (paths alterados) e `markdownlint-cli2` nos artefatos OpenSpec alterados.
- [x] 5.3 Atualizar checklist do change com evidências de verificação e notas de rollout/rollback.

## Evidências de verificação e notas de rollout/rollback

### Evidências de verificação

- Parser de convites no sync:
  - `uv run pytest tests/unit/test_sync_events.py -q`
- Adapter Matrix HTTP para join:
  - `uv run pytest tests/unit/test_matrix_http_client.py -q`
- Runtime bot-matrix (allowlist, logs, retry e reaceite):
  - `uv run pytest tests/unit/test_bot_matrix_main.py -q`
- Validação consolidada do change:
  - `uv run pytest tests/unit/test_sync_events.py tests/unit/test_matrix_http_client.py tests/unit/test_bot_matrix_main.py -q` → `27 passed`
  - `uv run ruff check apps/bot_matrix/main.py src/triage_automation/infrastructure/matrix/http_client.py src/triage_automation/infrastructure/matrix/sync_events.py tests/unit/test_bot_matrix_main.py tests/unit/test_matrix_http_client.py tests/unit/test_sync_events.py` → sem erros
  - `uv run mypy -m apps.bot_matrix.main` e `uv run mypy src/triage_automation/infrastructure/matrix/http_client.py src/triage_automation/infrastructure/matrix/sync_events.py` → sem erros
  - `markdownlint-cli2` em `proposal.md`, `design.md`, `spec.md` e `tasks.md` do change → sem erros

### Notas de rollout

- Pré-requisitos:
  - `bot-matrix` em execução
  - `MATRIX_ACCESS_TOKEN` válido com permissão para ingressar nas salas convidadas
  - `ROOM1_ID`, `ROOM2_ID`, `ROOM3_ID` e `ROOM4_ID` corretamente configurados no ambiente
- Comportamento esperado após deploy:
  - convites para salas configuradas: autojoin com log `INFO`
  - convites fora da allowlist: ignorados
  - falha de join para sala configurada: log `WARNING` com `room_id` e motivo, com nova tentativa em polls seguintes

### Notas de rollback

- Reverter para versão anterior do `bot-matrix` para desativar autoaceite.
- Mitigação operacional imediata em rollback:
  - aceitar convites manualmente (UI Matrix ou chamada API com token do bot) para salas oficiais.
