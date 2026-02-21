"""Tests for app runtime role templates and rendering tasks."""

from __future__ import annotations

from pathlib import Path


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_app_runtime_role_declares_template_targets_and_env_merge() -> None:
    """Ensure app_runtime role defines render targets and env map composition."""

    defaults = _read("ansible/roles/app_runtime/defaults/main.yml")
    tasks = _read("ansible/roles/app_runtime/tasks/main.yml")

    assert "ats_runtime_compose_file:" in defaults
    assert "ats_runtime_environment_file_mode:" in defaults
    assert "ats_runtime_compose_file_mode:" in defaults

    assert "ats_runtime_env_defaults | combine(ats_runtime_env_optional)" in tasks
    assert "combine(ats_runtime_env_required)" in tasks
    assert "ansible.builtin.template:" in tasks
    assert "src: runtime.env.j2" in tasks
    assert "dest: \"{{ ats_runtime_env_file }}\"" in tasks
    assert "src: docker-compose.rootless.yml.j2" in tasks
    assert "dest: \"{{ ats_runtime_compose_file }}\"" in tasks


def test_app_runtime_role_templates_exist_with_expected_placeholders() -> None:
    """Ensure runtime templates include env and compose placeholders."""

    env_template = _read("ansible/roles/app_runtime/templates/runtime.env.j2")
    compose_template = _read("ansible/roles/app_runtime/templates/docker-compose.rootless.yml.j2")

    assert "for key, value in ats_runtime_env | dictsort" in env_template
    assert "{{ key }}={{ value }}" in env_template

    assert "services:" in compose_template
    assert "bot-api:" in compose_template
    assert "bot-matrix:" in compose_template
    assert "worker:" in compose_template
    assert "{{ ats_runtime_image }}" in compose_template
    assert "{{ ats_runtime_env_file }}" in compose_template
