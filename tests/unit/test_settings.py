import pytest
from pydantic import ValidationError

from triage_automation.config.settings import Settings

REQUIRED_ENV = {
    "ROOM1_ID": "!room1:example.org",
    "ROOM2_ID": "!room2:example.org",
    "ROOM3_ID": "!room3:example.org",
    "MATRIX_HOMESERVER_URL": "https://matrix.example.org",
    "WEBHOOK_PUBLIC_URL": "https://webhook.example.org",
    "DATABASE_URL": "postgresql+asyncpg://user:pass@postgres:5432/triage",
    "WEBHOOK_HMAC_SECRET": "super-secret",
}


def _set_required_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key, value in REQUIRED_ENV.items():
        monkeypatch.setenv(key, value)


def test_required_env_var_missing_raises_validation_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_required_env(monkeypatch)
    monkeypatch.delenv("ROOM1_ID", raising=False)

    with pytest.raises(ValidationError):
        Settings()


def test_defaults_are_deterministic(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required_env(monkeypatch)

    settings = Settings()

    assert settings.log_level == "INFO"


def test_room_ids_and_urls_are_non_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required_env(monkeypatch)

    settings = Settings()

    assert settings.room1_id
    assert settings.room2_id
    assert settings.room3_id
    assert str(settings.matrix_homeserver_url)
    assert str(settings.webhook_public_url)
