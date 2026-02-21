from __future__ import annotations

from pathlib import Path


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_ansible_ops_runbook_documents_initial_installation_in_portuguese() -> None:
    runbook = _read("docs/ansible_ops_runbook.md")
    bootstrap_command = (
        "ansible-playbook -i ansible/inventory/hosts.yml ansible/playbooks/bootstrap.yml"
    )
    deploy_command = (
        "ansible-playbook -i ansible/inventory/hosts.yml ansible/playbooks/deploy.yml"
    )

    assert "Idioma: **Português (BR)** | [English](en/ansible_ops_runbook.md)" in runbook
    assert "Ubuntu 24.04 LTS" in runbook
    assert "single-host" in runbook
    assert "GHCR público" in runbook
    assert "## Pré-requisitos" in runbook
    assert "## Inventário mínimo" in runbook
    assert "## Comandos oficiais de instalação inicial" in runbook
    assert bootstrap_command in runbook
    assert deploy_command in runbook
    assert "ats_runtime_image_tag=v1.0.0" in runbook
    assert "DATABASE_URL" in runbook
    assert "MATRIX_ACCESS_TOKEN" in runbook


def test_ansible_ops_runbook_documents_upgrade_and_rollback_in_portuguese() -> None:
    runbook = _read("docs/ansible_ops_runbook.md")
    upgrade_command = (
        "ansible-playbook -i ansible/inventory/hosts.yml ansible/playbooks/upgrade.yml"
    )
    rollback_command = (
        "ansible-playbook -i ansible/inventory/hosts.yml ansible/playbooks/rollback.yml"
    )

    assert "## Fluxo oficial de upgrade" in runbook
    assert "ats_runtime_image_tag=v1.0.1" in runbook
    assert upgrade_command in runbook
    assert "Validate all runtime services are running after upgrade" in runbook
    assert "## Fluxo oficial de rollback" in runbook
    assert "ats_runtime_rollback_image_tag=v1.0.0" in runbook
    assert rollback_command in runbook
    assert "Validate all runtime services are running after rollback" in runbook


def test_ansible_ops_runbook_documents_initial_installation_in_english() -> None:
    runbook = _read("docs/en/ansible_ops_runbook.md")
    bootstrap_command = (
        "ansible-playbook -i ansible/inventory/hosts.yml ansible/playbooks/bootstrap.yml"
    )
    deploy_command = (
        "ansible-playbook -i ansible/inventory/hosts.yml ansible/playbooks/deploy.yml"
    )

    assert "Language: [Portugues (BR)](../ansible_ops_runbook.md) | **English**" in runbook
    assert "Ubuntu 24.04 LTS" in runbook
    assert "single-host" in runbook
    assert "public GHCR" in runbook
    assert "## Prerequisites" in runbook
    assert "## Minimum Inventory" in runbook
    assert "## Official Initial Installation Commands" in runbook
    assert bootstrap_command in runbook
    assert deploy_command in runbook
    assert "ats_runtime_image_tag=v1.0.0" in runbook
    assert "DATABASE_URL" in runbook
    assert "MATRIX_ACCESS_TOKEN" in runbook


def test_ansible_ops_runbook_documents_upgrade_and_rollback_in_english() -> None:
    runbook = _read("docs/en/ansible_ops_runbook.md")
    upgrade_command = (
        "ansible-playbook -i ansible/inventory/hosts.yml ansible/playbooks/upgrade.yml"
    )
    rollback_command = (
        "ansible-playbook -i ansible/inventory/hosts.yml ansible/playbooks/rollback.yml"
    )

    assert "## Official Upgrade Flow" in runbook
    assert "ats_runtime_image_tag=v1.0.1" in runbook
    assert upgrade_command in runbook
    assert "Validate all runtime services are running after upgrade" in runbook
    assert "## Official Rollback Flow" in runbook
    assert "ats_runtime_rollback_image_tag=v1.0.0" in runbook
    assert rollback_command in runbook
    assert "Validate all runtime services are running after rollback" in runbook
