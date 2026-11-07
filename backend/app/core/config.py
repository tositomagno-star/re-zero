from functools import lru_cache
from pathlib import Path
from typing import Literal, Self

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Crônicas do Reino API"
    app_environment: Literal["development", "production"] | None = None
    database_url: str = "postgresql+asyncpg://localhost/cronicas_do_reino"
    asset_storage_path: Path = Path(__file__).resolve().parents[2] / "uploads" / "assets"
    asset_max_upload_bytes: int = Field(default=5 * 1024 * 1024, ge=1, le=5 * 1024 * 1024)
    frontend_origins: list[str] = [
        "http://localhost:8080",
        "http://127.0.0.1:8080",
    ]
    cookie_secure: bool = False
    player_session_hours: int = 12
    admin_session_hours: int = 4
    auth_rate_limit_attempts: int = 5
    auth_rate_limit_minutes: int = 15
    auth_lockout_minutes: int = 15
    app_secret_key: str = "development-only-change-in-production"
    discord_client_id: str | None = None
    discord_client_secret: str | None = None
    discord_redirect_uri: str | None = None
    discord_bot_token: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @model_validator(mode="after")
    def validate_cookie_security(self) -> Self:
        if not self.cookie_secure and self.app_environment != "development":
            raise ValueError(
                "COOKIE_SECURE=false is only allowed when "
                "APP_ENVIRONMENT=development."
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
