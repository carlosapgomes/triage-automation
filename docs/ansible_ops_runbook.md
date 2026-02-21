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
