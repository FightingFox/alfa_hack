from fastapi.testclient import TestClient

from app.main import app
from app.orchestrator import MaskingProviderError
from app.store import Record

client = TestClient(app)


class FakeOrchestrator:
    def __init__(
        self,
        result: dict[str, dict[str, list[dict] | float | None]] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.result = result
        self.error = error
        self.calls: list[str] = []

    async def mask(self, text: str) -> dict[str, dict[str, list[dict] | float | None]]:
        self.calls.append(text)
        if self.error:
            raise self.error
        return self.result or {
            "regex": {
                "result": [
                    {
                        "text": f"masked({text})",
                        "type": ["FIO"],
                        "score": 1.0,
                        "slice": [0, len(text)],
                        "will_be_used": True,
                    }
                ],
                "elapsed": 0.1,
            }
        }


class FakeStore:
    def __init__(self) -> None:
        self._records: dict[str, Record] = {}

    def get(self, payload_id: str) -> Record | None:
        return self._records.get(payload_id)

    def put(self, payload_id: str, record: Record) -> None:
        self._records[payload_id] = record


def _patch_deps(monkeypatch, fake_orchestrator=None, fake_store=None):
    fake_orchestrator = fake_orchestrator or FakeOrchestrator()
    fake_store = fake_store or FakeStore()
    monkeypatch.setattr("app.routers.process.get_orchestrator", lambda: fake_orchestrator)
    monkeypatch.setattr("app.routers.process.get_store", lambda: fake_store)
    return fake_orchestrator, fake_store


def test_process_mask_then_unmask(monkeypatch) -> None:
    fake_orchestrator, _ = _patch_deps(monkeypatch)
    payload_id = "8a77d363c7c044b49b41d7b8a448243a"
    original = "Клиент Иванов Иван Иванович, паспорт 4509 123456"

    # Прямой шаг: маскирование через внешние сервисы
    mask_resp = client.post(
        "/process",
        json={"payload": original, "payload_id": payload_id},
    )
    assert mask_resp.status_code == 200
    masked = mask_resp.json()["results"]
    assert masked == {
        "regex": {
            "result": [
                {
                    "text": f"masked({original})",
                    "type": ["FIO"],
                    "score": 1.0,
                    "slice": [0, len(original)],
                    "will_be_used": True,
                }
            ],
            "elapsed": 0.1,
        }
    }
    assert fake_orchestrator.calls == [original]

    # Обратный шаг: демаскирование
    unmask_resp = client.post(
        "/process",
        json={"payload": masked, "payload_id": payload_id},
    )
    assert unmask_resp.status_code == 200
    assert unmask_resp.json()["results"] == original


def test_process_unknown_payload_id_returns_400(monkeypatch) -> None:
    _patch_deps(monkeypatch)
    payload_id = "unknown-id"

    # Сначала зарегистрируем payload_id
    client.post(
        "/process",
        json={"payload": "Иванов Иван Иванович, паспорт 4509 123456", "payload_id": payload_id},
    )

    # Отправляем несовпадающую строку
    resp = client.post(
        "/process",
        json={"payload": "Совсем другая строка", "payload_id": payload_id},
    )
    assert resp.status_code == 400


def test_process_missing_fields_returns_422() -> None:
    resp = client.post("/process", json={"payload": "test"})
    assert resp.status_code == 422


def test_process_masking_service_error_returns_502(monkeypatch) -> None:
    _patch_deps(
        monkeypatch,
        fake_orchestrator=FakeOrchestrator(error=MaskingProviderError("boom")),
    )
    resp = client.post(
        "/process",
        json={"payload": "test", "payload_id": "fail-id"},
    )
    assert resp.status_code == 502
