# Runbook Manual E2E

Idioma: **Português (BR)** | [English](en/manual_e2e_runbook.md)

Este runbook valida ponta a ponta o caminho de resposta Matrix estruturada da Sala 2 em ambiente local determinístico.
Execute `docs/runtime-smoke.md` antes para confirmar startup de processo e alcance de callback.

## Pré-requisitos

1. Inicie os processos de runtime com os mesmos comandos usados em `docs/runtime-smoke.md`:

```bash
uv run uvicorn apps.bot_api.main:create_app --factory --host 0.0.0.0 --port 8000
uv run python -m apps.bot_matrix.main
uv run python -m apps.worker.main
```

1. Use um caso de teste já movido para `WAIT_DOCTOR` com contexto de caso na Sala 2 postado pelo bot.

## Checagens de login web e menu por papel

1. Acesso anônimo no navegador:

- abrir `GET /`
- esperado: redirect para `/login`

1. Checagens de sessão `reader`:

- login como usuário `reader` via formulário `POST /login`
- verificar `GET /dashboard/cases` retorna `200`
- verificar shell nav contém `Dashboard`
- verificar shell nav não contém `Prompts`
- verificar `GET /admin/prompts` retorna `403`

1. Checagens de sessão `admin`:

- login como usuário `admin` via formulário `POST /login`
- verificar `GET /dashboard/cases` retorna `200`
- verificar shell nav contém `Dashboard` e `Prompts`
- verificar `GET /admin/prompts` retorna `200` com lista e controles de ativação

1. Logout:

- enviar `POST /logout` no cabeçalho da shell
- esperado: redirect para `/login`
- verificar que um novo `GET /` redireciona para `/login`

## Caminho positivo de resposta estruturada da Sala 2

1. Validar o combo de três mensagens da Sala 2 para o caso alvo em clientes desktop e mobile:

- message I: contexto original do PDF
- message II: dados extraídos + resumo + recomendação (reply para message I)
- message III: instruções de template estrito (reply para message I)
- verificar em desktop e mobile que mensagens permanecem agrupadas sob message I

1. Abrir message III e copiar o template estrito.

1. Enviar decisão como reply Matrix para message I (reply to message I):

- incluir campos do template exatamente:
  - `decision: accept|deny`
  - `support_flag: none|anesthesist|anesthesist_icu`
  - `reason: <texto livre ou vazio>`
  - `case_id: <case-id>`

1. Para validação do fluxo positivo, enviar:

- `decision: accept`
- `support_flag: none`
- `reason` opcional

1. Validar progressão esperada:

- status do caso move para `DOCTOR_ACCEPTED`
- próximo job `post_room3_request` é enfileirado
- auditoria inclui sender Matrix como ator e outcome

## Checagens negativas de auth do widget

1. Enviar sem Authorization header (without Authorization):

- `POST /widget/room2/submit`
- esperado: `401`

1. Enviar com token de papel reader (reader role token):

- `POST /widget/room2/submit`
- esperado: `403`

1. Validar ausência de mutação inesperada de estado/job (state/job mutation):

- status do caso não muda
- nenhum job adicional de decisão é enfileirado
- apenas registros esperados de auth/auditoria são adicionados

## Checagens negativas de reply da Sala 2

1. Postar reply com template malformado (malformed template):

- reply para message I com linhas obrigatórias ausentes/inválidas
- esperado: feedback do bot inclui `error_code: invalid_template`
- esperado: no decision mutation e nenhum novo downstream job enfileirado

1. Postar template valido no parent de reply errado (wrong reply-parent):

- enviar template como reply para message II/III ou evento não relacionado (não message I root)
- esperado: feedback do bot inclui `error_code: invalid_template`
- esperado: no decision mutation e nenhum novo downstream job enfileirado

## Checagens de dashboard e API de monitoramento

1. Abrir listagem de dashboard server-rendered no navegador:

- `GET /dashboard/cases` com bearer token valido
- esperado: lista HTML renderiza casos e filtros

1. Validar API de listagem de monitoramento:

- `GET /monitoring/cases`
- esperado: `200` com JSON contendo `items`, `page`, `page_size`, `total`

1. Validar API de detalhe por caso e eventos auditáveis:

- `GET /monitoring/cases/{case_id}`
- esperado: `200` com chronological timeline ordenada por `timestamp`
- timeline deve incluir `source`, `channel`, `actor`, `event_type`
- quando aplicável, validar presença de eventos ACK e human reply

1. Cruzar API com detalhe do dashboard:

- abrir `GET /dashboard/cases/{case_id}`
- verificar timeline cronológica visível na UI igual a API de monitoramento para o mesmo caso

## Fluxo de autorização de gerenciamento de prompts

1. Usando token de reader (reader token), verificar comportamento read-only:

- `GET /monitoring/cases` retorna `200`
- `GET /admin/prompts/versions` retorna `403`
- `GET /admin/prompts/{prompt_name}/active` retorna `403`
- `POST /admin/prompts/{prompt_name}/activate` retorna `403`

1. Usando token de admin (admin token), verificar mutação de prompts:

- `GET /admin/prompts/versions` retorna `200`
- `GET /admin/prompts/{prompt_name}/active` retorna `200`
- `POST /admin/prompts/{prompt_name}/activate` retorna `200`

1. Validar efeitos colaterais de ativação de prompt:

- exatamente uma versão ativa permanece para o nome do prompt
- auditoria auth inclui `prompt_version_activated` com ator e prompt/version alvo

1. Validar ativação de prompt via formulário HTML (sessão admin):

- abrir `GET /admin/prompts`
- enviar formulário `POST /admin/prompts/{prompt_name}/activate-form`
- esperado: redirect para `/admin/prompts` com feedback de ativação
- validar última linha em `auth_events` com `event_type=prompt_version_activated`

## Fluxo de autorização de gerenciamento de usuários

1. Usando token de `reader` (reader token), validar bloqueio de acesso:

- `GET /admin/users` retorna `403`
- `POST /admin/users` retorna `403`
- `POST /admin/users/{user_id}/block` retorna `403`
- `POST /admin/users/{user_id}/activate` retorna `403`
- `POST /admin/users/{user_id}/remove` retorna `403`
- esperado: sem mutação de contas de usuário

1. Usando sessão `admin`, validar criação de conta:

- abrir `GET /admin/users`
- enviar formulário `POST /admin/users` para criar um `reader`
- esperado: redirect para `/admin/users` com feedback `Usuario criado`
- validar que o novo usuário aparece na listagem com estado `active`

1. Usando sessão `admin`, validar bloqueio de conta ativa:

- enviar `POST /admin/users/{user_id}/block` para usuário alvo `active`
- esperado: redirect para `/admin/users` com feedback de atualização
- validar na listagem que o usuário alvo muda para estado `blocked`
- validar `POST /auth/login` com credenciais do usuário alvo retorna `403` (`inactive user`)

1. Usando sessão `admin`, validar reativação de conta bloqueada:

- enviar `POST /admin/users/{user_id}/activate` para usuário alvo `blocked`
- esperado: redirect para `/admin/users` com feedback de atualização
- validar na listagem que o usuário alvo volta para estado `active`
- validar `POST /auth/login` com credenciais do usuário alvo retorna `200`

1. Usando sessão `admin`, validar remoção administrativa (soft delete):

- enviar `POST /admin/users/{user_id}/remove` para usuário alvo
- esperado: redirect para `/admin/users` com feedback de atualização
- validar na listagem que o usuário alvo muda para estado `removed`
- validar `POST /auth/login` com credenciais do usuário alvo retorna `403` (`inactive user`)
