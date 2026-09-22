import asyncio

from app.config import get_settings
from app.providers import MaskingProvider, MaskingProviderError, build_provider


class MaskingOrchestrator:
    """Запускает все провайдеры маскирования асинхронно, каждый с таймаутом."""

    def __init__(self, providers: list[MaskingProvider]) -> None:
        self._providers = providers

    async def start(self) -> None:
        """Инициализирует провайдеров (например, прогревает пулы соединений)."""
        for provider in self._providers:
            start = getattr(provider, "start", None)
            if start is not None:
                await start()

    async def close(self) -> None:
        """Освобождает ресурсы провайдеров (закрывает пулы соединений)."""
        for provider in self._providers:
            close = getattr(provider, "close", None)
            if close is not None:
                await close()

    async def mask(self, text: str) -> dict[str, dict[str, list[dict] | float | None]]:
        """Маскирует строку всеми провайдерами параллельно.

        Возвращает словарь, где ключ — имя сервиса, а значение — словарь с
        результатом и временем выполнения в секундах. Если сервис не дал
        успешного ответа, результат будет None.
        """
        if not self._providers:
            raise MaskingProviderError("no masking providers configured")

        async def _run(
            provider: MaskingProvider,
        ) -> tuple[str, dict[str, list[dict] | float | None]]:
            start = asyncio.get_running_loop().time()
            try:
                result = await provider.mask(text)
                elapsed = asyncio.get_running_loop().time() - start
                return provider.config.name, {"result": result, "elapsed": elapsed}
            except MaskingProviderError:
                elapsed = asyncio.get_running_loop().time() - start
                return provider.config.name, {"result": None, "elapsed": elapsed}
            except Exception:
                elapsed = asyncio.get_running_loop().time() - start
                return provider.config.name, {"result": None, "elapsed": elapsed}

        tasks = [_run(p) for p in self._providers]

        results: dict[str, dict[str, list[dict] | float | None]] = {}
        for coro in asyncio.as_completed(tasks):
            name, entry = await coro
            results[name] = entry

        return results


_orchestrator: MaskingOrchestrator | None = None


def get_orchestrator() -> MaskingOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        settings = get_settings()
        providers = [build_provider(cfg) for cfg in settings.masking_services]
        _orchestrator = MaskingOrchestrator(providers)
    return _orchestrator
