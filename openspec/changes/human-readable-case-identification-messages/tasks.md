# Tasks

## 1. Contrato de mensagens e dados de identificação

- [x] 1.1 Mapear e classificar templates Room-1/2/3 em `estrutural` (UUID obrigatório) vs `informativo` (UUID não obrigatório) e documentar a classificação em comentários/testes de contrato.
- [x] 1.2 Padronizar helper reutilizável para bloco textual de identificação humana (`no. ocorrência` e `paciente`) com fallback `não detectado`.
- [x] 1.3 Garantir que o fluxo de Room-2 obtenha `patient_name` de forma consistente a partir de `structured_data_json`, alinhado com o helper já usado em Room-1/3.

## 2. Atualização de templates e filename por sala

- [x] 2.1 Atualizar templates informativos de Room-2 para substituir destaque de UUID por bloco humano, mantendo UUID apenas onde o contrato estrutural exigir.
- [x] 2.2 Atualizar templates de Room-3 (mensagem de solicitação, ACK e re-prompt/template estrito) aplicando a política dual: bloco humano em todas e UUID preservado nas mensagens estruturais.
- [x] 2.3 Atualizar templates finais de Room-1 para priorizar `no. ocorrência` e `paciente` no topo com fallback `não detectado`.
- [x] 2.4 Alterar geração de filename de anexo PDF da Room-2 para `ocorrencia-<agency_record_number>-caso-<uuid>-relatorio-original.pdf` com fallback `ocorrencia-indisponivel-caso-<uuid>-relatorio-original.pdf`.
- [x] 2.5 Incluir `no. ocorrência` e `paciente` no template estrutural de resposta do médico (Room-2), preservando `caso: <uuid>` para o parser.

## 3. Testes e validação

- [x] 3.1 Atualizar testes unitários de `message_templates` para cobrir bloco humano, fallback `não detectado`, preservação de UUID em templates estruturais e remoção de UUID como identificador principal em mensagens informativas.
- [x] 3.2 Atualizar testes de integração dos fluxos Room-1/2/3 para refletir novo conteúdo textual e novo padrão de filename do PDF da Room-2.
- [x] 3.3 Executar verificações obrigatórias do slice (`uv run pytest` alvo, `uv run ruff check` caminhos alterados, `uv run mypy` caminhos alterados, `markdownlint-cli2` nos artefatos OpenSpec alterados) e registrar qualquer limitação.

## Notes

- Verificação de markdown foi executada com sucesso: `markdownlint-cli2 "openspec/changes/human-readable-case-identification-messages/tasks.md"` retornou `0 error(s)`.
- Slice 2.5 validado com `uv run pytest` (alvos unitários + integração), `uv run ruff check`, `uv run mypy` e `markdownlint-cli2` sem erros.
- Follow-up operacional (2026-03-01): corrigido `HandleDoctorDecisionService` para propagar `agency_record_number` e `patient_name` (extraído de `structured_data_json`) no `build_room2_decision_ack_message`, eliminando fallback indevido `não detectado` no ACK final da Sala 2 quando os dados já existem no caso.
- Cobertura adicionada em integração: `test_runtime_listener_includes_human_identification_in_room2_ack_when_available` em `tests/integration/test_room2_reply_flow.py`.
