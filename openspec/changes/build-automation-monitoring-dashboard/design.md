# Design

## Context

O sistema atual já possui base de auditoria (`case_events`) e mapeamento de mensagens Matrix (`case_messages`), mas não guarda integralmente o conteúdo textual necessário para investigação operacional completa. Para o dashboard de monitoramento, precisamos de rastreabilidade ponta a ponta por caso, incluindo: texto extraído do PDF, entradas e saídas de LLM1/LLM2, mensagens enviadas para salas 1/2/3, respostas humanas e ACKs.

Também já existe fundação de autenticação/autorização com `users`, `auth_tokens` e papéis `reader` e `admin`, que será reutilizada para diferenciar acesso de monitoramento e gestão de prompts.

## Goals

- Disponibilizar visão temporal completa por caso, com sequência de eventos/mensagens e metadados de sala, ator e horário.
- Persistir conteúdo integral das interações necessárias para auditoria técnica e melhoria contínua (incluindo payloads LLM e mensagens Matrix completas).
- Expor APIs para dashboard com controle de acesso por papel (`reader` e `admin`).
- Permitir que `admin` gerencie prompts versionados sem romper o carregamento dinâmico atual do worker.

## Non-Goals

- Alterar a máquina de estados clínica ou regras de decisão existentes.
- Implementar anonimização automática de conteúdo histórico nesta mesma mudança.
- Redesenhar o mecanismo de auth/token já em uso.

## Decisions

### Decision 1: Introduzir trilha unificada de conteúdo auditável por caso

- Choice: criar persistência dedicada para histórico completo de conteúdo (mensagens + I/O de LLM) com associação por `case_id`, carimbo temporal, origem/canal e autor.
- Rationale: `case_messages` guarda somente identificadores e não atende o requisito de conteúdo integral para debug/auditoria.
- Alternative considered: expandir `case_messages` com muitas colunas para todos os tipos de conteúdo.
  - Rejected por acoplamento alto ao domínio Matrix e baixa clareza para eventos não-Matrix (LLM/PDF).

### Decision 2: Separar captura de interações LLM em estrutura própria

- Choice: persistir interações LLM (prompt enviado, resposta recebida, metadados de modelo/versão de prompt, estágio LLM1/LLM2) em registro estruturado e ligado ao caso.
- Rationale: facilita auditoria de qualidade de prompt e correlação com decisões sem poluir eventos de chat.
- Alternative considered: armazenar tudo em JSON livre numa única tabela de auditoria.
  - Rejected por perda de queryabilidade e dificuldade de filtros operacionais.

### Decision 3: Dashboard orientado a APIs com timeline agregada

- Choice: expor endpoints para:
  - listagem paginada de casos por período/status,
  - detalhe de caso com timeline cronológica,
  - filtros por sala/ator/tipo de evento,
  - trechos e conteúdo completo quando autorizado.
- Rationale: desacopla frontend de estrutura interna e permite evolução de UI sem alterar persistência.
- Alternative considered: frontend consultando banco diretamente.
  - Rejected por risco de segurança e quebra de encapsulamento arquitetural.

### Decision 4: Reusar RBAC existente (`reader`/`admin`)

- Choice: `reader` acessa somente monitoramento; `admin` acessa monitoramento + endpoints de gestão de prompts (listar versões, ativar versão, histórico de alterações).
- Rationale: mantém consistência com fundação já implementada e reduz superfície de decisão nova.
- Alternative considered: criar novo papel adicional para prompts.
  - Rejected nesta fase para reduzir complexidade inicial.

### Decision 5: Captura no ponto de fronteira (adapters) com regra de append-only

- Choice: gravar trilha no momento de entrada/saída dos adapters (Matrix ingress/egress e LLM client boundary), mantendo histórico append-only.
- Rationale: minimiza perda de eventos e evita dependência de reconstrução posterior por inferência.
- Alternative considered: gerar trilha somente por batch offline.
  - Rejected por atraso e risco de inconsistência.

## Risks / Trade-offs

- [Crescimento acelerado de volume de dados textuais] → Mitigation: índices por `case_id`/`timestamp`, paginação obrigatória e política de retenção definida em operação.
- [Exposição de conteúdo sensível em dashboard] → Mitigation: RBAC estrito, trilha de acesso/auditoria e revisão de máscara/ocultação em campos de alto risco.
- [Impacto de performance ao escrever trilha em tempo real] → Mitigation: escrita enxuta por evento, payloads estruturados e testes de carga em rotas de maior frequência.
- [Complexidade de consistência entre múltiplas fontes (Matrix/LLM/PDF)] → Mitigation: schema explícito de origem/tipo de evento e ordenação por timestamp de ingestão com ids estáveis.

## Migration Plan

1. Criar migrações de banco para estruturas de trilha completa e índices necessários.
2. Atualizar adapters/serviços para capturar e persistir conteúdo integral novo (sem backfill obrigatório de históricos antigos).
3. Implementar endpoints de monitoramento para listagem de casos e timeline detalhada.
4. Implementar endpoints de gestão de prompts para `admin`, preservando invariantes de uma versão ativa por prompt.
5. Implementar UI do dashboard com visão de thread temporal e diferenciação visual de sala/tipo.
6. Validar com testes (unit/integration) e checklist manual de RBAC, timeline e prompt management.

Rollback strategy:

- Rollback de código para desativar APIs/UI novas mantendo tabelas aditivas (sem DROP imediato).
- Em caso de regressão operacional, manter apenas fluxo de produção existente e pausar uso do dashboard até correção.

## Open Questions

- Definir política operacional de retenção de conteúdo integral (prazo e procedimento de expurgo). - Resposta: retenção permanente neste momento
- Definir se respostas de API do dashboard devem aplicar mascaramento parcial por campo sensível já na primeira versão. Resposta: não aplicar nenhum mascaramento
- Definir limites de paginação e filtros mínimos obrigatórios para evitar consultas pesadas em produção. Resposta: mostrar 10-15 casos por página, usar a data atual como  filtro default.
