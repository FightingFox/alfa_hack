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
        result: list[dict] | None = None,
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

    async def mask(self, text: str) -> list[dict]:
        self.started.set()
        if self.gate is not None:
            await self.gate.wait()
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.error:
            raise self.error
        return self.result or [{"text": f"masked_by_{self.config.name}", "type": ["FIO"]}]


def _provider(name: str, **kwargs) -> FakeProvider:
    return FakeProvider(name, **kwargs)


def test_runs_providers_concurrently() -> None:
    gate = asyncio.Event()
    p1 = _provider("p1", gate=gate)
    p2 = _provider("p2", gate=gate)
    orch = MaskingOrchestrator([p1, p2])

    async def run() -> dict[str, dict[str, list[dict] | float | None]]:
        task = asyncio.create_task(orch.mask("text"))
        await p1.started.wait()
        await p2.started.wait()
        # Оба стартовали до завершения — значит запущены параллельно
        assert not task.done()
        gate.set()
        return await task

    result = asyncio.run(run())
    assert result["p1"]["result"] == [{"text": "masked_by_p1", "type": ["FIO"]}]
    assert result["p2"]["result"] == [{"text": "masked_by_p2", "type": ["FIO"]}]
    assert isinstance(result["p1"]["elapsed"], float)
    assert isinstance(result["p2"]["elapsed"], float)
    assert result["p1"]["elapsed"] >= 0
    assert result["p2"]["elapsed"] >= 0


def test_returns_result_per_provider() -> None:
    p1 = _provider("p1", result=[{"text": "first", "type": ["FIO"]}])
    p2 = _provider("p2", result=[{"text": "second", "type": ["EMAIL"]}])
    orch = MaskingOrchestrator([p1, p2])

    result = asyncio.run(orch.mask("text"))
    assert result["p1"]["result"] == [{"text": "first", "type": ["FIO"]}]
    assert result["p2"]["result"] == [{"text": "second", "type": ["EMAIL"]}]


def test_waits_for_slowest_provider() -> None:
    p1 = _provider("p1", delay=0.1, result=[{"text": "slow", "type": ["FIO"]}])
    p2 = _provider("p2", delay=0.01, result=[{"text": "fast", "type": ["FIO"]}])
    orch = MaskingOrchestrator([p1, p2])

    async def run() -> dict[str, dict[str, list[dict] | float | None]]:
        task = asyncio.create_task(orch.mask("text"))
        await asyncio.sleep(0.05)
        # p2 уже завершился, но оркестратор ждёт p1 (последнего)
        assert not task.done()
        return await task

    result = asyncio.run(run())
    assert result["p1"]["result"] == [{"text": "slow", "type": ["FIO"]}]
    assert result["p2"]["result"] == [{"text": "fast", "type": ["FIO"]}]
    assert isinstance(result["p1"]["elapsed"], float)
    assert isinstance(result["p2"]["elapsed"], float)
    assert result["p1"]["elapsed"] >= result["p2"]["elapsed"]


def test_failed_provider_returns_none() -> None:
    p1 = _provider("p1", result=[{"text": "ok", "type": ["FIO"]}])
    p2 = _provider("p2", error=MaskingProviderError("e2"))
    orch = MaskingOrchestrator([p1, p2])

    result = asyncio.run(orch.mask("text"))
    assert result["p1"]["result"] == [{"text": "ok", "type": ["FIO"]}]
    assert result["p2"]["result"] is None
    assert isinstance(result["p2"]["elapsed"], float)
    assert result["p2"]["elapsed"] >= 0


def test_all_providers_failed_returns_none_values() -> None:
    p1 = _provider("p1", error=MaskingProviderError("e1"))
    p2 = _provider("p2", error=MaskingProviderError("e2"))
    orch = MaskingOrchestrator([p1, p2])

    result = asyncio.run(orch.mask("text"))
    assert result["p1"]["result"] is None
    assert result["p2"]["result"] is None


def test_no_providers_raises() -> None:
    orch = MaskingOrchestrator([])
    with pytest.raises(MaskingProviderError):
        asyncio.run(orch.mask("text"))
