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

    async def get(self, payload_id: str) -> Record | None:
        return self._records.get(payload_id)

    async def put(self, payload_id: str, record: Record) -> None:
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
    body = mask_resp.json()
    assert body["results"] == {
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
    assert body["masked_text"] == "{{ FIO 1 }}"
    assert body["replacements"] == [
        {
            "slice": [0, len(original)],
            "types": ["FIO"],
            "mask": "{{ FIO 1 }}",
            "original_text": original,
        }
    ]
    assert fake_orchestrator.calls == [original]

    # Обратный шаг: демаскирование по masked_text
    unmask_resp = client.post(
        "/process",
        json={"payload": body["masked_text"], "payload_id": payload_id},
    )
    assert unmask_resp.status_code == 200
    assert unmask_resp.json()["results"] == original


def test_process_unmask_restores_from_replacements(monkeypatch) -> None:
    """Демаскирование восстанавливает оригинал, заменяя маски из replacements."""
    fake_orchestrator, _ = _patch_deps(monkeypatch)
    payload_id = "unmask-restore-id"
    original = "Клиент Иванов Иван Иванович, паспорт 4509 123456"

    mask_resp = client.post(
        "/process",
        json={"payload": original, "payload_id": payload_id},
    )
    assert mask_resp.status_code == 200
    masked_text = mask_resp.json()["masked_text"]

    # Демаскирование по замаскированному тексту
    unmask_resp = client.post(
        "/process",
        json={"payload": masked_text, "payload_id": payload_id},
    )
    assert unmask_resp.status_code == 200
    assert unmask_resp.json()["results"] == original


def test_process_unmask_multiple_replacements(monkeypatch) -> None:
    """Несколько масок в тексте восстанавливаются в правильном порядке."""
    fake_orchestrator, _ = _patch_deps(
        monkeypatch,
        fake_orchestrator=FakeOrchestrator(
            result={
                "regex": {
                    "result": [
                        {
                            "text": "Иванов Иван",
                            "type": ["FIO"],
                            "score": 1.0,
                            "slice": [0, 11],
                            "will_be_used": True,
                        },
                        {
                            "text": "+7 900 123-45-67",
                            "type": ["PHONE"],
                            "score": 1.0,
                            "slice": [18, 33],
                            "will_be_used": True,
                        },
                    ],
                    "elapsed": 0.1,
                }
            }
        ),
    )
    payload_id = "unmask-multi-id"
    original = "Иванов Иван, тел. +7 900 123-45-67"

    mask_resp = client.post(
        "/process",
        json={"payload": original, "payload_id": payload_id},
    )
    assert mask_resp.status_code == 200
    body = mask_resp.json()
    assert len(body["replacements"]) == 2

    unmask_resp = client.post(
        "/process",
        json={"payload": body["masked_text"], "payload_id": payload_id},
    )
    assert unmask_resp.status_code == 200
    assert unmask_resp.json()["results"] == original


def test_process_unmask_unknown_payload_id_masks_instead(monkeypatch) -> None:
    """Неизвестный payload_id трактуется как маскирование (новая запись)."""
    fake_orchestrator, _ = _patch_deps(monkeypatch)
    resp = client.post(
        "/process",
        json={"payload": "Иванов Иван", "payload_id": "never-registered"},
    )
    assert resp.status_code == 200
    assert resp.json()["masked_text"] == "{{ FIO 1 }}"


def test_process_unmask_non_string_payload_returns_422(monkeypatch) -> None:
    """payload_id известен, но payload не строка и не валидный dict — 422."""
    fake_orchestrator, _ = _patch_deps(monkeypatch)
    payload_id = "non-string-id"
    client.post(
        "/process",
        json={"payload": "Иванов Иван", "payload_id": payload_id},
    )

    resp = client.post(
        "/process",
        json={"payload": {"some": "dict"}, "payload_id": payload_id},
    )
    assert resp.status_code == 422


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
