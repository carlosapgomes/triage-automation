"""Tests for base host role structure and bootstrap wiring."""

from __future__ import annotations

from pathlib import Path


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_base_host_role_declares_required_packages_and_supported_distro() -> None:
    """Ensure base_host role defines package list and Ubuntu baseline guard."""

    defaults = _read("ansible/roles/base_host/defaults/main.yml")
    tasks = _read("ansible/roles/base_host/tasks/main.yml")

    assert "ats_base_host_packages:" in defaults
    assert "ca-certificates" in defaults
    assert "curl" in defaults
    assert "uidmap" in defaults
    assert "dbus-user-session" in defaults
    assert "slirp4netns" in defaults
    assert "fuse-overlayfs" in defaults

    assert "ansible.builtin.assert:" in tasks
    assert "ansible_facts.distribution == \"Ubuntu\"" in tasks
    assert "ansible_facts.distribution_version is version(\"24.04\", \"==\")" in tasks
    assert "ansible.builtin.apt:" in tasks
    assert "name: \"{{ ats_base_host_packages }}\"" in tasks


def test_bootstrap_playbook_invokes_base_host_role() -> None:
    """Ensure bootstrap playbook wires the base_host role."""

    bootstrap = _read("ansible/playbooks/bootstrap.yml")

    assert "include_role:" in bootstrap
    assert "name: base_host" in bootstrap
