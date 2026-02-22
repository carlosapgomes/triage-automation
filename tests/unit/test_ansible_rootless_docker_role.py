"""Tests for rootless Docker role structure and bootstrap wiring."""

from __future__ import annotations

from pathlib import Path


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_rootless_docker_role_declares_user_context_setup_tasks() -> None:
    """Ensure rootless_docker role configures rootless runtime for service user."""

    defaults = _read("ansible/roles/rootless_docker/defaults/main.yml")
    tasks = _read("ansible/roles/rootless_docker/tasks/main.yml")

    assert "ats_rootless_docker_packages:" in defaults
    assert "docker.io" in defaults
    assert "docker-compose-v2" in defaults

    assert "/etc/subuid" in tasks
    assert "/etc/subgid" in tasks
    assert "loginctl enable-linger {{ ats_service_user }}" in tasks
    assert "become_user: \"{{ ats_service_user }}\"" in tasks
    assert "dockerd-rootless-setuptool.sh install --force" in tasks
    assert "ansible.builtin.systemd_service:" in tasks
    assert "scope: user" in tasks
    assert "name: docker.service" in tasks
    assert "state: started" in tasks
    assert "enabled: true" in tasks
    assert "ats_docker_info_server_version_format" in tasks
    assert "ats_docker_info_security_options_format" in tasks
    assert "docker compose version" in tasks
    assert "Rootless Docker is not active" in tasks


def test_bootstrap_playbook_invokes_rootless_docker_role() -> None:
    """Ensure bootstrap playbook wires rootless_docker role."""

    bootstrap = _read("ansible/playbooks/bootstrap.yml")

    assert "name: rootless_docker" in bootstrap
