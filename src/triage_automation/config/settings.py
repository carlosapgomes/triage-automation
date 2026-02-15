"""Runtime settings loaded from environment variables."""

from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict

NonEmptyStr = Annotated[str, Field(min_length=1)]
NonNegativeFloat = Annotated[float, Field(ge=0.0)]
PositiveInt = Annotated[int, Field(gt=0)]


class Settings(BaseSettings):
    """Environment-driven application settings."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    room1_id: NonEmptyStr = Field(validation_alias="ROOM1_ID")
    room2_id: NonEmptyStr = Field(validation_alias="ROOM2_ID")
    room3_id: NonEmptyStr = Field(validation_alias="ROOM3_ID")
    matrix_homeserver_url: HttpUrl = Field(validation_alias="MATRIX_HOMESERVER_URL")
    matrix_bot_user_id: NonEmptyStr = Field(validation_alias="MATRIX_BOT_USER_ID")
    matrix_access_token: NonEmptyStr = Field(validation_alias="MATRIX_ACCESS_TOKEN")
    matrix_sync_timeout_ms: PositiveInt = Field(
        default=30_000,
        validation_alias="MATRIX_SYNC_TIMEOUT_MS",
    )
    matrix_poll_interval_seconds: NonNegativeFloat = Field(
        default=1.0,
        validation_alias="MATRIX_POLL_INTERVAL_SECONDS",
    )
    worker_poll_interval_seconds: NonNegativeFloat = Field(
        default=1.0,
        validation_alias="WORKER_POLL_INTERVAL_SECONDS",
    )
    webhook_public_url: HttpUrl = Field(validation_alias="WEBHOOK_PUBLIC_URL")
    database_url: NonEmptyStr = Field(validation_alias="DATABASE_URL")
    webhook_hmac_secret: NonEmptyStr = Field(validation_alias="WEBHOOK_HMAC_SECRET")
    llm_runtime_mode: Literal["deterministic", "provider"] = Field(
        default="deterministic",
        validation_alias="LLM_RUNTIME_MODE",
    )
    openai_api_key: str | None = Field(default=None, validation_alias="OPENAI_API_KEY")
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")


@lru_cache(maxsize=1)
def load_settings() -> Settings:
    """Load and cache application settings."""

    return Settings()  # type: ignore[call-arg]
