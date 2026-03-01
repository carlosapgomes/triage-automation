# Runbook Operacional Ansible

Idioma: **Português (BR)** | [English](en/ansible_ops_runbook.md)

Este runbook descreve a instalação inicial oficial do ATS em ambiente remoto com Ansible.

Baseline suportado nesta entrega:

- Ubuntu 24.04 LTS
- single-host
- Docker rootless com usuário dedicado de serviço
- imagem pública em GHCR público

## Pré-requisitos

1. Estação de operação com Ansible instalado.
1. Acesso SSH ao host remoto com usuário que tenha `sudo`.
1. Host alvo em Ubuntu 24.04 LTS.
1. Repositório clonado localmente com o diretório `ansible/` presente.
1. Inventário e variáveis preenchidos antes de executar playbooks.

## Acesso ao dashboard por domínio

Para uso real do dashboard web, é necessário publicar o endpoint local do `bot-api`
(`http://127.0.0.1:8000`) por um domínio do hospital.

Opções suportadas nesta fase:

- reverse proxy (por exemplo, Nginx/Caddy) encaminhando para `127.0.0.1:8000`.
- túnel Cloudflare (Cloudflare Tunnel) apontando para `http://127.0.0.1:8000`.

Recomendação operacional:

- usar HTTPS no domínio público.
- não expor diretamente porta de loopback sem camada de publicação controlada.

## Inventário mínimo

Crie `ansible/inventory/hosts.yml`:

```yaml
all:
  hosts:
    ats-prod-01:
      ansible_host: 203.0.113.10
      ansible_user: ubuntu
```

Preencha variáveis obrigatórias em `ansible/host_vars/ats-prod-01.yml`:

```yaml
ats_runtime_env_required:
  DATABASE_URL: "postgresql+asyncpg://ats:<senha>@127.0.0.1:5432/ats"
  ROOM1_ID: "!room1:example.org"
  ROOM2_ID: "!room2:example.org"
  ROOM3_ID: "!room3:example.org"
  MATRIX_HOMESERVER_URL: "https://matrix.example.org"
  MATRIX_BOT_USER_ID: "@ats-bot:example.org"
  MATRIX_ACCESS_TOKEN: "<token>"
  WEBHOOK_PUBLIC_URL: "https://ats.example.org/widget"
  WEBHOOK_HMAC_SECRET: "<segredo>"
```

Opcional para bootstrap do primeiro admin:

```yaml
ats_runtime_env_optional:
  BOOTSTRAP_ADMIN_EMAIL: "admin@example.org"
  BOOTSTRAP_ADMIN_PASSWORD: "<senha-forte>"
```

## Comandos oficiais de instalação inicial

1. Executar bootstrap do host (dependências, usuário de serviço e Docker rootless):

```bash
ansible-playbook -i ansible/inventory/hosts.yml ansible/playbooks/bootstrap.yml
```

1. Executar deploy inicial com tag explícita:

```bash
ansible-playbook -i ansible/inventory/hosts.yml ansible/playbooks/deploy.yml \
  -e ats_runtime_image_tag=v1.0.0
```

1. Resultado esperado:

- serviços `bot-api`, `bot-matrix` e `worker` iniciados.
- configuração de runtime renderizada em `{{ ats_runtime_root }}` no host remoto.
- playbook finalizado sem falhas.

## Política de pull de imagem no deploy/upgrade

Política padrão atual do runtime:

- `ats_runtime_pull_policy: "always"`

Implicações operacionais:

- o deploy/upgrade sempre tenta baixar a imagem da tag alvo no registry;
- o comportamento não depende de remover imagem local da tag antes do `pull`.

Observação sobre limpeza de imagem:

- a remoção prévia da imagem alvo é executada apenas em modo `missing` (best-effort);
- no baseline (`always`), essa remoção condicional fica inativa.

## Fluxo oficial de upgrade

1. Defina a nova tag alvo (não usar `latest`):

```bash
ansible-playbook -i ansible/inventory/hosts.yml ansible/playbooks/upgrade.yml \
  -e ats_runtime_image_tag=v1.0.1
```

1. Resultado esperado:

- serviços continuam em execução após atualização.
- validação pós-deploy do playbook executa `Validate all runtime services are running after upgrade`.
- playbook finalizado sem falhas.

## Fluxo oficial de rollback

1. Defina a tag estável anterior para retorno:

```bash
ansible-playbook -i ansible/inventory/hosts.yml ansible/playbooks/rollback.yml \
  -e ats_runtime_rollback_image_tag=v1.0.0
```

1. Resultado esperado:

- serviços retornam para a versão estável definida no rollback.
- validação pós-rollback do playbook executa `Validate all runtime services are running after rollback`.
- playbook finalizado sem falhas.

## Troubleshooting de primeiro nível

1. Falha por variável obrigatória ausente no bootstrap:

- sintoma: playbook falha com mensagem contendo `Required runtime variable`.
- ação imediata: revisar `ansible/host_vars/<host>.yml` e preencher todas as chaves de `ats_runtime_env_required`.
- repetir comando oficial:

```bash
ansible-playbook -i ansible/inventory/hosts.yml ansible/playbooks/bootstrap.yml
```

1. Falha por tag inválida (`latest`) em deploy/upgrade:

- sintoma: playbook falha com `Explicit runtime image tag is required.`.
- ação imediata: definir tag explícita versionada em `ats_runtime_image_tag` e executar novamente.

1. Falha no gate pós-deploy:

- sintoma: erro com `Deploy approval gate failed.`.
- ação imediata: validar status dos serviços no host e corrigir configuração de runtime antes de nova execução.
- repetir o comando do playbook correspondente (`deploy.yml`, `upgrade.yml` ou `rollback.yml`).

## Limites de escalonamento para desenvolvimento

Escalonar para desenvolvimento quando:

- erro persistir após correção de inventário/variáveis e nova execução completa do playbook.
- falha indicar possível bug de automação (ex.: role com comportamento inconsistente entre execuções idempotentes).
- falha de validação pós-deploy não for resolvida com ajuste operacional de primeiro nível.

Incluir no chamado para escalonar para desenvolvimento:

- comando executado e horário.
- host alvo e tag usada (`ats_runtime_image_tag` ou `ats_runtime_rollback_image_tag`).
- trecho relevante do erro retornado pelo Ansible.
