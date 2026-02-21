"""Tests for bootstrap playbook early validation behavior."""

from __future__ import annotations

from pathlib import Path


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_bootstrap_playbook_declares_preflight_required_variable_assertions() -> None:
    """Ensure bootstrap playbook fails early when required variables are missing."""

    bootstrap = _read("ansible/playbooks/bootstrap.yml")

    assert "pre_tasks:" in bootstrap
    assert "ansible.builtin.assert:" in bootstrap
    assert "ats_runtime_env_required | dict2items" in bootstrap
    assert "is missing or empty" in bootstrap
