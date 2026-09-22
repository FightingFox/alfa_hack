"""Синтетические тесты трёх сервисов ПД и генерация HTML-отчёта.

Прогоняет набор синтетических текстов через три сервиса:
  - gliner_famous   (http://127.0.0.1:8001/process)
  - ml_for_all_types(http://127.0.0.1:8005/process)
  - llm_service     (http://127.0.0.1:8003/process)

Для каждого текста задан ожидаемый набор типов ПД. По результатам считаются
precision/recall/F1 на уровне типов и формируется сводная HTML-таблица.

Запуск:  python bench_services.py [--out report.html]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from urllib import request

# --- Конфигурация сервисов -------------------------------------------------

SERVICES = {
    "gliner_famous": "http://127.0.0.1:8001/process",
    "ml_for_all_types": "http://127.0.0.1:8005/process",
    "llm_service": "http://127.0.0.1:8003/process",
}

# --- Синтетические тестовые случаи -----------------------------------------
# (текст, ожидаемые коды типов ПД)

TEST_CASES: list[tuple[str, set[str]]] = [
    (
        "Иван Петров, паспорт 4510 123456, ИНН 770123456789, email ivan.petrov@mail.ru, тел +7 (903) 123-45-67",
        {"FIO", "PASSPORT", "INN", "EMAIL", "PHONE"},
    ),
    (
        "Карта 4111 1111 1111 1111, CVV 123, PIN 1234, держатель IVAN PETROV",
        {"CARD_NUMBER", "CVV", "PIN", "CARDHOLDER"},
    ),
    (
        "СНИЛС 112-233-445 95, адрес 125167, г. Москва, ул. Правды, д. 24, кв. 5",
        {"SNILS", "ADDRESS"},
    ),
    (
        "Сегодня хорошая погода на улице.",
        set(),
    ),
    (
        "Поэт Александр Сергеевич Пушкин родился в 1799 году.",
        {"FAM_FIO"},
    ),
    (
        "Сервер 192.168.1.105, MAC 00:1A:2B:3C:4D:5E, порт 8080",
        {"IP_ADDRESS", "MAC_ADDRESS"},
    ),
    (
        "Анна Смирнова, дата рождения 15 марта 1985 года, гражданство РФ, работает инженером в Альфа-Банке",
        {"FIO", "DATE", "CITIZENSHIP", "PROFESSION", "COMPANY"},
    ),
    (
        "Военный билет АБ 12 1234567, загранпаспорт 75 №1234567, свидетельство о рождении I-МЮ №123456",
        {"MILITARY_ID", "FOREIGN_PASSPORT", "BIRTH_CERT"},
    ),
    (
        "Полис ОМС 5400000000000000, полис ДМС 0123456789, миграционная карта 0012345678",
        {"OMS", "DMC", "MIGRATION_CARD"},
    ),
    (
        "Логин vk.com @petr_ivanov87, пароль qwerty123, код подразделения 770-001, выдан ОВД Ленинского района",
        {"SOCIAL_LOGIN", "PASSWORD", "ISSUE_CODE", "ISSUING_AUTHORITY"},
    ),
    (
        "Водительское удостоверение 4510 123456, серия и номер прав 4510 123456",
        {"LICENSE"},
    ),
]


def _post(url: str, text: str, timeout: float = 60.0) -> dict:
    """POST /process и вернуть JSON-ответ."""
    body = json.dumps({"text": text}).encode("utf-8")
    req = request.Request(url, data=body, headers={"Content-Type": "application/json"})
    with request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _extract_entities(resp: dict) -> list[dict]:
    """Извлечь найденные сущности/типы с их слайсами из ответа сервиса.

    gliner_famous и llm_service возвращают сущности с полем `type` (список кодов)
    и `slice` ([start, end)). ml_for_all_types возвращает типы с полем `code`
    и `slice`. Нормализуем в единый список: {code, slice}.
    """
    entities: list[dict] = []
    for item in resp.get("data", []):
        if "type" in item:
            for code in item["type"]:
                entities.append({"code": code, "slice": item.get("slice")})
        elif "code" in item:
            entities.append({"code": item["code"], "slice": item.get("slice")})
    return entities


def _extract_types(resp: dict) -> set[str]:
    """Извлечь найденные коды типов ПД из ответа сервиса."""
    return {e["code"] for e in _extract_entities(resp)}


def _metrics(expected: set[str], found: set[str]) -> dict:
    """Precision/recall/F1 по типам ПД."""
    tp = len(expected & found)
    fp = len(found - expected)
    fn = len(expected - found)
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {
        "tp": tp, "fp": fp, "fn": fn,
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "f1": round(f1, 3),
    }


def run_case(service: str, url: str, text: str, expected: set[str]) -> dict:
    """Прогнать один текст через сервис и вернуть результат."""
    start = time.perf_counter()
    try:
        resp = _post(url, text)
        work_time = resp.get("work_time", round(time.perf_counter() - start, 3))
        entities = _extract_entities(resp)
        found = {e["code"] for e in entities}
        error = None
    except Exception as exc:  # noqa: BLE001
        work_time = round(time.perf_counter() - start, 3)
        entities = []
        found = set()
        error = str(exc)
    m = _metrics(expected, found)
    return {
        "service": service,
        "text": text,
        "expected": sorted(expected),
        "found": sorted(found),
        "entities": entities,
        "work_time": work_time,
        "error": error,
        **m,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Синтетические тесты сервисов ПД")
    parser.add_argument("--out", default="report.html", help="Путь к HTML-отчёту")
    args = parser.parse_args()

    results: list[dict] = []
    for service, url in SERVICES.items():
        for text, expected in TEST_CASES:
            results.append(run_case(service, url, text, expected))

    # Сводка по сервисам
    summary = {}
    for service in SERVICES:
        rows = [r for r in results if r["service"] == service]
        tp = sum(r["tp"] for r in rows)
        fp = sum(r["fp"] for r in rows)
        fn = sum(r["fn"] for r in rows)
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
        avg_time = sum(r["work_time"] for r in rows) / len(rows)
        errors = sum(1 for r in rows if r["error"])
        summary[service] = {
            "tp": tp, "fp": fp, "fn": fn,
            "precision": round(precision, 3),
            "recall": round(recall, 3),
            "f1": round(f1, 3),
            "avg_time": round(avg_time, 3),
            "errors": errors,
        }

    _write_html(args.out, results, summary)
    print(f"Отчёт сохранён: {args.out}")
    print("\n=== Сводка ===")
    for service, s in summary.items():
        print(f"{service:<20} P={s['precision']:.3f} R={s['recall']:.3f} F1={s['f1']:.3f} "
              f"avg_time={s['avg_time']:.3f}s errors={s['errors']}")
    return 0


def _write_html(path: str, results: list[dict], summary: dict) -> None:
    """Сформировать HTML-отчёт со сводной таблицей."""
    service_names = list(SERVICES.keys())

    def _slices_html(r: dict) -> str:
        """Список найденных типов с их слайсами."""
        if not r["entities"]:
            return '<span class="small">—</span>'
        parts = []
        for e in r["entities"]:
            sl = e.get("slice")
            sl_str = f"[{sl[0]}:{sl[1]}]" if sl else ""
            parts.append(f'<span class="ent">{_esc(e["code"])} <span class="sl">{sl_str}</span></span>')
        return '<br>'.join(parts)

    def _cell(r: dict) -> str:
        if r["error"]:
            return f'<td class="err" title="{r["error"]}">ERR</td>'
        f1 = r["f1"]
        cls = "good" if f1 >= 0.8 else ("mid" if f1 >= 0.5 else "bad")
        return (f'<td class="{cls}">F1={f1:.2f}<br>'
                f'<span class="small">P={r["precision"]:.2f} R={r["recall"]:.2f}</span><br>'
                f'<span class="small">{r["work_time"]:.2f}s</span><br>'
                f'{_slices_html(r)}</td>')

    rows_html = []
    for i, (text, expected) in enumerate(TEST_CASES):
        cells = ""
        for svc in service_names:
            r = next(x for x in results if x["service"] == svc and x["text"] == text)
            cells += _cell(r)
        rows_html.append(
            f"<tr><td class='case'>{i + 1}</td>"
            f"<td class='text'>{_esc(text)}</td>"
            f"<td class='exp'>{', '.join(sorted(expected)) or '—'}</td>"
            f"{cells}</tr>"
        )

    summary_rows = ""
    for svc in service_names:
        s = summary[svc]
        summary_rows += (
            f"<tr><td>{svc}</td>"
            f"<td>{s['tp']}</td><td>{s['fp']}</td><td>{s['fn']}</td>"
            f"<td>{s['precision']:.3f}</td><td>{s['recall']:.3f}</td>"
            f"<td class='f1'>{s['f1']:.3f}</td>"
            f"<td>{s['avg_time']:.3f}s</td><td>{s['errors']}</td></tr>"
        )

    html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<title>Сводный отчёт: сервисы ПД</title>
<style>
  body {{ font-family: -apple-system, Segoe UI, Roboto, sans-serif; margin: 24px; color: #222; }}
  h1 {{ font-size: 22px; }}
  h2 {{ font-size: 18px; margin-top: 32px; }}
  table {{ border-collapse: collapse; width: 100%; margin-top: 12px; }}
  th, td {{ border: 1px solid #ccc; padding: 8px 10px; text-align: center; font-size: 13px; }}
  th {{ background: #f0f0f0; }}
  td.text {{ text-align: left; max-width: 340px; }}
  td.exp {{ text-align: left; font-size: 12px; }}
  td.case {{ font-weight: bold; }}
  .good {{ background: #d4edda; }}
  .mid  {{ background: #fff3cd; }}
  .bad  {{ background: #f8d7da; }}
  .err  {{ background: #e2e3e5; color: #721c24; font-weight: bold; }}
  .small {{ font-size: 11px; color: #555; }}
  .f1 {{ font-weight: bold; }}
  .ent {{ display: inline-block; font-size: 11px; background: rgba(255,255,255,0.6); border-radius: 3px; padding: 1px 4px; margin: 1px 0; }}
  .sl {{ color: #666; font-family: monospace; }}
  .legend span {{ display: inline-block; padding: 2px 8px; margin-right: 8px; border-radius: 3px; }}
</style>
</head>
<body>
<h1>Сводный отчёт: сравнение сервисов распознавания ПД</h1>
<p>Синтетические тесты ({len(TEST_CASES)} кейсов) по трём сервисам. Метрики считаются по типам ПД (precision/recall/F1). В ячейках кейсов указаны найденные типы с их слайсами [start:end] в тексте.</p>

<h2>Сводная таблица по сервисам</h2>
<table>
  <tr><th>Сервис</th><th>TP</th><th>FP</th><th>FN</th><th>Precision</th><th>Recall</th><th>F1</th><th>Ср. время</th><th>Ошибки</th></tr>
  {summary_rows}
</table>

<h2>Детализация по кейсам</h2>
<div class="legend">
  <span class="good">F1 ≥ 0.8</span>
  <span class="mid">0.5 ≤ F1 &lt; 0.8</span>
  <span class="bad">F1 &lt; 0.5</span>
  <span class="err">Ошибка</span>
</div>
<table>
  <tr>
    <th>#</th><th>Текст</th><th>Ожидаемые типы</th>
    <th>gliner_famous</th><th>ml_for_all_types</th><th>llm_service</th>
  </tr>
  {''.join(rows_html)}
</table>

<p class="small">Сгенерировано {time.strftime('%Y-%m-%d %H:%M:%S')}</p>
</body>
</html>"""
    Path(path).write_text(html, encoding="utf-8")


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


if __name__ == "__main__":
    sys.exit(main())