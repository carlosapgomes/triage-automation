import pytest
from pydantic import ValidationError

from triage_automation.config.settings import Settings

REQUIRED_ENV = {
    "ROOM1_ID": "!room1:example.org",
    "ROOM2_ID": "!room2:example.org",
    "ROOM3_ID": "!room3:example.org",
    "MATRIX_HOMESERVER_URL": "https://matrix.example.org",
    "MATRIX_BOT_USER_ID": "@triage-bot:example.org",
    "MATRIX_ACCESS_TOKEN": "matrix-access-token",
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
    assert settings.matrix_sync_timeout_ms == 30_000
    assert settings.matrix_poll_interval_seconds == 1.0
    assert settings.worker_poll_interval_seconds == 1.0
    assert settings.llm_runtime_mode == "deterministic"
    assert settings.openai_api_key is None


def test_room_ids_and_urls_are_non_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required_env(monkeypatch)

    settings = Settings()

    assert settings.room1_id
    assert settings.room2_id
    assert settings.room3_id
    assert str(settings.matrix_homeserver_url)
    assert str(settings.webhook_public_url)


def test_matrix_auth_env_var_missing_raises_validation_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_required_env(monkeypatch)
    monkeypatch.delenv("MATRIX_ACCESS_TOKEN", raising=False)

    with pytest.raises(ValidationError):
        Settings()
