from functools import lru_cache
from typing import Literal

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class WebSocketPoolConfig(BaseModel):
    """Настройки автоматически расширяемого пула WebSocket-соединений."""

    min_connections: int = Field(default=4, ge=0)
    max_connections: int = Field(default=64, ge=1)
    idle_shrink_interval: float = Field(default=5.0, gt=0)
    idle_shrink_ratio: float = Field(default=0.5, gt=0, le=1.0)
    connect_timeout: float = Field(default=10.0, gt=0)
    connect_retry_delay: float = Field(default=1.0, gt=0)
    connect_retry_max_delay: float = Field(default=30.0, gt=0)


class MaskingServiceConfig(BaseModel):
    name: str
    protocol: Literal["rest", "websocket"]
    url: str
    timeout: float = Field(default=10.0, gt=0)
    pool: WebSocketPoolConfig = Field(default_factory=WebSocketPoolConfig)


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
    workers: int = 4
    log_level: str = "info"

    # Префикс пути, под которым сервис доступен через балансировщик
    # (например, "/main-module"). Используется для генерации корректных
    # URL в Swagger UI / OpenAPI-спецификации.
    root_path: str = ""

    # Внешние сервисы маскирования (REST и/или WebSocket)
    masking_services: list[MaskingServiceConfig] = [
        MaskingServiceConfig(name="default", protocol="rest", url="http://localhost:9000")
    ]

    # Redis для хранения корреляции payload_id
    redis_url: str = "redis://localhost:6379/0"


@lru_cache
def get_settings() -> Settings:
    return Settings()
