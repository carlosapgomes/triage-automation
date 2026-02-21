# Ansible Operations Runbook

Language: [Portugues (BR)](../ansible_ops_runbook.md) | **English**

This runbook defines the official ATS initial installation flow on a remote host using Ansible.

Supported baseline in this delivery:

- Ubuntu 24.04 LTS
- single-host
- rootless Docker with a dedicated service user
- public image on public GHCR

## Prerequisites

1. Operator workstation with Ansible installed.
1. SSH access to the remote host with a user that has `sudo`.
1. Target host running Ubuntu 24.04 LTS.
1. Repository cloned locally with the `ansible/` directory available.
1. Inventory and required variables filled before playbook execution.

## Minimum Inventory

Create `ansible/inventory/hosts.yml`:

```yaml
all:
  hosts:
    ats-prod-01:
      ansible_host: 203.0.113.10
      ansible_user: ubuntu
```

Fill mandatory variables in `ansible/host_vars/ats-prod-01.yml`:

```yaml
ats_runtime_env_required:
  DATABASE_URL: "postgresql+asyncpg://ats:<password>@127.0.0.1:5432/ats"
  ROOM1_ID: "!room1:example.org"
  ROOM2_ID: "!room2:example.org"
  ROOM3_ID: "!room3:example.org"
  MATRIX_HOMESERVER_URL: "https://matrix.example.org"
  MATRIX_BOT_USER_ID: "@ats-bot:example.org"
  MATRIX_ACCESS_TOKEN: "<token>"
  WEBHOOK_PUBLIC_URL: "https://ats.example.org/widget"
  WEBHOOK_HMAC_SECRET: "<secret>"
```

Optional bootstrap for the first admin:

```yaml
ats_runtime_env_optional:
  BOOTSTRAP_ADMIN_EMAIL: "admin@example.org"
  BOOTSTRAP_ADMIN_PASSWORD: "<strong-password>"
```

## Official Initial Installation Commands

1. Run host bootstrap (dependencies, service user, and rootless Docker):

```bash
ansible-playbook -i ansible/inventory/hosts.yml ansible/playbooks/bootstrap.yml
```

1. Run initial deployment with an explicit image tag:

```bash
ansible-playbook -i ansible/inventory/hosts.yml ansible/playbooks/deploy.yml \
  -e ats_runtime_image_tag=v1.0.0
```

1. Expected result:

- `bot-api`, `bot-matrix`, and `worker` services started.
- runtime artifacts rendered under `{{ ats_runtime_root }}` on the remote host.
- playbook completes without failures.

## Official Upgrade Flow

1. Set the new target tag (do not use `latest`):

```bash
ansible-playbook -i ansible/inventory/hosts.yml ansible/playbooks/upgrade.yml \
  -e ats_runtime_image_tag=v1.0.1
```

1. Expected result:

- services remain running after the update.
- playbook post-deploy validation runs `Validate all runtime services are running after upgrade`.
- playbook completes without failures.

## Official Rollback Flow

1. Set the previous stable tag to return to:

```bash
ansible-playbook -i ansible/inventory/hosts.yml ansible/playbooks/rollback.yml \
  -e ats_runtime_rollback_image_tag=v1.0.0
```

1. Expected result:

- services return to the stable version defined for rollback.
- playbook post-rollback validation runs `Validate all runtime services are running after rollback`.
- playbook completes without failures.
