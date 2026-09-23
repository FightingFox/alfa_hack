import asyncio
import contextlib
import logging
from collections import deque
from typing import AsyncIterator

import websockets
from websockets.asyncio.connection import State

from app.config import WebSocketPoolConfig

logger = logging.getLogger(__name__)


class WebSocketPoolError(Exception):
    """Ошибка при работе с пулом WebSocket-соединений."""


class WebSocketPool:
    """Автоматически расширяемый пул WebSocket-соединений.

    Пул растёт под нагрузкой (до ``max_connections``) и сжимается обратно к
    ``min_connections``, когда соединения простаивают. Соединения переиспользуются
    между запросами, что устраняет накладные расходы на рукопожатие при высоком RPS.
    """

    def __init__(self, url: str, config: WebSocketPoolConfig) -> None:
        self._url = url
        self._config = config
        self._idle: deque[websockets.WebSocketClientProtocol] = deque()
        self._total = 0
        self._lock = asyncio.Lock()
        self._shrink_task: asyncio.Task | None = None
        self._closed = False

    @property
    def total(self) -> int:
        return self._total

    @property
    def idle_count(self) -> int:
        return len(self._idle)

    async def start(self) -> None:
        """Запускает фоновую задачу сжатия пула и прогревает min-соединений."""
        self._shrink_task = asyncio.create_task(self._shrink_loop())
        for _ in range(self._config.min_connections):
            ws = await self._acquire_new()
            self._idle.append(ws)

    async def close(self) -> None:
        """Закрывает все соединения и останавливает фоновую задачу."""
        self._closed = True
        if self._shrink_task is not None:
            self._shrink_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._shrink_task
        while self._idle:
            ws = self._idle.popleft()
            await self._safe_close(ws)

    @contextlib.asynccontextmanager
    async def connection(self) -> AsyncIterator[websockets.WebSocketClientProtocol]:
        """Возвращает соединение из пула, переиспользуя простаивающие."""
        ws = await self._acquire()
        try:
            yield ws
        finally:
            await self._release(ws)

    async def _acquire(self) -> websockets.WebSocketClientProtocol:
        if self._closed:
            raise WebSocketPoolError("pool is closed")

        # Сначала пробуем взять простаивающее соединение.
        while self._idle:
            ws = self._idle.popleft()
            if self._is_open(ws):
                return ws
            self._total -= 1
            await self._safe_close(ws)

        # Нет свободных — создаём новое, если не упёрлись в максимум.
        if self._total < self._config.max_connections:
            return await self._acquire_new()

        # Достигнут максимум — ждём освобождения соединения.
        return await self._wait_for_idle()

    async def _acquire_new(self) -> websockets.WebSocketClientProtocol:
        async with self._lock:
            if self._total >= self._config.max_connections:
                return await self._wait_for_idle()
            try:
                ws = await asyncio.wait_for(
                    websockets.connect(self._url),
                    timeout=self._config.connect_timeout,
                )
            except (websockets.WebSocketException, asyncio.TimeoutError, OSError) as exc:
                raise WebSocketPoolError(f"failed to connect to '{self._url}': {exc}") from exc
            self._total += 1
            return ws

    async def _wait_for_idle(self) -> websockets.WebSocketClientProtocol:
        while True:
            if self._idle:
                ws = self._idle.popleft()
                if self._is_open(ws):
                    return ws
                self._total -= 1
                await self._safe_close(ws)
                continue
            await asyncio.sleep(0.01)

    async def _release(self, ws: websockets.WebSocketClientProtocol) -> None:
        if self._closed or not self._is_open(ws):
            self._total -= 1
            await self._safe_close(ws)
            return
        self._idle.append(ws)

    async def _shrink_loop(self) -> None:
        """Периодически закрывает лишние простаивающие соединения."""
        while not self._closed:
            await asyncio.sleep(self._config.idle_shrink_interval)
            await self._shrink()

    async def _shrink(self) -> None:
        target = self._config.min_connections
        while len(self._idle) > target and self._total > target:
            ws = self._idle.popleft()
            self._total -= 1
            await self._safe_close(ws)

    async def _safe_close(self, ws: websockets.WebSocketClientProtocol) -> None:
        with contextlib.suppress(websockets.WebSocketException):
            await ws.close()

    @staticmethod
    def _is_open(ws: websockets.WebSocketClientProtocol) -> bool:
        return getattr(ws, "state", None) == State.OPEN
