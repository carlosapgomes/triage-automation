# Guia de Setup

Idioma: **Português (BR)** | [English](en/setup.md)

## Pré-requisitos

- Python `3.12.x`
- `uv`
- Docker + Docker Compose (opcional, mas recomendado para stack local)

## 1. Instalar dependências

```bash
uv sync
```

## 2. Criar arquivo local de ambiente

```bash
cp .env.example .env
```

Variáveis principais para runtime Matrix-only de decisão:

- `ROOM1_ID`
- `ROOM2_ID`
- `ROOM3_ID`
- `MATRIX_HOMESERVER_URL`
- `DATABASE_URL`
- `LLM_RUNTIME_MODE`
- `LOG_LEVEL`
- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`

Para o contrato completo de ambiente, revise `.env.example`.

Variáveis opcionais para modo provider:

- `OPENAI_API_KEY`
- `OPENAI_MODEL_LLM1`
- `OPENAI_MODEL_LLM2`
- `OPENAI_TIMEOUT_SECONDS` (padrão: 60; aumente para PDFs grandes)

Variáveis opcionais para bootstrap do primeiro admin:

- `BOOTSTRAP_ADMIN_EMAIL`
- `BOOTSTRAP_ADMIN_PASSWORD` ou `BOOTSTRAP_ADMIN_PASSWORD_FILE` (definir apenas uma)

Comportamento de bootstrap:

- Executado pelo `bot-api` no startup
- Cria usuário inicial `admin` apenas quando a tabela `users` estiver vazia
- Se já existirem usuários, o bootstrap é ignorado
- `BOOTSTRAP_ADMIN_PASSWORD_FILE` é recomendado em ambientes mais próximos de produção

## 3. Executar migrações de banco

```bash
uv run alembic upgrade head
```

## 4. Executar testes e quality gates

```bash
uv run ruff check .
uv run mypy src apps
uv run pytest -q
```

## 5. Fluxo web de login/logout

Depois das migrações e startup dos serviços, use o portal direto no navegador.

1. Abra página raiz:

- URL: `http://localhost:8000/`
- esperado para usuário anônimo: redirect para `/login`

1. Login:

- envie `email` + `password` em `GET /login`
- sucesso esperado: redirect para `/dashboard/cases`
- credenciais inválidas: erro HTML na página de login, sem cookie de sessão

1. Autorização por papel:

- `reader`: acessa páginas de dashboard, não acessa páginas admin de prompts
- `admin`: acessa páginas de dashboard e páginas admin de prompts

1. Logout:

- envie `POST /logout` (botão `Sair` no cabeçalho)
- resultado esperado: redirect para `/login` e cookie de sessão limpo

## 6. Subir stack local (opcional)

```bash
docker compose up --build
```

## 7. Validação de smoke do runtime (recomendado antes do E2E manual)

Siga `docs/runtime-smoke.md` para validar:

- startup local dos processos com `uv`
- prontidão de respostas estruturadas Matrix para decisões da Sala 2
- modo determinístico de runtime LLM para testes sem provider

## 8. Operações de admin

### 8.1 Reset de senha admin (CLI)

Use este fluxo quando uma senha de admin precisar de rotação ou recuperação.
Ele atualiza o hash bcrypt diretamente em `users` usando o `DATABASE_URL` configurado.

1. Defina identidade alvo e nova senha:

```bash
export ADMIN_EMAIL=admin@example.org
export ADMIN_NEW_PASSWORD='change-me-now'
```

1. Aplique reset:

```bash
uv run python - <<'PY'
import asyncio
import os
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine
from triage_automation.config.settings import load_settings
from triage_automation.infrastructure.security.password_hasher import BcryptPasswordHasher

email = os.environ["ADMIN_EMAIL"].strip().lower()
new_password = os.environ["ADMIN_NEW_PASSWORD"]
if not email:
    raise SystemExit("ADMIN_EMAIL cannot be blank")
if not new_password.strip():
    raise SystemExit("ADMIN_NEW_PASSWORD cannot be blank")

settings = load_settings()
engine = create_async_engine(settings.database_url)
hasher = BcryptPasswordHasher()
password_hash = hasher.hash_password(new_password)

async def main() -> None:
    async with engine.begin() as conn:
        result = await conn.execute(
            sa.text(
                "UPDATE users "
                "SET password_hash = :password_hash, updated_at = CURRENT_TIMESTAMP "
                "WHERE lower(email) = :email AND role = 'admin' AND is_active = true"
            ),
            {"password_hash": password_hash, "email": email},
        )
    await engine.dispose()
    if result.rowcount == 0:
        raise SystemExit("No active admin user found for ADMIN_EMAIL")
    print("Admin password updated successfully")

asyncio.run(main())
PY
```

1. Verifique via login:

- `POST /auth/login` com o mesmo `ADMIN_EMAIL` e a nova senha
- resultado esperado: `200` com payload de token

### 8.2 Reset de senha admin (Docker Compose)

Use este fluxo quando a stack estiver em containers e você preferir não usar Python no host.

1. Garanta que `bot-api` esteja em execução:

```bash
docker compose up -d postgres bot-api
```

1. Defina identidade alvo e nova senha:

```bash
export ADMIN_EMAIL=admin@example.org
export ADMIN_NEW_PASSWORD='change-me-now'
```

1. Aplique reset de dentro do container `bot-api`:

```bash
docker compose exec -T \
  -e ADMIN_EMAIL="$ADMIN_EMAIL" \
  -e ADMIN_NEW_PASSWORD="$ADMIN_NEW_PASSWORD" \
  bot-api \
  uv run python - <<'PY'
import asyncio
import os
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine
from triage_automation.config.settings import load_settings
from triage_automation.infrastructure.security.password_hasher import BcryptPasswordHasher

email = os.environ["ADMIN_EMAIL"].strip().lower()
new_password = os.environ["ADMIN_NEW_PASSWORD"]
if not email:
    raise SystemExit("ADMIN_EMAIL cannot be blank")
if not new_password.strip():
    raise SystemExit("ADMIN_NEW_PASSWORD cannot be blank")

settings = load_settings()
engine = create_async_engine(settings.database_url)
hasher = BcryptPasswordHasher()
password_hash = hasher.hash_password(new_password)

async def main() -> None:
    async with engine.begin() as conn:
        result = await conn.execute(
            sa.text(
                "UPDATE users "
                "SET password_hash = :password_hash, updated_at = CURRENT_TIMESTAMP "
                "WHERE lower(email) = :email AND role = 'admin' AND is_active = true"
            ),
            {"password_hash": password_hash, "email": email},
        )
    await engine.dispose()
    if result.rowcount == 0:
        raise SystemExit("No active admin user found for ADMIN_EMAIL")
    print("Admin password updated successfully")

asyncio.run(main())
PY
```

1. Verifique via login:

- `POST /auth/login` com o mesmo `ADMIN_EMAIL` e a nova senha
- resultado esperado: `200` com payload de token

## Comandos comuns

- Criar migração:

```bash
uv run alembic revision -m "describe-change"
```

- Aplicar migração mais recente:

```bash
uv run alembic upgrade head
```

- Reverter uma migração:

```bash
uv run alembic downgrade -1
```
