# Proposal

## Why

A equipe de TI do hospital precisa de uma forma padronizada e reproduzível para instalar, atualizar e operar o sistema em ambiente remoto. Hoje não existe automação de deploy operacional para produção com usuário dedicado e Docker rootless.

## What Changes

- Criar automação oficial de deploy com Ansible para provisionamento e operação remota.
- Provisionar execução do `bot-api`, `bot-matrix` e `worker` com usuário de serviço dedicado (sem root para runtime da aplicação).
- Configurar Docker rootless no host alvo para execução dos serviços.
- Definir playbooks para:
  - bootstrap do host,
  - instalação de dependências,
  - configuração de ambiente (`.env`/segredos por variável),
  - deploy/upgrade,
  - validação pós-deploy e procedimentos básicos de rollback.
- Incluir documentação operacional para TI (inventário, variáveis obrigatórias, execução, troubleshooting).
- **BREAKING**: o processo operacional recomendado deixa de ser manual/adhoc e passa a exigir fluxo Ansible como caminho oficial de instalação.

## Capabilities

### New Capabilities

- `ansible-rootless-runtime-deploy`: automação idempotente de provisionamento e deploy remoto com Docker rootless e usuário dedicado.
- `ops-runbook-automation`: documentação operacional alinhada aos playbooks para instalação, atualização e suporte de primeiro nível.

### Modified Capabilities

- `runtime-orchestration`: formalizar que os comandos/runtime suportados em produção devem ser compatíveis com execução via automação de deploy.

## Impact

- Novo diretório de infraestrutura/automação (inventário, playbooks, templates e defaults).
- Ajustes de documentação (`README.md`, `docs/setup.md`, guia operacional de deploy).
- Definição explícita de variáveis de ambiente obrigatórias para ambiente remoto.
- Impacto operacional positivo: instalação previsível, menor drift entre ambientes e suporte mais simples para TI hospitalar.
