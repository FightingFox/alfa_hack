import asyncio

import pytest

from app.config import MaskingServiceConfig
from app.orchestrator import MaskingOrchestrator, MaskingProviderError
from app.providers import MaskingProvider


class FakeProvider(MaskingProvider):
    def __init__(
        self,
        name: str,
        delay: float = 0.0,
        result: str | None = None,
        error: Exception | None = None,
        gate: asyncio.Event | None = None,
    ):
        super().__init__(
            MaskingServiceConfig(name=name, protocol="rest", url="http://x", timeout=10.0)
        )
        self.delay = delay
        self.result = result
        self.error = error
        self.gate = gate
        self.started = asyncio.Event()

    async def mask(self, text: str) -> str:
        self.started.set()
        if self.gate is not None:
            await self.gate.wait()
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.error:
            raise self.error
        return self.result or f"masked_by_{self.config.name}"


def _provider(name: str, **kwargs) -> FakeProvider:
    return FakeProvider(name, **kwargs)


def test_runs_providers_concurrently() -> None:
    gate = asyncio.Event()
    p1 = _provider("p1", gate=gate)
    p2 = _provider("p2", gate=gate)
    orch = MaskingOrchestrator([p1, p2])

    async def run() -> str:
        task = asyncio.create_task(orch.mask("text"))
        await p1.started.wait()
        await p2.started.wait()
        # Оба стартовали до завершения — значит запущены параллельно
        assert not task.done()
        gate.set()
        return await task

    result = asyncio.run(run())
    assert result in {"masked_by_p1", "masked_by_p2"}


def test_returns_last_completed_result() -> None:
    p1 = _provider("p1", delay=0.1, result="first")
    p2 = _provider("p2", delay=0.01, result="second")
    orch = MaskingOrchestrator([p1, p2])

    result = asyncio.run(orch.mask("text"))
    # p2 завершился последним (меньшая задержка -> раньше), но gather возвращает в порядке списка.
    # "последний завершившийся" здесь интерпретируем как последний в списке успешный.
    assert result == "first"


def test_waits_for_slowest_provider() -> None:
    p1 = _provider("p1", delay=0.1, result="slow")
    p2 = _provider("p2", delay=0.01, result="fast")
    orch = MaskingOrchestrator([p1, p2])

    async def run() -> str:
        task = asyncio.create_task(orch.mask("text"))
        await asyncio.sleep(0.05)
        # p2 уже завершился, но оркестратор ждёт p1 (последнего)
        assert not task.done()
        return await task

    result = asyncio.run(run())
    assert result == "slow"


def test_all_providers_failed_raises() -> None:
    p1 = _provider("p1", error=MaskingProviderError("e1"))
    p2 = _provider("p2", error=MaskingProviderError("e2"))
    orch = MaskingOrchestrator([p1, p2])

    with pytest.raises(MaskingProviderError):
        asyncio.run(orch.mask("text"))


def test_no_providers_raises() -> None:
    orch = MaskingOrchestrator([])
    with pytest.raises(MaskingProviderError):
        asyncio.run(orch.mask("text"))
