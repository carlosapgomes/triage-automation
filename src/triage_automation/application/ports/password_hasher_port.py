"""Port for password hashing and verification."""

from __future__ import annotations

from typing import Protocol


class PasswordHasherPort(Protocol):
    """Password hashing/verification contract."""

    def hash_password(self, password: str) -> str:
        """Hash plaintext password for storage."""

    def verify_password(self, *, password: str, password_hash: str) -> bool:
        """Verify plaintext password against stored hash."""
