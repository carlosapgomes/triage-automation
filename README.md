# Augmented Triage System (ATS)

Idioma: **Portugues (BR)** | [English](README.en.md)

Augmented Triage System (ATS) e um servico de backend projetado para apoiar fluxos reais de triagem clinica, mantendo profissionais de saude totalmente no controle das decisoes e do cuidado ao paciente.

O ATS nao substitui o julgamento clinico nem automatiza decisoes medicas.
O sistema foi projetado para apoiar comunicacao, organizacao e fluxo de informacoes durante a triagem, permitindo que profissionais trabalhem com mais seguranca e eficiencia em ambientes de alta demanda.

O objetivo principal do ATS e melhorar coordenacao, rastreabilidade e consciencia situacional durante processos de triagem.

O ATS e uma ferramenta de apoio para equipes de saude e deve sempre ser utilizado sob supervisao profissional e dentro de protocolos clinicos estabelecidos.

![Python](https://img.shields.io/badge/python-3.12-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Lint](https://img.shields.io/badge/lint-ruff-orange.svg)
![Type Check](https://img.shields.io/badge/types-mypy-blue.svg)
![Tests](https://img.shields.io/badge/tests-pytest-brightgreen.svg)

Servicos de backend para um fluxo de triagem orientado a eventos em salas Matrix.

Servicos principais:

- `bot-api` (fundacao de autenticacao e runtime com FastAPI)
- `bot-matrix` (integracao de ingestao de eventos Matrix)
- `worker` (runtime de execucao de jobs)

Este repositorio e implementado com TDD estrito e historico de slices OpenSpec em `openspec/changes/archive/`.

## Por Que Este Projeto

- Automatiza fluxo de triagem em multiplas etapas entre salas Matrix.
- Preserva auditabilidade com registros append-only.
- Usa transicoes de estado deterministicas e jobs em fila.
- Adiciona fundacoes administrativas (roles, auth e prompts) sem introduzir comportamento de UI no runtime clinico.

## Escopo Atual

- A fundacao do fluxo de triagem esta implementada e coberta por testes automatizados.
- A superficie administrativa e de monitoramento esta disponivel no `bot-api`:
  - fluxo web de sessao (`GET /`, `GET /login`, `POST /login`, `POST /logout`)
  - login/auth (`/auth/login`)
  - API de monitoramento (`/monitoring/cases`, `/monitoring/cases/{case_id}`)
  - dashboard server-rendered (`/dashboard/cases`, `/dashboard/cases/{case_id}`)
  - admin de prompts server-rendered (`GET /admin/prompts`, `POST /admin/prompts/{prompt_name}/activate-form`)
  - API de administracao de prompts (`/admin/prompts/*`)

## Topologia de Runtime

```text
Matrix Rooms ---> bot-matrix ----\
                                  \
Login/Auth ----------> bot-api ----> PostgreSQL <---- worker
```

## Superficie Publica (Atual)

Paginas web e rotas de sessao:

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

## Acesso Web e Papeis

Fluxo de acesso pelo navegador:

1. Abra `/` no navegador.
1. Acesso anonimo e redirecionado para `/login`.
1. Envie email e senha no formulario de login.
1. Em caso de sucesso, o app redireciona para `/dashboard/cases`.
1. Use `Sair` (`POST /logout`) para encerrar a sessao.

Matriz de papeis:

| Papel | Paginas de dashboard | Paginas admin de prompt | APIs admin de prompt |
| --- | --- | --- | --- |
| `reader` | permitido | proibido (`403`) | proibido (`403`) |
| `admin` | permitido | permitido | permitido |

## Documentacao do Projeto

- Setup: `docs/setup.md`
- Operacoes admin (bootstrap + reset de senha): `docs/setup.md#7-admin-operations`
- Runbook de smoke de runtime: `docs/runtime-smoke.md`
- Arquitetura: `docs/architecture.md`
- Seguranca: `docs/security.md`
- Contexto interno de implementacao: `PROJECT_CONTEXT.md`

## Checklist de contribuicao da documentacao bilingue

1. Alterou `README.md`? Atualize `README.en.md` no mesmo PR.
1. Alterou `docs/<arquivo>.md`? Atualize `docs/en/<arquivo>.md` no mesmo PR.
1. Mantenha os seletores de idioma no topo dos dois arquivos espelhados.
1. Execute:

```bash
uv run pytest tests/unit/test_readme_bilingual_baseline.py tests/unit/test_docs_bilingual_mirror.py -q
markdownlint-cli2 "README.md" "README.en.md" "docs/*.md" "docs/en/*.md"
```

## Estrutura do Repositorio

```text
apps/                         # Entrypoints de runtime (bot-api, bot-matrix, worker)
src/triage_automation/        # Codigo de application/domain/infrastructure
alembic/                      # Migracoes de banco
tests/                        # Testes unitarios, integracao e e2e
docs/                         # Documentacao publica do projeto
openspec/                     # Artefatos de change/spec
```

## Inicio Rapido

1. Instale dependencias:

```bash
uv sync
```

1. Crie arquivo de ambiente local:

```bash
cp .env.example .env
```

1. Execute migracoes de banco:

```bash
uv run alembic upgrade head
```

1. Opcional: bootstrap do primeiro admin no startup (uma vez, quando `users` estiver vazio):

```bash
export BOOTSTRAP_ADMIN_EMAIL=admin@example.org
export BOOTSTRAP_ADMIN_PASSWORD='change-me-now'
```

Para ambientes mais proximos de producao, prefira `BOOTSTRAP_ADMIN_PASSWORD_FILE`.

1. Execute quality gates locais:

```bash
uv run ruff check .
uv run mypy src apps
uv run pytest -q
```

## Servicos Locais (Docker Compose)

```bash
docker compose up --build
```

O Compose espera `.env` presente e inicia:

- `postgres`
- `bot-api`
- `bot-matrix`
- `worker`

## Nota de Deploy

Este repositorio esta otimizado atualmente para deploy local/dev com Docker Compose.
Para deploy em producao, adicione hardening especifico de ambiente (integracao com secret manager,
politica de rede, terminacao TLS e observabilidade).

## CI

Quality gates sao aplicados em `.github/workflows/quality-gates.yml`.

## Licenca

MIT. Veja `LICENSE`.

## Creditos

Este projeto foi desenvolvido com assistencia de modelos de linguagem de grande porte (LLMs).
