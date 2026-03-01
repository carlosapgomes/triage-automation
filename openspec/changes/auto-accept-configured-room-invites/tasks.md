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
- [ ] 5.2 Executar validações do slice: `uv run pytest` (alvos), `uv run ruff check` (paths alterados), `uv run mypy` (paths alterados) e `markdownlint-cli2` nos artefatos OpenSpec alterados.
- [ ] 5.3 Atualizar checklist do change com evidências de verificação e notas de rollout/rollback.
