"""Сбор данных о прогоне e2e-тестов и генерация HTML-отчёта.

Таблица отчёта:
    столбцы — микросервисы + общий результат (успех/неудача);
    строки — тесты, в ячейках время выполнения запроса по данному тесту.
"""

from __future__ import annotations

import html
import json
import os
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = Path(
    os.getenv("E2E_REPORT_PATH", PROJECT_ROOT / "e2e_report.html")
)


class ReportCollector:
    """Накопитель данных о прогоне тестов."""

    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []
        self.services: list[str] = []

    def add_service(self, name: str) -> None:
        if name not in self.services:
            self.services.append(name)

    def add_row(
        self,
        query_id: int,
        char_count: int,
        elapsed_by_service: dict[str, float],
        passed: bool,
        error: str | None = None,
    ) -> None:
        for name in elapsed_by_service:
            self.add_service(name)
        self.rows.append(
            {
                "query_id": query_id,
                "char_count": char_count,
                "elapsed_by_service": elapsed_by_service,
                "passed": passed,
                "error": error,
            }
        )

    def _render_table(self) -> str:
        columns = ["Тест", "Символов"] + self.services + ["Результат"]
        header = "".join(f"<th>{html.escape(c)}</th>" for c in columns)

        body_rows: list[str] = []
        for row in self.rows:
            cells = [f"<td>q{row['query_id']}</td>", f"<td>{row['char_count']}</td>"]
            for service in self.services:
                elapsed = row["elapsed_by_service"].get(service)
                if elapsed is None:
                    cells.append('<td class="na">—</td>')
                else:
                    cells.append(f'<td class="time">{elapsed:.3f} с</td>')

            if row["passed"]:
                cells.append('<td class="ok">OK</td>')
            else:
                title = html.escape(row["error"] or "")
                cells.append(f'<td class="fail" title="{title}">FAIL</td>')

            body_rows.append("<tr>" + "".join(cells) + "</tr>")

        return (
            "<table>\n"
            f"<thead><tr>{header}</tr></thead>\n"
            "<tbody>\n"
            + "\n".join(body_rows)
            + "\n</tbody>\n"
            "</table>"
        )

    def _render_summary(self) -> str:
        total = len(self.rows)
        passed = sum(1 for r in self.rows if r["passed"])
        failed = total - passed
        return (
            f"<p>Всего тестов: <b>{total}</b>; "
            f"успешно: <b class='ok'>{passed}</b>; "
            f"неудачно: <b class='fail'>{failed}</b></p>"
        )

    def render_html(self) -> str:
        return f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<title>E2E отчёт</title>
<style>
  body {{ font-family: -apple-system, Segoe UI, Roboto, sans-serif; margin: 24px; }}
  h1 {{ font-size: 20px; }}
  table {{ border-collapse: collapse; width: 100%; font-size: 13px; }}
  th, td {{ border: 1px solid #ccc; padding: 6px 10px; text-align: center; }}
  th {{ background: #f0f0f0; }}
  td.time {{ font-variant-numeric: tabular-nums; }}
  td.na {{ color: #999; }}
  td.ok {{ color: #1a7f37; font-weight: 600; }}
  td.fail {{ color: #cf222e; font-weight: 600; }}
  .ok {{ color: #1a7f37; }}
  .fail {{ color: #cf222e; }}
</style>
</head>
<body>
<h1>E2E отчёт: время работы сервисов</h1>
{self._render_summary()}
{self._render_table()}
</body>
</html>
"""

    def save(self, path: str | Path = REPORT_PATH) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.render_html(), encoding="utf-8")
        return path

    def save_json(self, path: str | Path | None = None) -> Path:
        path = Path(path) if path else REPORT_PATH.with_suffix(".json")
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "services": self.services,
            "rows": self.rows,
        }
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return path


collector = ReportCollector()