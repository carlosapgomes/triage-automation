"""Tests for required Ansible base directory layout."""

from __future__ import annotations

from pathlib import Path


def test_ansible_base_layout_exists() -> None:
    """Ensure the mandatory Ansible root layout is present in the repository."""

    expected_directories = (
        Path("ansible"),
        Path("ansible/inventory"),
        Path("ansible/inventory/group_vars"),
        Path("ansible/inventory/host_vars"),
        Path("ansible/playbooks"),
        Path("ansible/roles"),
        Path("ansible/templates"),
    )

    missing = [str(path) for path in expected_directories if not path.is_dir()]
    assert not missing, f"Missing Ansible directories: {missing}"
