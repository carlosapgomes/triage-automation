# Tasks

## 1. Persistencia de trilha completa

- [ ] 1.1 Criar migration para armazenar texto extraido integral do relatorio por `case_id`.
- [ ] 1.2 Criar migration para armazenar interacoes LLM1/LLM2 com payload de entrada, payload de saida, estagio e metadados de prompt/modelo.
- [ ] 1.3 Criar migration para armazenar mensagens completas Matrix (bot e humano), incluindo replies e ACKs, com `room_id`, `sender`, `timestamp` e tipo.
- [ ] 1.4 Adicionar indices para consultas por `case_id` e ordenacao cronologica por timestamp.

## 2. Captura de eventos nos boundaries

- [ ] 2.1 Persistir texto extraido completo no ponto de finalizacao da extracao do relatorio.
- [ ] 2.2 Persistir I/O completo de LLM no boundary do client LLM sem alterar o workflow clinico.
- [ ] 2.3 Persistir mensagens completas enviadas/recebidas nos adapters Matrix para salas 1, 2 e 3.
- [ ] 2.4 Garantir estrategia append-only para os novos registros de trilha.

## 3. API de monitoramento

- [ ] 3.1 Implementar endpoint paginado de listagem de casos com filtros de periodo/status e ordenacao por atividade mais recente.
- [ ] 3.2 Definir filtro padrao por data atual e limite padrao de 10-15 casos por pagina.
- [ ] 3.3 Implementar endpoint de detalhe por caso com timeline cronologica unificada (PDF, LLM, Matrix).
- [ ] 3.4 Incluir metadados minimos por evento na timeline: sala/canal, ator, timestamp e tipo de evento, com ACKs e respostas humanas.

## 4. Dashboard web

- [ ] 4.1 Implementar tela de listagem de casos com filtros, paginação e campos operacionais principais.
- [ ] 4.2 Implementar tela de detalhe com timeline cronologica e diferenciacao visual por sala/tipo de evento.
- [ ] 4.3 Exibir trecho e conteudo completo de mensagens/eventos conforme permissao do usuario autenticado.

## 5. RBAC e gestao de prompts

- [ ] 5.1 Reutilizar papeis `reader` e `admin` no backend do dashboard sem alterar o mecanismo atual de autenticacao/token.
- [ ] 5.2 Implementar endpoints de prompt management para `admin`: listar versoes, consultar ativa e ativar versao.
- [ ] 5.3 Garantir rejeicao de operacoes mutaveis de prompt para `reader`.
- [ ] 5.4 Registrar auditoria das acoes de prompt (ator, acao, alvo, timestamp).

## 6. Compatibilidade de runtime e callback

- [ ] 6.1 Garantir que o runtime `bot-api` continue expondo `/callbacks/triage-decision` para compatibilidade de emergencia.
- [ ] 6.2 Garantir que a rota de callback mantenha contrato e comportamento atual de transicao de estado.
- [ ] 6.3 Expor no mesmo runtime as rotas de monitoramento e de administracao de prompts.

## 7. Validacao e prontidao manual

- [ ] 7.1 Adicionar testes de persistencia e ordenacao cronologica para trilha completa por caso.
- [ ] 7.2 Adicionar testes de autorizacao para garantir `reader` somente leitura e `admin` com mutacao de prompts.
- [ ] 7.3 Atualizar runbook/checklist manual com validacao de APIs de dashboard, timeline auditavel e fluxo de autorizacao de prompts.
- [ ] 7.4 Executar verificacoes de qualidade para o slice implementado (`uv run pytest`, `uv run ruff check`, `uv run mypy`) e registrar qualquer limitacao.
