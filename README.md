# Augmented Triage System (ATS)

Idioma: **Português (BR)** | [English](README.en.md)

Augmented Triage System (ATS) é um serviço de backend projetado para apoiar fluxos reais de triagem clínica, mantendo profissionais de saúde totalmente no controle das decisões e do cuidado ao paciente.

O ATS não substitui o julgamento clínico nem automatiza decisões médicas.
O sistema foi projetado para apoiar comunicação, organização e fluxo de informações durante a triagem, permitindo que profissionais trabalhem com mais segurança e eficiência em ambientes de alta demanda.

O objetivo principal do ATS é melhorar coordenação, rastreabilidade e consciência situacional durante processos de triagem.

O ATS é uma ferramenta de apoio para equipes de saúde e deve sempre ser utilizado sob supervisão profissional e dentro de protocolos clínicos estabelecidos.

![Python](https://img.shields.io/badge/python-3.12-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Lint](https://img.shields.io/badge/lint-ruff-orange.svg)
![Type Check](https://img.shields.io/badge/types-mypy-blue.svg)
![Tests](https://img.shields.io/badge/tests-pytest-brightgreen.svg)

Serviços de backend para um fluxo de triagem orientado a eventos em salas Matrix.

Serviços principais:

- `bot-api` (fundação de autenticação e runtime com FastAPI)
- `bot-matrix` (integração de ingestão de eventos Matrix)
- `worker` (runtime de execução de jobs)

Este repositório é implementado com TDD estrito e histórico de slices OpenSpec em `openspec/changes/archive/`.

## Por Que Este Projeto

- Automatiza fluxo de triagem em múltiplas etapas entre salas Matrix.
- Preserva auditabilidade com registros append-only.
- Usa transições de estado determinísticas e jobs em fila.
- Adiciona fundações administrativas (roles, auth e prompts) sem introduzir comportamento de UI no runtime clínico.

## Escopo Atual

- A fundação do fluxo de triagem está implementada e coberta por testes automatizados.
- A superfície administrativa e de monitoramento está disponível no `bot-api`:
  - fluxo web de sessão (`GET /`, `GET /login`, `POST /login`, `POST /logout`)
  - login/auth (`/auth/login`)
  - API de monitoramento (`/monitoring/cases`, `/monitoring/cases/{case_id}`)
  - dashboard server-rendered (`/dashboard/cases`, `/dashboard/cases/{case_id}`)
  - admin de prompts server-rendered (`GET /admin/prompts`, `POST /admin/prompts/{prompt_name}/activate-form`)
  - API de administração de prompts (`/admin/prompts/*`)

## Topologia de Runtime

```text
Matrix Rooms ---> bot-matrix ----\
                                  \
Login/Auth ----------> bot-api ----> PostgreSQL <---- worker
```

## Superficie Publica (Atual)

Páginas web e rotas de sessão:

- `GET /`
- `GET /login`
- `POST /login`
- `POST /logout`
- `GET /dashboard/cases`
- `GET /dashboard/cases/{case_id}`
- `GET /admin/prompts`
- `POST /admin/prompts/{prompt_name}/activate-form`

Rotas de API JSON:

- `POST /auth/login`
- `GET /monitoring/cases`
- `GET /monitoring/cases/{case_id}`
- `GET /admin/prompts/versions`
- `GET /admin/prompts/{prompt_name}/active`
- `POST /admin/prompts/{prompt_name}/activate`

## Acesso Web e Papéis

Fluxo de acesso pelo navegador:

1. Abra `/` no navegador.
1. Acesso anônimo é redirecionado para `/login`.
1. Envie email e senha no formulário de login.
1. Em caso de sucesso, o app redireciona para `/dashboard/cases`.
1. Use `Sair` (`POST /logout`) para encerrar a sessão.

Matriz de papéis:

| Papel | Paginas de dashboard | Paginas admin de prompt | APIs admin de prompt |
| --- | --- | --- | --- |
| `reader` | permitido | proibido (`403`) | proibido (`403`) |
| `admin` | permitido | permitido | permitido |

## Documentação do Projeto

- Setup: `docs/setup.md`
- Operações admin (bootstrap + reset de senha): `docs/setup.md#7-admin-operations`
- Runbook de smoke de runtime: `docs/runtime-smoke.md`
- Arquitetura: `docs/architecture.md`
- Seguranca: `docs/security.md`
- Contexto interno de implementação: `PROJECT_CONTEXT.md`

## Checklist de contribuição da documentação bilíngue

1. Alterou `README.md`? Atualize `README.en.md` no mesmo PR.
1. Alterou `docs/<arquivo>.md`? Atualize `docs/en/<arquivo>.md` no mesmo PR.
1. Mantenha os seletores de idioma no topo dos dois arquivos espelhados.
1. Execute:

```bash
uv run pytest tests/unit/test_readme_bilingual_baseline.py tests/unit/test_docs_bilingual_mirror.py -q
markdownlint-cli2 "README.md" "README.en.md" "docs/*.md" "docs/en/*.md"
```

## Estrutura do Repositório

```text
apps/                         # Entrypoints de runtime (bot-api, bot-matrix, worker)
src/triage_automation/        # Código de application/domain/infrastructure
alembic/                      # Migrações de banco
tests/                        # Testes unitários, integração e e2e
docs/                         # Documentação pública do projeto
openspec/                     # Artefatos de change/spec
```

## Início Rápido

1. Instale dependências:

```bash
uv sync
```

1. Crie arquivo de ambiente local:

```bash
cp .env.example .env
```

1. Execute migrações de banco:

```bash
uv run alembic upgrade head
```

1. Opcional: bootstrap do primeiro admin no startup (uma vez, quando `users` estiver vazio):

```bash
export BOOTSTRAP_ADMIN_EMAIL=admin@example.org
export BOOTSTRAP_ADMIN_PASSWORD='change-me-now'
```

Para ambientes mais próximos de produção, prefira `BOOTSTRAP_ADMIN_PASSWORD_FILE`.

1. Execute quality gates locais:

```bash
uv run ruff check .
uv run mypy src apps
uv run pytest -q
```

## Serviços Locais (Docker Compose)

```bash
docker compose up --build
```

O Compose espera `.env` presente e inicia:

- `postgres`
- `bot-api`
- `bot-matrix`
- `worker`

## Nota de Deploy

Este repositório está otimizado atualmente para deploy local/dev com Docker Compose.
Para deploy em produção, adicione hardening específico de ambiente (integração com secret manager,
política de rede, terminação TLS e observabilidade).

## CI

Quality gates são aplicados em `.github/workflows/quality-gates.yml`.

## Licença

MIT. Veja `LICENSE`.

## Créditos

Este projeto foi desenvolvido com assistência de modelos de linguagem de grande porte (LLMs).
