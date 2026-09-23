"""Pytest-хуки для сбора результатов e2e-тестов и генерации HTML-отчёта.

Поддерживает параллельный запуск через pytest-xdist:
    - каждый воркер сохраняет свои данные в отдельный JSON-файл;
    - главный процесс собирает данные всех воркеров и формирует общий отчёт.
"""

from __future__ import annotations

import pytest

from report import (
    ReportCollector,
    clear_worker_data,
    collector,
    load_all_worker_data,
    save_worker_data,
)


def _is_worker(session) -> bool:
    """True, если текущий процесс — воркер pytest-xdist."""
    return hasattr(session.config, "workerinput")


def _worker_id(session) -> str:
    return session.config.workerinput.get("workerid", "unknown")


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()

    if call.when != "call":
        return

    query_id = getattr(item, "cached_query_id", None)
    if query_id is None:
        return

    elapsed_by_service = getattr(item, "cached_elapsed_by_service", {})
    char_count = getattr(item, "cached_char_count", 0)
    passed = report.passed
    error = None
    if report.failed:
        error = str(report.longrepr) if report.longrepr else "failed"

    collector.add_row(
        query_id=query_id,
        char_count=char_count,
        elapsed_by_service=elapsed_by_service,
        passed=passed,
        error=error,
    )


def pytest_sessionfinish(session, exitstatus):
    if _is_worker(session):
        # Воркер: сохраняем свои данные во временный файл.
        if collector.rows:
            save_worker_data(_worker_id(session), collector.to_dict())
        return

    # Главный процесс: собираем данные всех воркеров и формируем отчёт.
    merged = ReportCollector()
    for data in load_all_worker_data():
        merged.merge(ReportCollector.from_dict(data))
    if not merged.rows:
        return

    html_path = merged.save()
    json_path = merged.save_json()
    clear_worker_data()
    print(f"\nE2E отчёт сохранён: {html_path}")
    print(f"JSON с данными: {json_path}")
