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


def _slice_overlap(a: list[int], b: list[int]) -> int:
    """Длина пересечения двух слайсов [start, end)."""
    return max(0, min(a[1], b[1]) - max(a[0], b[0]))


def _match_expected(expected: dict, entities: list[dict]) -> dict | None:
    """Ищет сущность, совпадающую с ожидаемой по типу и слайсу."""
    exp_type = expected["type"]
    exp_slice = expected["slice"]

    best: dict | None = None
    best_overlap = 0
    for entity in entities:
        if exp_type not in entity["type"]:
            continue
        overlap = _slice_overlap(exp_slice, entity["slice"])
        if overlap > best_overlap:
            best_overlap = overlap
            best = entity
    return best


def _report_mismatch(query: dict, expected: dict, entity: dict | None) -> str:
    text = query["text"]
    exp_slice = expected["slice"]
    exp_value = expected["value"]
    exp_type = expected["type"]
    actual_text = text[exp_slice[0] : exp_slice[1]] if exp_slice[1] <= len(text) else "?"

    lines = [
        f"  query id={query['id']} type={exp_type}",
        f"    expected: value={exp_value!r} slice={exp_slice}",
        f"    actual text at slice: {actual_text!r}",
    ]
    if entity is None:
        lines.append("    found: НЕ НАЙДЕНО")
    else:
        lines.append(
            f"    found: text={entity['text']!r} type={entity['type']} "
            f"slice={entity['slice']} score={entity['score']:.3f} "
            f"service={entity['_service']}"
        )
    return "\n".join(lines)


@pytest.fixture(scope="module")
def client() -> httpx.Client:
    return httpx.Client(timeout=30.0)


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
def test_query_matches_personal_data(client: httpx.Client, query: dict) -> None:
    payload_id = f"dataset-{query['id']}-{uuid.uuid4().hex[:8]}"
    resp = client.post(
        PROCESS_URL,
        json={"payload": query["text"], "payload_id": payload_id},
    )
    assert resp.status_code == 200, (
        f"query id={query['id']}: HTTP {resp.status_code}: {resp.text[:300]}"
    )

    body = resp.json()
    entities = _collect_entities(body["results"])

    failures: list[str] = []
    for expected in query["personal_data"]:
        match = _match_expected(expected, entities)
        if match is None:
            failures.append(_report_mismatch(query, expected, None))
            continue

        exp_slice = expected["slice"]
        exp_value = expected["value"]
        overlap = _slice_overlap(exp_slice, match["slice"])
        if overlap <= 0:
            failures.append(_report_mismatch(query, expected, match))
            continue

        actual_value = query["text"][exp_slice[0] : exp_slice[1]]
        if actual_value != exp_value:
            failures.append(_report_mismatch(query, expected, match))

    assert not failures, "Несоответствия с ожидаемыми personal_data:\n" + "\n".join(
        failures
    )