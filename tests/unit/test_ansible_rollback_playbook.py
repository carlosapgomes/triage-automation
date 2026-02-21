"""Tests for rollback playbook wiring and post-rollback validation."""

from __future__ import annotations

from pathlib import Path


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_rollback_playbook_declares_target_tag_and_validation_flow() -> None:
    """Ensure rollback playbook targets explicit tag and validates runtime health."""

    playbook = _read("ansible/playbooks/rollback.yml")
    rollback_tag_guard = (
        "ats_runtime_allow_latest_tag or "
        '(ats_runtime_rollback_image_tag | lower != "latest")'
    )
    running_services_guard = (
        "ats_runtime_deploy_services | "
        "difference(ats_rollback_running_services.stdout_lines) | length == 0"
    )

    assert "name: Rollback ATS runtime services" in playbook
    assert "pre_tasks:" in playbook
    assert "Validate explicit rollback image tag" in playbook
    assert "ats_runtime_rollback_image_tag is defined" in playbook
    assert "ats_runtime_rollback_image_tag | trim | length > 0" in playbook
    assert rollback_tag_guard in playbook
    assert "Set rollback image tag as active deploy target" in playbook
    assert "ats_runtime_image_tag: \"{{ ats_runtime_rollback_image_tag }}\"" in playbook
    assert "Rollback target image: {{ ats_runtime_image }}" in playbook
    assert "name: app_runtime" in playbook
    assert "name: deploy" in playbook
    assert "post_tasks:" in playbook
    assert "ps --services --filter status=running" in playbook
    assert "register: ats_rollback_running_services" in playbook
    assert running_services_guard in playbook
    assert "Rollback validation failed" in playbook
