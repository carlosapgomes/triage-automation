# Arquitetura

Idioma: **Português (BR)** | [English](en/architecture.md)

## Visão Geral

O sistema é dividido em três apps deployáveis mais PostgreSQL:

- `bot-api`: ingress HTTP para fundação de login/auth e endpoints de suporte de runtime.
- `bot-matrix`: integração Matrix para eventos de intake/reação.
- `worker`: consumidor async de fila para extração, jobs LLM, postagem e cleanup.
- `postgres`: fonte de verdade para casos, jobs, mapeamento de mensagens e trilha de auditoria.

## Camadas e direção de dependência

O código segue esta direção de dependência:

- adapters (`apps`, `infrastructure/http`, `infrastructure/matrix`)
- serviços e portas de aplicação (`src/triage_automation/application`)
- dominio (`src/triage_automation/domain`)
- implementacoes de infraestrutura (`src/triage_automation/infrastructure`)

Regras:

- lógica de negócio pertence a `application` e `domain`
- adapters devem permanecer enxutos
- detalhes de infraestrutura são consumidos via portas

## Módulos principais

- Settings: `src/triage_automation/config/settings.py`
- Metadata de banco: `src/triage_automation/infrastructure/db/metadata.py`
- Job queue: `src/triage_automation/infrastructure/db/job_queue_repository.py`
- Rota de auth/login: `src/triage_automation/infrastructure/http/auth_router.py`
- Montagem do runtime Bot API: `apps/bot_api/main.py`

## Notas do workflow

- O ciclo de vida da triagem é dirigido por máquina de estados (veja `PROJECT_CONTEXT.md` para estados canônicos).
- O caminho de decisão médica da Sala 2 é somente por resposta estruturada Matrix.
- O cleanup é disparado pela primeira reação de thumbs-up na resposta final da Sala 1.
- O monitoramento inclui API e páginas server-rendered de dashboard no `bot-api`.
- O gerenciamento de prompts segue com acesso de `admin` na superfície administrativa.

## Modelo de persistência (alto nível)

- `cases`: ciclo de vida do caso e artefatos
- `case_events`: entradas append-only de auditoria
- `case_messages`: mapeamentos de sala/evento Matrix
- `jobs`: registros de fila com retry/scheduling
- `prompt_templates`: prompts versionados com uma versão ativa por nome
- `users` e `auth_tokens`: fundação de auth e controle de acesso
