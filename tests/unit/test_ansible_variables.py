"""Tests for required Ansible variable defaults and mandatory keys."""

from __future__ import annotations

from pathlib import Path


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_ansible_group_vars_defines_runtime_deploy_defaults() -> None:
    """Ensure base remote deploy defaults are declared in group_vars."""

    variables = _read("ansible/inventory/group_vars/all.yml")

    required_tokens = (
        "ats_service_user:",
        "ats_runtime_image_registry:",
        "ats_runtime_image_repository:",
        "ats_runtime_image_tag:",
        "ats_runtime_image:",
        "ats_runtime_services:",
        "bot_api:",
        "bot_matrix:",
        "worker:",
        "ats_runtime_env_required:",
        "ats_runtime_env_defaults:",
    )
    for token in required_tokens:
        assert token in variables, f"Missing variable token in ansible defaults: {token}"


def test_ansible_group_vars_declares_public_ghcr_baseline_and_required_env() -> None:
    """Ensure GHCR public baseline and mandatory runtime env keys are declared."""

    variables = _read("ansible/inventory/group_vars/all.yml")

    assert 'ats_runtime_image_registry: "ghcr.io"' in variables
    assert (
        'ats_runtime_image_repository: "carlosapgomes/augmented-triage-system"'
        in variables
    )

    required_env_keys = (
        "DATABASE_URL",
        "ROOM1_ID",
        "ROOM2_ID",
        "ROOM3_ID",
        "MATRIX_HOMESERVER_URL",
        "MATRIX_BOT_USER_ID",
        "MATRIX_ACCESS_TOKEN",
        "WEBHOOK_PUBLIC_URL",
        "WEBHOOK_HMAC_SECRET",
    )
    for key in required_env_keys:
        assert f"  {key}:" in variables, f"Missing mandatory env key declaration: {key}"
