"""Bcrypt password hasher adapter."""

from __future__ import annotations

import bcrypt

from triage_automation.application.ports.password_hasher_port import PasswordHasherPort


class BcryptPasswordHasher(PasswordHasherPort):
    """Password hashing adapter using bcrypt."""

    def hash_password(self, password: str) -> str:
        encoded = password.encode("utf-8")
        return bcrypt.hashpw(encoded, bcrypt.gensalt()).decode("utf-8")

    def verify_password(self, *, password: str, password_hash: str) -> bool:
        try:
            return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
        except ValueError:
            return False
