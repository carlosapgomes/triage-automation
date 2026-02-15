from __future__ import annotations

from triage_automation.infrastructure.security.password_hasher import BcryptPasswordHasher


def test_hash_password_never_stores_plaintext_and_verifies() -> None:
    hasher = BcryptPasswordHasher()
    password = "super-secret-password"

    password_hash = hasher.hash_password(password)

    assert password_hash != password
    assert password not in password_hash
    assert hasher.verify_password(password=password, password_hash=password_hash) is True


def test_wrong_password_fails_verification() -> None:
    hasher = BcryptPasswordHasher()
    password_hash = hasher.hash_password("correct")

    assert hasher.verify_password(password="wrong", password_hash=password_hash) is False
