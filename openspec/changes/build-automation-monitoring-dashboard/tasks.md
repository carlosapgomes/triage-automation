# Tasks

## 1. Persistencia de trilha completa

- [x] 1.1 Criar migration para armazenar texto extraido integral do relatorio por `case_id`.
- [x] 1.2 Criar migration para armazenar interacoes LLM1/LLM2 com payload de entrada, payload de saida, estagio e metadados de prompt/modelo.
- [x] 1.3 Criar migration para armazenar mensagens completas Matrix (bot e humano), incluindo replies e ACKs, com `room_id`, `sender`, `timestamp` e tipo.
- [x] 1.4 Adicionar indices para consultas por `case_id` e ordenacao cronologica por timestamp.

## 2. Captura de eventos nos boundaries

- [x] 2.1 Persistir texto extraido completo no ponto de finalizacao da extracao do relatorio.
- [x] 2.2 Persistir I/O completo de LLM no boundary do client LLM sem alterar o workflow clinico.
- [x] 2.3 Persistir mensagens completas enviadas/recebidas nos adapters Matrix para salas 1, 2 e 3.
- [x] 2.4 Garantir estrategia append-only para os novos registros de trilha.

## 3. API de monitoramento

- [x] 3.1 Implementar endpoint paginado de listagem de casos com filtros de periodo/status e ordenacao por atividade mais recente.
- [x] 3.2 Definir filtro padrao por data atual e limite padrao de 10-15 casos por pagina.
- [x] 3.3 Implementar endpoint de detalhe por caso com timeline cronologica unificada (PDF, LLM, Matrix).
- [x] 3.4 Incluir metadados minimos por evento na timeline: sala/canal, ator, timestamp e tipo de evento, com ACKs e respostas humanas.

## 4. Dashboard web

- [x] 4.1 Implementar páginas server-rendered no `bot-api` com `FastAPI` + `Jinja2` e layout base em `Bootstrap 5.3`.
- [x] 4.2 Implementar tela de listagem de casos com filtros e paginação usando `Unpoly` para atualizações parciais sem build step frontend.
- [x] 4.3 Implementar tela de detalhe com timeline cronologica e diferenciacao visual por sala/tipo de evento usando `Bootstrap 5.3`.
- [x] 4.4 Exibir trecho e conteudo completo de mensagens/eventos conforme permissao do usuario autenticado, com `JavaScript vanilla` apenas para interações pontuais.

## 5. RBAC e gestao de prompts

- [x] 5.1 Reutilizar papeis `reader` e `admin` no backend do dashboard sem alterar o mecanismo atual de autenticacao/token.
- [x] 5.2 Implementar endpoints de prompt management para `admin`: listar versoes, consultar ativa e ativar versao.
- [x] 5.3 Garantir rejeicao de operacoes mutaveis de prompt para `reader`.
- [x] 5.4 Registrar auditoria das acoes de prompt (ator, acao, alvo, timestamp).

## 6. Compatibilidade de runtime Matrix-only

- [x] 6.1 Garantir que o runtime `bot-api` exponha as rotas de monitoramento e de administracao de prompts no mesmo processo.
- [x] 6.2 Garantir que o runtime de decisao medica permaneca Matrix-only (sem reintroduzir fallback HTTP de decisao).

## 7. Validacao e prontidao manual

- [x] 7.1 Adicionar testes de persistencia e ordenacao cronologica para trilha completa por caso.
- [x] 7.2 Adicionar testes de autorizacao para garantir `reader` somente leitura e `admin` com mutacao de prompts.
- [x] 7.3 Atualizar runbook/checklist manual com validacao de APIs de dashboard, timeline auditavel e fluxo de autorizacao de prompts.
- [x] 7.4 Executar verificacoes de qualidade para o slice implementado (`uv run pytest`, `uv run ruff check`, `uv run mypy`) e registrar qualquer limitacao.
  - Limitacao registrada (2026-02-18): `pytest` exibiu `DeprecationWarning` de adaptador `datetime` do `sqlite3` via SQLAlchemy/aiosqlite; sem falha funcional dos testes.
