"""End-to-end тесты всей цепочки маскирования.

Каждый запрос из датасета отправляется в `POST /process` main-module,
который проксирует текст во внешние сервисы (regex, llm, gliner, ml),
а полученные сущности сверяются с ожидаемыми `personal_data`.

Конфигурация через переменные окружения:
    MAIN_MODULE_URL  — базовый URL main-module (по умолчанию http://localhost:8000)
    DATASET_PATH     — путь к файлу датасета
                       (по умолчанию test-data/deepseek_json_20260922_merged.json)
"""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

import httpx
import pytest

MAIN_MODULE_URL = os.getenv("MAIN_MODULE_URL", "http://localhost:8000").rstrip("/")
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATASET_PATH = Path(
    os.getenv(
        "DATASET_PATH",
        PROJECT_ROOT / "test-data" / "deepseek_json_20260922_merged.json",
    )
)

PROCESS_URL = f"{MAIN_MODULE_URL}/process"
E2E_TIMEOUT = float(os.getenv("E2E_TIMEOUT", "120"))


def _load_dataset() -> list[dict]:
    if not DATASET_PATH.exists():
        pytest.fail(f"Датасет не найден: {DATASET_PATH}")
    with DATASET_PATH.open(encoding="utf-8") as fh:
        data = json.load(fh)
    return data["test_queries"]


def _collect_entities(results: dict) -> list[dict]:
    """Собирает все сущности из результатов всех сервисов."""
    entities: list[dict] = []
    for service, entry in results.items():
        result = entry.get("result")
        if not result:
            continue
        for entity in result:
            entities.append({**entity, "_service": service})
    return entities


def _normalize(value: str) -> str:
    """Нормализует значение для сравнения (убирает пробелы и регистр)."""
    return "".join(value.split()).lower()


def _values_match(expected_value: str, entity_text: str) -> bool:
    """Сверяет значение по типу и значению, игнорируя пробелы и регистр."""
    exp = _normalize(expected_value)
    act = _normalize(entity_text)
    return exp in act or act in exp


def _match_expected(expected: dict, entities: list[dict]) -> dict | None:
    """Ищет сущность, совпадающую с ожидаемой по типу и значению."""
    exp_type = expected["type"]
    exp_value = expected["value"]

    for entity in entities:
        if exp_type not in entity["type"]:
            continue
        if _values_match(exp_value, entity["text"]):
            return entity
    return None


def _report_mismatch(query: dict, expected: dict, entity: dict | None) -> str:
    exp_value = expected["value"]
    exp_type = expected["type"]

    lines = [
        f"  query id={query['id']} type={exp_type}",
        f"    expected: value={exp_value!r}",
    ]
    if entity is None:
        lines.append("    found: НЕ НАЙДЕНО")
    else:
        lines.append(
            f"    found: text={entity['text']!r} type={entity['type']} "
            f"score={entity['score']:.3f} service={entity['_service']}"
        )
    return "\n".join(lines)


@pytest.fixture(scope="module")
def client() -> httpx.Client:
    return httpx.Client(timeout=E2E_TIMEOUT)


@pytest.fixture(scope="module")
def dataset() -> list[dict]:
    return _load_dataset()


def test_main_module_health() -> None:
    resp = httpx.get(f"{MAIN_MODULE_URL}/health", timeout=10.0)
    assert resp.status_code == 200, (
        f"main-module недоступен по {MAIN_MODULE_URL}. "
        f"Запустите сервис (docker compose up) и проверьте MAIN_MODULE_URL."
    )


@pytest.mark.parametrize("query", _load_dataset(), ids=lambda q: f"q{q['id']}")
def test_query_matches_personal_data(
    client: httpx.Client, query: dict, request: pytest.FixtureRequest
) -> None:
    request.node.cached_query_id = query["id"]
    request.node.cached_char_count = len(query["text"])
    payload_id = f"dataset-{query['id']}-{uuid.uuid4().hex[:8]}"
    resp = client.post(
        PROCESS_URL,
        json={"payload": query["text"], "payload_id": payload_id},
    )
    assert resp.status_code == 200, (
        f"query id={query['id']}: HTTP {resp.status_code}: {resp.text[:300]}"
    )

    body = resp.json()
    request.node.cached_elapsed_by_service = {
        service: entry["elapsed"] for service, entry in body["results"].items()
    }

    entities = _collect_entities(body["results"])

    failures: list[str] = []
    for expected in query["personal_data"]:
        match = _match_expected(expected, entities)
        if match is None:
            failures.append(_report_mismatch(query, expected, None))

    assert not failures, "Несоответствия с ожидаемыми personal_data:\n" + "\n".join(
        failures
    )