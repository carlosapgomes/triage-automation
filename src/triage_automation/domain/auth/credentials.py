"""Shared normalization helpers for user credential inputs."""

from __future__ import annotations


def normalize_user_email(*, email: str) -> str:
    """Normalize one user email and reject blank values."""

    normalized = email.strip().lower()
    if not normalized:
        raise ValueError("email cannot be blank")
    return normalized


def normalize_user_password(*, password: str) -> str:
    """Normalize one plaintext password and reject blank values."""

    normalized = password.strip()
    if not normalized:
        raise ValueError("password cannot be blank")
    return normalized
