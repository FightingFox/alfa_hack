"""Ансамбль лёгковесных ML-моделей-детекторов ПД.

Единая точка входа: загружает все обученные модели (по одной на каждый тип ПД
из реестра PII_TYPES) и прогоняет их ансамблем по тексту. Каждая модель —
независимый бинарный классификатор, обученный на своей синтетике.

Интерфейс:
    detect(text) -> list[dict]          # все найденные типы с вероятностями
    detect_types(text) -> list[str]     # только коды найденных типов
    score(text, code) -> float          # вероятность конкретного типа
    load_all() / reload()               # (пере)загрузка ансамбля
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

import _common

ROOT = Path(__file__).resolve().parent

# Порог по умолчанию для ансамбля (можно переопределить при вызове).
DEFAULT_THRESHOLD = 0.5


def _type_names() -> dict[str, str]:
    """Код -> человекочитаемое имя типа ПД (из реестра, если доступен)."""
    try:
        import sys
        sys.path.insert(0, str(ROOT.parent / "gliner_famous" / "model_interfaces"))
        from pii_types import PII_TYPES
        return {t.code: t.name for t in PII_TYPES}
    except Exception:
        return {}


def _discover_folders() -> list[Path]:
    """Все подкаталоги с обученными моделями (содержат model.npz)."""
    folders = []
    for p in sorted(ROOT.iterdir()):
        if p.is_dir() and (p / "model.npz").exists():
            folders.append(p)
    return folders


@lru_cache(maxsize=1)
def load_all() -> dict[str, _common.PiiDetector]:
    """Загрузить все обученные модели. Кэшируется; вызовите reload() для сброса."""
    detectors: dict[str, _common.PiiDetector] = {}
    for folder in _discover_folders():
        det = _common.PiiDetector.load(folder)
        detectors[det.code] = det
    return detectors


def reload() -> dict[str, _common.PiiDetector]:
    """Принудительно перезагрузить ансамбль (после переобучения моделей)."""
    load_all.cache_clear()
    return load_all()


def available_types() -> list[str]:
    """Коды типов, для которых есть обученная модель."""
    return sorted(load_all().keys())


def score(text: str, code: str) -> float:
    """Вероятность того, что текст содержит тип ПД `code`."""
    det = load_all().get(code)
    if det is None:
        raise KeyError(f"Нет модели для типа {code}")
    return det.score(text)


def detect(text: str, threshold: float = DEFAULT_THRESHOLD) -> list[dict]:
    """Прогнать текст через ансамбль.

    Возвращает список словарей для типов, чья вероятность >= threshold:
        {"code", "name", "score"}
    Отсортировано по убыванию вероятности.
    """
    names = _type_names()
    results = []
    for code, det in load_all().items():
        s = det.score(text)
        if s >= threshold:
            results.append({
                "code": code,
                "name": names.get(code, det.name),
                "score": round(s, 4),
            })
    results.sort(key=lambda r: r["score"], reverse=True)
    return results


def detect_types(text: str, threshold: float = DEFAULT_THRESHOLD) -> list[str]:
    """Коды типов ПД, найденных в тексте (без вероятностей)."""
    return [r["code"] for r in detect(text, threshold)]


def detect_with_scores(text: str) -> list[dict]:
    """Все типы с вероятностями (без порога), отсортированы по убыванию."""
    names = _type_names()
    results = []
    for code, det in load_all().items():
        results.append({
            "code": code,
            "name": names.get(code, det.name),
            "score": round(det.score(text), 4),
        })
    results.sort(key=lambda r: r["score"], reverse=True)
    return results


# --- Детекция по окнам (для длинных текстов) ------------------------------

# Размер окна в символах: достаточно, чтобы захватить сущность целиком,
# но не настолько, чтобы размыть сигнал. Перекрытие — чтобы сущность на
# границе окна не терялась.
WINDOW_SIZE = 60
WINDOW_STEP = 30


def _windows(text: str, size: int = WINDOW_SIZE, step: int = WINDOW_STEP) -> list[str]:
    """Разбить текст на перекрывающиеся окна по символам."""
    if len(text) <= size:
        return [text]
    return [text[i:i + size] for i in range(0, len(text) - size + 1, step)]


def detect_spans(text: str, threshold: float = DEFAULT_THRESHOLD) -> list[dict]:
    """Детекция по перекрывающимся окнам текста.

    Для длинных текстов целотекстовая классификация размывает сигнал
    (сущность — малая доля текста). Здесь текст режется на окна, каждое окно
    прогоняется через ансамбль, и для каждого типа берётся максимальная
    вероятность по всем окнам. Тип считается найденным, если максимум
    >= threshold.
    """
    names = _type_names()
    best: dict[str, float] = {}
    for win in _windows(text):
        for code, det in load_all().items():
            s = det.score(win)
            if s > best.get(code, 0.0):
                best[code] = s
    results = [
        {"code": code, "name": names.get(code, load_all()[code].name), "score": round(s, 4)}
        for code, s in best.items() if s >= threshold
    ]
    results.sort(key=lambda r: r["score"], reverse=True)
    return results


def detect_types_spans(text: str, threshold: float = DEFAULT_THRESHOLD) -> list[str]:
    """Коды типов ПД, найденных в тексте (по окнам)."""
    return [r["code"] for r in detect_spans(text, threshold)]


# Размер окна для повторного поиска (шаг 2): меньше основного, чтобы сузить
# фрагмент вокруг найденной сущности и уточнить её позицию.
RESEARCH_WINDOW_SIZE = 24
RESEARCH_WINDOW_STEP = 8


def _research_window(
    text: str,
    start: int,
    end: int,
    code: str,
    threshold: float,
) -> tuple[float, int, int, str]:
    """Повторный поиск по найденному куску (шаг 2).

    Внутри окна [start, end), где тип `code` уже найден на шаге 1, режем текст
    на более мелкие перекрывающиеся подокна и прогоняем модель ещё раз. Берём
    самое узкое подокно, чья вероятность >= threshold, — это уточняет позицию
    сущности перед определением финального слайса.

    Возвращает (score, start, end, chunk) для лучшего подокна.
    """
    det = load_all()[code]
    chunk = text[start:end]
    best: tuple[float, int, int, str] = (0.0, start, end, chunk)
    for sub in _windows(chunk, RESEARCH_WINDOW_SIZE, RESEARCH_WINDOW_STEP):
        s = det.score(sub)
        if s >= threshold and s > best[0]:
            sub_start = start + chunk.find(sub)
            best = (s, sub_start, sub_start + len(sub), sub)
    return best


def detect_spans_with_positions(text: str, threshold: float = DEFAULT_THRESHOLD) -> list[dict]:
    """Трёхшаговая детекция по окнам с позициями найденных фрагментов.

    Шаг 1 — обычный поиск: текст режется на перекрывающиеся окна, каждое окно
    прогоняется через ансамбль, для каждого типа берётся окно с максимальной
    вероятностью (как detect_spans).

    Шаг 2 — повторный поиск по найденному куску: внутри найденного окна текст
    режется на более мелкие подокна и модель прогоняется ещё раз, чтобы сузить
    фрагмент вокруг сущности и уточнить её позицию.

    Шаг 3 — определение слайсов для конечного результата: для уточнённого
    фрагмента ищем точное совпадение по regex (если есть) и возвращаем его
    позицию; иначе возвращаем фрагмент целиком.
    """
    names = _type_names()
    regexes = _type_regexes()
    best: dict[str, tuple[float, int, int, str]] = {}
    for win in _windows(text):
        start = text.find(win)
        if start < 0:
            start = 0
        end = start + len(win)
        for code, det in load_all().items():
            s = det.score(win)
            if s > best.get(code, (0.0, 0, 0, ""))[0]:
                best[code] = (s, start, end, win)
    results = []
    for code, (s, start, end, win) in best.items():
        if s < threshold:
            continue
        # Шаг 2: повторный поиск по найденному куску — уточняем позицию.
        s, rs_start, rs_end, _ = _research_window(text, start, end, code, threshold)
        # Шаг 3: определение слайса для конечного результата. Ищем regex по
        # исходному окну (гарантированно содержит сущность целиком), но
        # предпочитаем совпадение, ближайшее к уточнённому фрагменту шага 2.
        rs, re, rtext = _locate_span(text, start, end, rs_start, rs_end, regexes.get(code))
        results.append({
            "code": code,
            "name": names.get(code, load_all()[code].name),
            "score": round(s, 4),
            "slice": [rs, re],
            "text": rtext,
        })
    results.sort(key=lambda r: r["score"], reverse=True)
    return results


def _type_regexes() -> dict[str, "re.Pattern"]:
    """Код типа -> скомпилированный regex для уточнения слайса.

    Сначала пробуем взять из реестра pii_types (если доступен), иначе используем
    встроенные паттерны — чтобы контейнер был самодостаточным.
    """
    try:
        import sys
        sys.path.insert(0, str(ROOT.parent / "gliner_famous" / "model_interfaces"))
        from pii_types import PII_TYPES
        regexes = {t.code: t.regex for t in PII_TYPES if t.regex is not None}
        if regexes:
            return regexes
    except Exception:
        pass
    return {code: re.compile(pat) for code, pat in _BUILTIN_REGEXES.items()}


# Встроенные regex-паттерны для уточнения слайсов (самодостаточность контейнера).
_BUILTIN_REGEXES: dict[str, str] = {
    "PASSPORT": r"\d{4}[\s-]?\d{6}",
    "LICENSE": r"\d{4}[\s-]?\d{6}",
    "CITIZENSHIP": r"(?:гражданство|гражданин|гражданка)\s*[:—-]?\s*([А-ЯЁа-яё]+)",
    "ISSUING_AUTHORITY": r"(?:ОВД|УФМС|МВД)[\s\S]{0,60}?(?:выдан|выдано|выдавший)",
    "ISSUE_CODE": r"\d{3}[-.]?\d{3}",
    "EMAIL": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
    "PHONE": r"\+?\d[\d\s().-]{6,}\d",
    "INN": r"\d{12}|\d{10}",
    "CARD_NUMBER": r"\d{4}([ -]?\d{4}){3}",
    "CVV": r"\d{3}",
    "PIN": r"\d{4}",
    "CARDHOLDER": r"\b[A-Z]{2,}(?:\s+[A-Z]{2,})+\b",
    "MILITARY_ID": r"[А-ЯЁ]{2}\s?\d{2}\s?\d{7,8}",
    "FOREIGN_PASSPORT": r"\d{2}\s?(?:No|№)?\s?\d{7}",
    "SNILS": r"\d{3}-\d{3}-\d{3}\s?\d{2}",
    "BIRTH_CERT": r"[IVXLCDM]+-[А-ЯЁ]{2}\s?(?:№|No)\s?\d{6}",
    "OMS": r"\d{16}",
    "DMC": r"\d{10}",
    "MIGRATION_CARD": r"\d{10}",
    "SOCIAL_LOGIN": r"@[A-Za-z0-9_.]{3,}",
    "IP_ADDRESS": r"\b(?:(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\.){3}(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\b",
    "MAC_ADDRESS": r"(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}",
}


def _locate_span(
    text: str,
    start: int,
    end: int,
    ref_start: int,
    ref_end: int,
    pattern,
) -> tuple[int, int, str]:
    """Найти точную позицию сущности по regex внутри окна [start, end).

    Ищем совпадение regex по исходному окну (модель уже подтвердила, что тип
    присутствует). Предпочитаем совпадение, ближайшее к уточнённому фрагменту
    [ref_start, ref_end) из шага 2, а среди равноудалённых — самое длинное
    (например, ИНН из 12 цифр вместо 10). Если regex нет или совпадение не
    найдено — возвращаем уточнённый фрагмент [ref_start, ref_end) целиком.
    """
    if pattern is not None:
        chunk = text[start:end]
        ref_center = (ref_start + ref_end) / 2.0
        best = None
        best_dist = None
        for m in pattern.finditer(chunk):
            m_start = start + m.start()
            m_end = start + m.end()
            center = (m_start + m_end) / 2.0
            dist = abs(center - ref_center)
            if best is None or dist < best_dist or (
                dist == best_dist and (m_end - m_start) > (best[1] - best[0])
            ):
                best = (m_start, m_end)
                best_dist = dist
        if best is not None:
            rs, re = best
            return rs, re, text[rs:re]
    return ref_start, ref_end, text[ref_start:ref_end]