from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://kquant:kquant@postgres:5432/kquant"
    redis_url: str = "redis://redis:6379/0"
    cors_origins: str = "http://localhost:3000"
    dart_api_key: str | None = None
    # Authentication must fail closed unless local development explicitly
    # opts into the disabled mode.
    auth_mode: Literal["session", "cognito", "disabled"] = "session"
    auth_cookie_secret: str | None = None
    auth_session_cookie_name: str = "kq_session"
    auth_csrf_cookie_name: str = "kq_csrf"
    auth_csrf_header_name: str = "x-csrf-token"
    auth_session_idle_ttl_seconds: int = 60 * 60 * 12
    auth_session_absolute_ttl_seconds: int = 60 * 60 * 24 * 7
    cognito_region: str | None = None
    cognito_user_pool_id: str | None = None
    cognito_app_client_id: str | None = None
    stripe_secret_key: str | None = None
    stripe_webhook_secret: str | None = None
    stripe_price_id: str | None = None
    frontend_url: str = "http://localhost:3000"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def allowed_origins(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.cors_origins.split(",")
            if origin.strip()
        ]


@lru_cache
def get_settings() -> Settings:
    return Settings()
