import asyncio
from abc import ABC, abstractmethod

import httpx
import websockets

from app.config import MaskingServiceConfig
from app.ws_pool import WebSocketPool, WebSocketPoolError


class MaskingProviderError(Exception):
    """Ошибка при обращении к сервису маскирования."""


class MaskingProvider(ABC):
    """Абстракция сервиса маскирования."""

    def __init__(self, config: MaskingServiceConfig) -> None:
        self.config = config

    @abstractmethod
    async def mask(self, text: str) -> str:
        """Маскирует строку. Должен быть ограничен таймаутом из конфига."""


class RestMaskingProvider(MaskingProvider):
    """REST-провайдер маскирования."""

    async def mask(self, text: str) -> str:
        try:
            async with httpx.AsyncClient(timeout=self.config.timeout) as client:
                response = await client.post(
                    self.config.url,
                    json={"text": text},
                )
                response.raise_for_status()
                data = response.json()
                return data["result"]
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            raise MaskingProviderError(
                f"rest provider '{self.config.name}' error: {exc}"
            ) from exc


class WebSocketMaskingProvider(MaskingProvider):
    """WebSocket-провайдер маскирования с автоматически расширяемым пулом соединений."""

    def __init__(self, config: MaskingServiceConfig) -> None:
        super().__init__(config)
        self._pool = WebSocketPool(config.url, config.pool)

    async def start(self) -> None:
        await self._pool.start()

    async def close(self) -> None:
        await self._pool.close()

    async def mask(self, text: str) -> str:
        try:
            async with self._pool.connection() as ws:
                await asyncio.wait_for(ws.send(text), timeout=self.config.timeout)
                result = await asyncio.wait_for(ws.recv(), timeout=self.config.timeout)
                return str(result)
        except (websockets.WebSocketException, asyncio.TimeoutError, WebSocketPoolError) as exc:
            raise MaskingProviderError(
                f"websocket provider '{self.config.name}' error: {exc}"
            ) from exc


def build_provider(config: MaskingServiceConfig) -> MaskingProvider:
    if config.protocol == "rest":
        return RestMaskingProvider(config)
    if config.protocol == "websocket":
        return WebSocketMaskingProvider(config)
    raise ValueError(f"unsupported protocol: {config.protocol}")
