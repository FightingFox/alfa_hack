"""Тест сервисов распознавания ПД на реальных тестовых данных.

Использует тестовые данные из `deepseek_json_20260922_merged.json` (68 запросов
с ожидаемыми типами ПД и значениями) и дополнительный прогон по длинному
связному тексту `big_text.txt`. Прогоняет каждый запрос через развёрнутые
сервисы (без балансировщика) и формирует HTML-отчёт в подпапке `test_results`.

Проверяются:
  - точность определения типов ПД (precision/recall/F1 по типам);
  - попадание в слайсы: для каждого ожидаемого значения ПД проверяется, что
    сервис вернул сущность нужного типа, слайс которой покрывает фактическую
    позицию значения в тексте.

Запуск:  python test_services.py [--out test_results/report.html]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from pathlib import Path
from typing import Any

import httpx
import websockets

# --- Конфигурация сервисов (развёрнуты без балансировщика) -----------------

SERVICES: dict[str, dict[str, Any]] = {
    "gliner_famous": {
        "protocol": "rest",
        "url": "http://127.0.0.1:8001/process",
    },
    "llm_service": {
        "protocol": "rest",
        "url": "http://127.0.0.1:8003/process",
    },
    "ml_for_all_types": {
        "protocol": "rest",
        "url": "http://127.0.0.1:8005/process",
    },
    "regex_module": {
        "protocol": "websocket",
        "url": "ws://127.0.0.1:8006/scan",
    },
}

TEST_DATA = Path(__file__).parent / "deepseek_json_20260922_merged.json"
BIG_TEXT_FILE = Path(__file__).parent / "big_text.txt"
DEFAULT_OUT = Path(__file__).parent / "test_results" / "report.html"

# Ожидаемые ПД в big_text.txt (длинный связный текст с одним телефоном).
BIG_TEXT_EXPECTED: list[dict] = [
    {"type": "PHONE", "value": "8 495 123-45-67"},
]


def load_test_data() -> list[dict]:
    """Загрузить тестовые запросы из JSON и добавить прогон по big_text.txt."""
    with TEST_DATA.open(encoding="utf-8") as f:
        data = json.load(f)
    queries = list(data["test_queries"])
    if BIG_TEXT_FILE.exists():
        queries.append({
            "id": len(queries) + 1,
            "text": BIG_TEXT_FILE.read_text(encoding="utf-8"),
            "personal_data": BIG_TEXT_EXPECTED,
        })
    return queries


def actual_slice(text: str, value: str) -> list[int] | None:
    """Фактическая позиция значения в тексте (тестовые слайсы ненадёжны)."""
    pos = text.find(value)
    if pos == -1:
        return None
    return [pos, pos + len(value)]


def extract_entities(resp: dict) -> list[dict]:
    """Извлечь сущности {code, slice} из ответа сервиса.

    Все сервисы возвращают `data` со списком сущностей, у каждой есть поле
    `type` (список кодов) и `slice` ([start, end)).
    """
    entities: list[dict] = []
    for item in resp.get("data", []):
        types = item.get("type") or []
        if isinstance(types, str):
            types = [types]
        for code in types:
            entities.append({"code": code, "slice": item.get("slice")})
    return entities


async def call_rest(client: httpx.AsyncClient, url: str, text: str) -> dict:
    """Вызвать REST-сервис POST /process."""
    resp = await client.post(url, json={"text": text}, timeout=120.0)
    resp.raise_for_status()
    return resp.json()


async def call_websocket(url: str, text: str) -> dict:
    """Вызвать WebSocket-сервис (regex-module /scan)."""
    async with websockets.connect(url) as ws:
        await ws.send(text)
        raw = await asyncio.wait_for(ws.recv(), timeout=120.0)
    return json.loads(raw)


async def run_case(
    service: str,
    cfg: dict[str, Any],
    client: httpx.AsyncClient,
    text: str,
    expected: list[dict],
) -> dict:
    """Прогнать один текст через сервис и вернуть результат с метриками."""
    start = time.perf_counter()
    try:
        if cfg["protocol"] == "rest":
            resp = await call_rest(client, cfg["url"], text)
        else:
            resp = await call_websocket(cfg["url"], text)
        work_time = resp.get("work_time", round(time.perf_counter() - start, 3))
        entities = extract_entities(resp)
        error = None
    except Exception as exc:  # noqa: BLE001
        work_time = round(time.perf_counter() - start, 3)
        entities = []
        error = str(exc)

    found_types = {e["code"] for e in entities}
    expected_types = {pd["type"] for pd in expected}

    tp = len(expected_types & found_types)
    fp = len(found_types - expected_types)
    fn = len(expected_types - found_types)
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0

    # --- Проверка попадания в слайсы --------------------------------------
    # Для каждого ожидаемого значения ПД проверяем, что сервис вернул сущность
    # нужного типа, слайс которой покрывает фактическую позицию значения.
    slice_hits = 0
    slice_total = 0
    slice_details: list[dict] = []
    for pd in expected:
        sl = actual_slice(text, pd["value"])
        if sl is None:
            continue
        slice_total += 1
        hit = False
        for e in entities:
            if e["code"] != pd["type"]:
                continue
            es = e.get("slice")
            if not es:
                continue
            # Слайс сервиса покрывает фактическую позицию значения
            if es[0] <= sl[0] and es[1] >= sl[1]:
                hit = True
                break
        if hit:
            slice_hits += 1
        slice_details.append({
            "type": pd["type"],
            "value": pd["value"],
            "actual_slice": sl,
            "hit": hit,
        })

    slice_rate = slice_hits / slice_total if slice_total else 0.0

    return {
        "service": service,
        "text": text,
        "expected_types": sorted(expected_types),
        "found_types": sorted(found_types),
        "entities": entities,
        "work_time": work_time,
        "error": error,
        "tp": tp, "fp": fp, "fn": fn,
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "f1": round(f1, 3),
        "slice_hits": slice_hits,
        "slice_total": slice_total,
        "slice_rate": round(slice_rate, 3),
        "slice_details": slice_details,
    }


async def run_all() -> list[dict]:
    """Прогнать все тестовые запросы через все сервисы."""
    queries = load_test_data()
    results: list[dict] = []
    async with httpx.AsyncClient() as client:
        for service, cfg in SERVICES.items():
            for q in queries:
                results.append(await run_case(
                    service, cfg, client, q["text"], q["personal_data"],
                ))
    return results


def build_summary(results: list[dict]) -> dict[str, dict]:
    """Сводные метрики по каждому сервису."""
    summary: dict[str, dict] = {}
    for service in SERVICES:
        rows = [r for r in results if r["service"] == service]
        tp = sum(r["tp"] for r in rows)
        fp = sum(r["fp"] for r in rows)
        fn = sum(r["fn"] for r in rows)
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
        slice_hits = sum(r["slice_hits"] for r in rows)
        slice_total = sum(r["slice_total"] for r in rows)
        slice_rate = slice_hits / slice_total if slice_total else 0.0
        avg_time = sum(r["work_time"] for r in rows) / len(rows)
        errors = sum(1 for r in rows if r["error"])
        summary[service] = {
            "tp": tp, "fp": fp, "fn": fn,
            "precision": round(precision, 3),
            "recall": round(recall, 3),
            "f1": round(f1, 3),
            "slice_hits": slice_hits,
            "slice_total": slice_total,
            "slice_rate": round(slice_rate, 3),
            "avg_time": round(avg_time, 3),
            "errors": errors,
        }
    return summary


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _slices_html(r: dict) -> str:
    """Список найденных типов с их слайсами."""
    if not r["entities"]:
        return '<span class="small">—</span>'
    parts = []
    for e in r["entities"]:
        sl = e.get("slice")
        sl_str = f"[{sl[0]}:{sl[1]}]" if sl else ""
        parts.append(
            f'<span class="ent">{_esc(e["code"])} <span class="sl">{sl_str}</span></span>'
        )
    return "<br>".join(parts)


def _slice_details_html(r: dict) -> str:
    """Детализация попадания в слайсы по ожидаемым значениям."""
    if not r["slice_details"]:
        return '<span class="small">—</span>'
    parts = []
    for d in r["slice_details"]:
        cls = "hit" if d["hit"] else "miss"
        sl = d["actual_slice"]
        parts.append(
            f'<span class="slc {cls}">{_esc(d["type"])} '
            f'<span class="sl">[{sl[0]}:{sl[1]}]</span> '
            f'<span class="small">{_esc(d["value"])}</span></span>'
        )
    return "<br>".join(parts)


def _cell(r: dict) -> str:
    if r["error"]:
        return f'<td class="err" title="{_esc(r["error"])}">ERR</td>'
    f1 = r["f1"]
    cls = "good" if f1 >= 0.8 else ("mid" if f1 >= 0.5 else "bad")
    sr = r["slice_rate"]
    sr_cls = "good" if sr >= 0.8 else ("mid" if sr >= 0.5 else "bad")
    return (
        f'<td class="{cls}">F1={f1:.2f}<br>'
        f'<span class="small">P={r["precision"]:.2f} R={r["recall"]:.2f}</span><br>'
        f'<span class="small">{r["work_time"]:.2f}s</span><br>'
        f'<span class="slc {sr_cls}">слайсы {r["slice_hits"]}/{r["slice_total"]}</span><br>'
        f'{_slices_html(r)}<br>{_slice_details_html(r)}</td>'
    )


def write_html(path: Path, results: list[dict], summary: dict[str, dict]) -> None:
    """Сформировать HTML-отчёт."""
    queries = load_test_data()
    service_names = list(SERVICES.keys())

    rows_html = []
    for i, q in enumerate(queries):
        cells = ""
        for svc in service_names:
            r = next(x for x in results if x["service"] == svc and x["text"] == q["text"])
            cells += _cell(r)
        expected = sorted({pd["type"] for pd in q["personal_data"]})
        rows_html.append(
            f"<tr><td class='case'>{i + 1}</td>"
            f"<td class='text'>{_esc(q['text'])}</td>"
            f"<td class='exp'>{', '.join(expected) or '—'}</td>"
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
            f"<td>{s['slice_hits']}/{s['slice_total']} ({s['slice_rate']:.3f})</td>"
            f"<td>{s['avg_time']:.3f}s</td><td>{s['errors']}</td></tr>"
        )

    html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<title>Отчёт: сервисы распознавания ПД</title>
<style>
  body {{ font-family: -apple-system, Segoe UI, Roboto, sans-serif; margin: 24px; color: #222; }}
  h1 {{ font-size: 22px; }}
  h2 {{ font-size: 18px; margin-top: 32px; }}
  table {{ border-collapse: collapse; width: 100%; margin-top: 12px; }}
  th, td {{ border: 1px solid #ccc; padding: 8px 10px; text-align: center; font-size: 13px; }}
  th {{ background: #f0f0f0; }}
  td.text {{ text-align: left; max-width: 320px; }}
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
  .slc {{ display: inline-block; font-size: 11px; border-radius: 3px; padding: 1px 4px; margin: 1px 0; }}
  .slc.hit {{ background: #d4edda; }}
  .slc.miss {{ background: #f8d7da; }}
  .legend span {{ display: inline-block; padding: 2px 8px; margin-right: 8px; border-radius: 3px; }}
</style>
</head>
<body>
<h1>Отчёт: сравнение сервисов распознавания ПД</h1>
<p>Тестовые данные: {len(queries)} запросов из <code>deepseek_json_20260922_merged.json</code>
и длинный текст <code>big_text.txt</code>.
Метрики по типам ПД (precision/recall/F1) и попадание в слайсы (доля ожидаемых значений,
слайс которых покрыт сущностью нужного типа).</p>

<h2>Сводная таблица по сервисам</h2>
<table>
  <tr><th>Сервис</th><th>TP</th><th>FP</th><th>FN</th><th>Precision</th><th>Recall</th><th>F1</th><th>Слайсы</th><th>Ср. время</th><th>Ошибки</th></tr>
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
    <th>gliner_famous</th><th>llm_service</th><th>ml_for_all_types</th><th>regex_module</th>
  </tr>
  {''.join(rows_html)}
</table>

<p class="small">Сгенерировано {time.strftime('%Y-%m-%d %H:%M:%S')}</p>
</body>
</html>"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Тест сервисов распознавания ПД")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="Путь к HTML-отчёту")
    args = parser.parse_args()

    results = asyncio.run(run_all())
    summary = build_summary(results)
    write_html(args.out, results, summary)

    print(f"Отчёт сохранён: {args.out}")
    print("\n=== Сводка ===")
    for service, s in summary.items():
        print(
            f"{service:<20} P={s['precision']:.3f} R={s['recall']:.3f} F1={s['f1']:.3f} "
            f"слайсы={s['slice_hits']}/{s['slice_total']} ({s['slice_rate']:.3f}) "
            f"avg_time={s['avg_time']:.3f}s errors={s['errors']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())