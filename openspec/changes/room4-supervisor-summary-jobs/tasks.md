# Tasks

## 1. Configuração e contratos do novo fluxo de resumo

- [x] 1.1 Adicionar testes para falhar (red) ao exigir configuração de Room-4 no `Settings` e validar timezone `America/Bahia` para o fluxo de resumo.
- [x] 1.2 Implementar configurações necessárias (`ROOM4_ID` e parâmetros de resumo) em `settings.py` e `.env.example` com tipagem/docstrings alinhadas ao padrão do projeto.
- [x] 1.3 Validar wiring inicial para permitir o novo `job_type` `post_room4_summary` no runtime sem alterar semânticas existentes.

## 2. Persistência de idempotência e trilha de despacho

- [x] 2.1 Criar testes de infraestrutura para garantir unicidade por `(room_id, window_start, window_end)` no controle de dispatch de resumo.
- [x] 2.2 Criar migração e metadata para tabela de dispatch de resumo com colunas de janela, status, `sent_at`, `matrix_event_id` e erro.
- [x] 2.3 Implementar repositório/porta de dispatch com operações atômicas de claim/registro de sucesso para suportar reexecução sem duplicidade.

## 3. Scheduler de enfileiramento (07:00/19:00 America/Bahia)

- [x] 3.1 Escrever testes unitários para cálculo de janela determinística às 07:00 e 19:00 (intervalos de 12h, formato `[start, end)`).
- [x] 3.2 Implementar serviço de scheduler que calcula a janela local e enfileira `post_room4_summary` com payload canônico em UTC.
- [x] 3.3 Criar entrypoint de scheduler (CLI/processo curto) e validar execução manual idempotente para mesma janela.

## 4. Execução no worker e postagem na Room-4

- [x] 4.1 Adicionar testes para o novo handler `post_room4_summary` no mapa de handlers do worker, incluindo integração com retry existente.
- [x] 4.2 Implementar serviço de aplicação que monta o resumo, consulta métricas e publica mensagem no Matrix Room-4.
- [x] 4.3 Implementar proteção de idempotência no caminho de publicação para não enviar segunda mensagem quando a janela já tiver dispatch bem-sucedido.

## 5. Consolidação das métricas obrigatórias do resumo

- [x] 5.1 Escrever testes de consulta/serviço para `pacientes recebidos`, `relatórios processados` e `casos avaliados` dentro da janela.
- [x] 5.2 Escrever testes para semântica de desfecho final: `aceitos` por confirmação de agendamento e `recusados` por negação médica ou negativa de agendamento.
- [x] 5.3 Implementar consultas SQLAlchemy e composição final de métricas com timestamps da janela e timezone de referência no texto.

## 6. Qualidade, documentação operacional e fechamento do change

- [ ] 6.1 Atualizar documentação operacional necessária para agendamento do scheduler (07:00/19:00 em `America/Bahia`) e sincronizar espelho `docs/en/` se houver alteração em `docs/`.
- [ ] 6.2 Executar validações do slice: `uv run pytest` (alvos), `uv run ruff check` (paths alterados), `uv run mypy` (paths alterados) e `markdownlint-cli2` nos artefatos OpenSpec alterados.
- [ ] 6.3 Atualizar checklist final do OpenSpec com evidências de verificação e observações de rollout/rollback.
