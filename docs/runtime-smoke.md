# Runbook de Smoke do Runtime

Idioma: **Português (BR)** | [English](en/runtime-smoke.md)

Este runbook valida prontidão local do runtime antes do teste manual end-to-end.
Ele não altera comportamento do workflow; apenas verifica se processos de runtime,
migrações de banco, prontidão do caminho de decisão Matrix e execução
LLM determinística estão funcionando de forma reproduzível.

## Aviso de caminho de decisão

- decisões padrão da Sala 2 usam respostas estruturadas Matrix.
- envio de decisão por callback/widget HTTP não faz parte da operação de runtime.

## Smoke local com UV

1. Preparar dependências e ambiente:

```bash
uv sync
cp .env.example .env
```

1. Iniciar somente Postgres:

```bash
docker compose up -d postgres
```

1. Aplicar migrações:

```bash
uv run alembic upgrade head
```

1. Iniciar processos em terminais separados:

```bash
uv run uvicorn apps.bot_api.main:create_app --factory --host 0.0.0.0 --port 8000
```

```bash
uv run python -m apps.bot_matrix.main
```

```bash
uv run python -m apps.worker.main
```

Defina `LOG_LEVEL=DEBUG` no `.env` quando precisar de traces estilo heartbeat.
Em `INFO`, logs mostram startup e atividades relevantes de roteamento/claim de job.

1. Verificar alcance da API:

```bash
curl -i http://127.0.0.1:8000/openapi.json
```

## Prontidão de resposta estruturada Matrix

Rode um teste de integração focado no fluxo de resposta estruturada da Sala 2:

```bash
uv run pytest tests/integration/test_room2_reply_flow.py -q
```

Resultado esperado:

- caminhos de parsing/validação de reply na Sala 2 executam com sucesso.
- tratamento de decisão é dirigido por eventos de reply Matrix (sem superfície HTTP de decisão).

## Caminho determinístico de LLM no smoke

Use modo determinístico quando credenciais de provider não estiverem disponíveis:

```bash
export LLM_RUNTIME_MODE=deterministic
```

Nesse modo, o runtime do worker usa adapters LLM determinísticos e ainda executa
estágios dependentes de LLM (`LLM1`/`LLM2`) e transições de enqueue sem mudar a
semântica clínica da triagem.

Para modo provider, defina:

- `OPENAI_API_KEY`
- `OPENAI_MODEL_LLM1`
- `OPENAI_MODEL_LLM2`

## Agendamento do resumo periódico da Room-4

O scheduler de resumo da Room-4 é um processo *one-shot*.
Cada execução calcula a janela anterior de 12h no timezone `America/Bahia`
e enfileira no máximo um job `post_room4_summary`.

Pré-condições operacionais:

- `worker` em execução (consome o job enfileirado)
- variáveis de ambiente configuradas: `ROOM4_ID`, `SUPERVISOR_SUMMARY_TIMEZONE`, `SUPERVISOR_SUMMARY_MORNING_HOUR`, `SUPERVISOR_SUMMARY_EVENING_HOUR`
- migrações aplicadas (`uv run alembic upgrade head`)

Execução manual (validação pontual):

```bash
uv run python -m apps.scheduler.main
```

Comportamento esperado:

- em 07:00 (`America/Bahia`): agenda janela `[19:00 dia anterior, 07:00 dia atual)`
- em 19:00 (`America/Bahia`): agenda janela `[07:00 dia atual, 19:00 dia atual)`
- reexecução da mesma janela não duplica postagem na Room-4 (idempotência por janela)

Exemplo de cron Linux (produção):

```cron
CRON_TZ=America/Bahia
0 7,19 * * * cd /srv/triage-automation && /usr/local/bin/uv run python -m apps.scheduler.main >> /var/log/ats-room4-scheduler.log 2>&1
```

## Paridade UV e Compose

Use os mesmos comandos de entrypoint definidos em `docker-compose.yml`:

```bash
docker compose up --build
docker compose logs -f bot-api bot-matrix worker
```

Paridade de comandos no Compose:

- `bot-api`: `uv run uvicorn apps.bot_api.main:create_app --factory --host 0.0.0.0 --port 8000`
- `bot-matrix`: `uv run python -m apps.bot_matrix.main`
- `worker`: `uv run python -m apps.worker.main`
