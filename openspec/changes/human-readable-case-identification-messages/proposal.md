# Proposal

## Why

As mensagens atuais exibem majoritariamente o UUID técnico do caso, o que reduz legibilidade e dificulta identificação rápida pelos usuários operacionais das salas. O fluxo precisa manter rastreabilidade técnica sem perder contexto humano, priorizando `no. ocorrência` e `paciente` no topo das mensagens.

## What Changes

- Atualizar templates e mensagens bot-driven das salas Room-1, Room-2 e Room-3 para exibir identificadores humanos no topo com formato:
  - `no. ocorrência: {{ agency_record_number }}`
  - `paciente: {{ patient_name }}`
- Padronizar fallback quando dado estiver ausente para `não detectado`.
- Aplicar regra de identificação por tipo de mensagem:
  - Mensagens onde UUID não é essencial: substituir referência principal de `caso: <uuid>` por `no. ocorrência` + `paciente`.
  - Mensagens onde UUID é essencial para contrato de parsing/validação: manter UUID e acrescentar `no. ocorrência` + `paciente` no contexto exibido.
- Preservar compatibilidade dos parsers estritos de Room-2 e Room-3 que dependem de linha `caso` com UUID para validação de consistência do fluxo.
- Alterar padrão de filename do anexo PDF em Room-2 para:
  - `ocorrencia-<agency_record_number>-caso-<uuid>-relatorio-original.pdf`
  - quando ocorrência indisponível: `ocorrencia-indisponivel-caso-<uuid>-relatorio-original.pdf`

## Capabilities

### New Capabilities

- `human-readable-case-identification-messages`: governança de identificação humana nas mensagens Room-1/2/3 com fallback padronizado, preservando UUID apenas quando tecnicamente obrigatório.

### Modified Capabilities

- `room2-structured-reply-decision`: ajustar requisitos de templates/feedback de Room-2 para exibir contexto humano (`no. ocorrência` + `paciente`) sem quebrar contrato estrito baseado em UUID.

## Impact

- Alterações em templates de mensagens Matrix e serviços que montam payloads de Room-1/2/3.
- Ajustes no snapshot/contexto de dados usados por Room-2 para garantir disponibilidade consistente de `patient_name` e `agency_record_number` nas mensagens.
- Ajustes em testes unitários/integrados de templates, parsing e fluxos de reply para refletir nova apresentação textual e regras de fallback.
- Melhoria de UX operacional nas salas com manutenção de rastreabilidade técnica onde necessária.
