from functools import lru_cache
from typing import Literal

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class MaskingServiceConfig(BaseModel):
    name: str
    protocol: Literal["rest", "websocket"]
    url: str
    timeout: float = Field(default=10.0, gt=0)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    app_name: str = "main-module"
    app_env: str = "development"
    debug: bool = True
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "info"

    # Внешние сервисы маскирования (REST и/или WebSocket)
    masking_services: list[MaskingServiceConfig] = [
        MaskingServiceConfig(name="default", protocol="rest", url="http://localhost:9000")
    ]

    # Redis для хранения корреляции payload_id
    redis_url: str = "redis://localhost:6379/0"


@lru_cache
def get_settings() -> Settings:
    return Settings()
