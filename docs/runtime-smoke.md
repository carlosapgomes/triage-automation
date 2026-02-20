# Runbook de Smoke do Runtime

Idioma: **Portugues (BR)** | [English](en/runtime-smoke.md)

Este runbook valida prontidao local do runtime antes do teste manual end-to-end.
Ele nao altera comportamento do workflow; apenas verifica se processos de runtime,
migracoes de banco, prontidao do caminho de decisao Matrix e execucao
LLM deterministica estao funcionando de forma reproduzivel.

## Aviso de caminho de decisao

- decisoes padrao da Sala 2 usam respostas estruturadas Matrix.
- envio de decisao por callback/widget HTTP nao faz parte da operacao de runtime.

## Smoke local com UV

1. Preparar dependencias e ambiente:

```bash
uv sync
cp .env.example .env
```

1. Iniciar somente Postgres:

```bash
docker compose up -d postgres
```

1. Aplicar migracoes:

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

## Prontidao de resposta estruturada Matrix

Rode um teste de integracao focado no fluxo de resposta estruturada da Sala 2:

```bash
uv run pytest tests/integration/test_room2_reply_flow.py -q
```

Resultado esperado:

- caminhos de parsing/validacao de reply na Sala 2 executam com sucesso.
- tratamento de decisao e dirigido por eventos de reply Matrix (sem superficie HTTP de decisao).

## Caminho deterministico de LLM no smoke

Use modo deterministico quando credenciais de provider nao estiverem disponiveis:

```bash
export LLM_RUNTIME_MODE=deterministic
```

Nesse modo, o runtime do worker usa adapters LLM deterministicos e ainda executa
estagios dependentes de LLM (`LLM1`/`LLM2`) e transicoes de enqueue sem mudar a
semantica clinica da triagem.

Para modo provider, defina:

- `OPENAI_API_KEY`
- `OPENAI_MODEL_LLM1`
- `OPENAI_MODEL_LLM2`

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
