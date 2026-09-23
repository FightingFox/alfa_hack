"""Pytest-хуки для сбора результатов e2e-тестов и генерации HTML-отчёта."""

from __future__ import annotations

import pytest
from report import collector


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
    if not collector.rows:
        return
    html_path = collector.save()
    json_path = collector.save_json()
    print(f"\nE2E отчёт сохранён: {html_path}")
    print(f"JSON с данными: {json_path}")
