# Arquitetura

Idioma: **Portugues (BR)** | [English](en/architecture.md)

## Visao Geral

O sistema e dividido em tres apps deployaveis mais PostgreSQL:

- `bot-api`: ingress HTTP para fundacao de login/auth e endpoints de suporte de runtime.
- `bot-matrix`: integracao Matrix para eventos de intake/reacao.
- `worker`: consumidor async de fila para extracao, jobs LLM, postagem e cleanup.
- `postgres`: fonte de verdade para casos, jobs, mapeamento de mensagens e trilha de auditoria.

## Camadas e direcao de dependencia

O codigo segue esta direcao de dependencia:

- adapters (`apps`, `infrastructure/http`, `infrastructure/matrix`)
- servicos e portas de aplicacao (`src/triage_automation/application`)
- dominio (`src/triage_automation/domain`)
- implementacoes de infraestrutura (`src/triage_automation/infrastructure`)

Regras:

- logica de negocio pertence a `application` e `domain`
- adapters devem permanecer enxutos
- detalhes de infraestrutura sao consumidos via portas

## Modulos principais

- Settings: `src/triage_automation/config/settings.py`
- Metadata de banco: `src/triage_automation/infrastructure/db/metadata.py`
- Job queue: `src/triage_automation/infrastructure/db/job_queue_repository.py`
- Rota de auth/login: `src/triage_automation/infrastructure/http/auth_router.py`
- Montagem do runtime Bot API: `apps/bot_api/main.py`

## Notas do workflow

- O ciclo de vida da triagem e dirigido por maquina de estados (veja `PROJECT_CONTEXT.md` para estados canonicos).
- O caminho de decisao medica da Sala 2 e somente por resposta estruturada Matrix.
- O cleanup e disparado pela primeira reacao de thumbs-up na resposta final da Sala 1.
- O monitoramento inclui API e paginas server-rendered de dashboard no `bot-api`.
- O gerenciamento de prompts segue com acesso de `admin` na superficie administrativa.

## Modelo de persistencia (alto nivel)

- `cases`: ciclo de vida do caso e artefatos
- `case_events`: entradas append-only de auditoria
- `case_messages`: mapeamentos de sala/evento Matrix
- `jobs`: registros de fila com retry/scheduling
- `prompt_templates`: prompts versionados com uma versao ativa por nome
- `users` e `auth_tokens`: fundacao de auth e controle de acesso
