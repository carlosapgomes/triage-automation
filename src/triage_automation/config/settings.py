"""Runtime settings loaded from environment variables."""

from functools import lru_cache
from typing import Annotated

from pydantic import Field, HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict

NonEmptyStr = Annotated[str, Field(min_length=1)]


class Settings(BaseSettings):
    """Environment-driven application settings."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    room1_id: NonEmptyStr = Field(validation_alias="ROOM1_ID")
    room2_id: NonEmptyStr = Field(validation_alias="ROOM2_ID")
    room3_id: NonEmptyStr = Field(validation_alias="ROOM3_ID")
    matrix_homeserver_url: HttpUrl = Field(validation_alias="MATRIX_HOMESERVER_URL")
    webhook_public_url: HttpUrl = Field(validation_alias="WEBHOOK_PUBLIC_URL")
    database_url: NonEmptyStr = Field(validation_alias="DATABASE_URL")
    webhook_hmac_secret: NonEmptyStr = Field(validation_alias="WEBHOOK_HMAC_SECRET")
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")


@lru_cache(maxsize=1)
def load_settings() -> Settings:
    """Load and cache application settings."""

    return Settings()  # type: ignore[call-arg]
