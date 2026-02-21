"""Tests for deploy role service startup and playbook wiring."""

from __future__ import annotations

from pathlib import Path


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_deploy_role_declares_rootless_service_startup_tasks() -> None:
    """Ensure deploy role starts runtime services in rootless user context."""

    defaults = _read("ansible/roles/deploy/defaults/main.yml")
    tasks = _read("ansible/roles/deploy/tasks/main.yml")

    assert "ats_runtime_deploy_services:" in defaults
    assert "bot-api" in defaults
    assert "bot-matrix" in defaults
    assert "worker" in defaults

    assert "id -u {{ ats_service_user }}" in tasks
    assert "become_user: \"{{ ats_service_user }}\"" in tasks
    assert "docker compose" in tasks
    assert "pull {{ ats_runtime_deploy_services | join(' ') }}" in tasks
    assert "up --detach {{ ats_runtime_deploy_services | join(' ') }}" in tasks
    assert "chdir: \"{{ ats_runtime_root }}\"" in tasks
    assert "XDG_RUNTIME_DIR" in tasks


def test_deploy_playbook_wires_runtime_render_and_deploy_roles() -> None:
    """Ensure deploy playbook includes app_runtime and deploy roles."""

    deploy_playbook = _read("ansible/playbooks/deploy.yml")

    assert "name: app_runtime" in deploy_playbook
    assert "name: deploy" in deploy_playbook
