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

    async def mask(self, text: str) -> str:
        """Маскирует строку всеми провайдерами параллельно.

        Дожидается завершения всех провайдеров (самого медленного) и возвращает
        результат последнего завершившегося успешного провайдера.
        Если все провайдеры упали — поднимает MaskingProviderError.
        """
        if not self._providers:
            raise MaskingProviderError("no masking providers configured")

        async def _run(provider: MaskingProvider) -> str:
            try:
                return await asyncio.wait_for(
                    provider.mask(text),
                    timeout=provider.config.timeout,
                )
            except MaskingProviderError:
                raise
            except Exception as exc:
                raise MaskingProviderError(
                    f"provider '{provider.config.name}' failed: {exc}"
                ) from exc

        tasks = [_run(p) for p in self._providers]

        # Ждём завершения всех, запоминая порядок завершения
        completed: list[str] = []
        for coro in asyncio.as_completed(tasks):
            try:
                completed.append(await coro)
            except MaskingProviderError:
                continue

        if completed:
            return completed[-1]

        raise MaskingProviderError("all masking providers failed")


_orchestrator: MaskingOrchestrator | None = None


def get_orchestrator() -> MaskingOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        settings = get_settings()
        providers = [build_provider(cfg) for cfg in settings.masking_services]
        _orchestrator = MaskingOrchestrator(providers)
    return _orchestrator
