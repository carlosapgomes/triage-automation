# Design

## Context

O fluxo atual publica mensagens para Room-1, Room-2 e Room-3 usando templates concentrados em `src/triage_automation/infrastructure/matrix/message_templates.py`. Em vários pontos o identificador visível principal é `caso: <uuid>`, enquanto usuários operacionais precisam identificar rapidamente por ocorrência e paciente.

Há restrição funcional crítica: os parsers estritos de resposta de Room-2 e Room-3 validam linha `caso` com UUID e fazem checagem de consistência com `expected_case_id`. Portanto, remover UUID dos templates estruturais quebraria parsing e roteamento.

Também existe requisito de nomenclatura de anexo PDF na Room-2, hoje baseada apenas no UUID, que deve passar a incluir ocorrência mantendo o UUID para rastreabilidade técnica.

## Goals / Non-Goals

**Goals:**

- Exibir identificadores humanos no topo das mensagens com formato fixo:
  - `no. ocorrência: <valor>`
  - `paciente: <valor>`
- Padronizar fallback para `não detectado` quando ocorrência e/ou paciente não estiverem disponíveis.
- Aplicar política dual de identificação:
  - Sem necessidade estrutural de UUID: substituir UUID visível por identificação humana.
  - Com necessidade estrutural de UUID: manter UUID e acrescentar identificação humana.
- Preservar compatibilidade de parsing, roteamento e state machine existentes.
- Atualizar nome de arquivo do PDF da Room-2 para incluir ocorrência e UUID com fallback definido.

**Non-Goals:**

- Alterar contratos de parser (`doctor_decision_parser`, `scheduler_parser`) ou semântica de validação de `expected_case_id`.
- Redesenhar estados de workflow, regras de decisão médica, ou regras de agendamento.
- Alterar payloads internos/auditoria de banco além do necessário para renderização das mensagens.

## Decisions

### Decision 1: Introduzir um bloco único de identificação humana reutilizável

Implementar helper de formatação em `message_templates.py` para gerar, de forma determinística, as duas linhas no topo:

- `no. ocorrência: <valor ou não detectado>`
- `paciente: <valor ou não detectado>`

Rationale:

- Evita divergência de texto entre Room-1/2/3.
- Reduz duplicação e risco de inconsistência de fallback.

Alternativas consideradas:

- Duplicar interpolação em cada template.
  - Rejeitada por alto risco de drift e manutenção frágil.

### Decision 2: Preservar UUID apenas nas mensagens com contrato estrutural

Classificar templates em dois grupos:

- Estruturais (UUID obrigatório): templates que o humano copia para resposta e prompts de correção de formato; nesses, manter linha `caso: <uuid>` e acrescentar bloco humano.
- Informativos (UUID não obrigatório): substituir destaque primário de UUID por bloco humano.

Rationale:

- Mantém UX mais legível sem quebrar contrato técnico de parsing.

Alternativas consideradas:

- Remover UUID de todos os templates.
  - Rejeitada por quebra direta de parsers e validação de consistência.

### Decision 3: Normalizar aquisição de `patient_name` para Room-2

Room-3 e Room-1 já extraem `patient_name` de `structured_data_json` via helper de contexto. Room-2 passará a usar o mesmo helper para renderização textual, sem mover lógica de negócio para adapter.

Rationale:

- Reuso de regra já consolidada no código.
- Mantém arquitetura em camadas e reduz chance de comportamento divergente.

Alternativas consideradas:

- Derivar nome do paciente diretamente no template por chave bruta.
  - Rejeitada por acoplamento e repetição de regras de extração.

### Decision 4: Atualizar filename do PDF com sanitização mínima e fallback

Novo padrão para Room-2:

- `ocorrencia-<agency_record_number>-caso-<uuid>-relatorio-original.pdf`
- fallback de ocorrência ausente: `ocorrencia-indisponivel-caso-<uuid>-relatorio-original.pdf`

Aplicar normalização segura para trecho de ocorrência no filename (trim e substituição de caracteres inviáveis para `-`).

Rationale:

- Melhora rastreabilidade operacional no cliente Matrix.
- Mantém UUID no filename para vínculo técnico inequívoco.

Alternativas consideradas:

- Usar ocorrência sem UUID no nome do arquivo.
  - Rejeitada por reduzir garantia de unicidade/rastreabilidade técnica.

## Risks / Trade-offs

- [Risco] Campos ausentes em casos antigos (sem ocorrência ou sem paciente) geram mensagens com fallback frequente.
  Mitigação: fallback explícito `não detectado` e testes com snapshots incompletos.

- [Risco] Mudanças textuais quebram asserts de testes de integração/unitários.
  Mitigação: atualizar testes por contrato (conteúdo essencial) e manter checks de parsing/UUID obrigatório nos templates estruturais.

- [Trade-off] Mensagens estruturais ficarão mais longas por incluir contexto humano e UUID.
  Mitigação: manter bloco humano curto no topo e conservar template estrito em linhas previsíveis.

## Migration Plan

1. Atualizar builders de templates e helpers de contexto/identificação.
2. Atualizar chamadas dos serviços Room-1/2/3 para fornecer dados necessários ao bloco humano.
3. Atualizar regra de filename do anexo Room-2 com fallback.
4. Atualizar e executar testes unitários/integrados dos fluxos de mensagens e parsing.
5. Deploy sem migração de schema; rollback é reversão de código para templates anteriores.

## Open Questions

- Não há questões abertas no momento; regras de fallback, formato textual e política de UUID já foram definidas.
