"""Контекстозависимая классификация известности персоны.

Принимает текст, имя персоны и позицию упоминания (start, end), вырезает окно
контекста вокруг упоминания и прогоняет через обученный трансформер.

В отличие от fame.py (контекстно-независимый gazetteer), эта модель решает по
контексту: «поэт Пушкин Александр Сергеевич» -> известный, а «Пушкин Александр
Сергеевич» без контекста -> неизвестный.
"""

from functools import lru_cache
from pathlib import Path
import re

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

ROOT = Path(__file__).resolve().parent.parent
MODEL_DIR = ROOT / "models" / "context_fame_model"

# Запас контекста в СЛОВАХ с каждой стороны от упоминания персоны.
# Модель обучена на окнах ±12 токенов; при инференсе даём сопоставимое окно,
# чтобы модель видела профессию/титул и биографический контекст.
CONTEXT_WORDS = 8

_WORD_SPLIT = re.compile(r"(\s+)")


@lru_cache(maxsize=1)
def get_model(model_dir: Path = MODEL_DIR):
    if torch.cuda.is_available():
        device = torch.device("cuda")
    elif torch.backends.mps.is_available():
        device = torch.device("mps")
    else:
        device = torch.device("cpu")
    model = AutoModelForSequenceClassification.from_pretrained(str(model_dir))
    model.to(device)
    model.eval()
    tokenizer = AutoTokenizer.from_pretrained(str(model_dir))
    return model, tokenizer, device


def _context_window(text: str, start: int, end: int, words: int = CONTEXT_WORDS) -> str:
    """Вырезать окно контекста вокруг упоминания [start, end) по СЛОВАМ.

    Возвращает слайс: до `words` слов слева + само упоминание + до `words` слов
    справа. Режем по границам слов, а не символов, чтобы не разрывать токены.
    """
    # Найти индексы слов, в которых начинается и кончается упоминание.
    parts = _WORD_SPLIT.split(text)
    pos = 0
    start_word = 0
    end_word = 0
    for i, part in enumerate(parts):
        if pos + len(part) > start:
            start_word = i
            break
        pos += len(part)
    pos = 0
    end_word = 0
    for i, part in enumerate(parts):
        if pos + len(part) > end:
            end_word = i
            break
        pos += len(part)
    else:
        # Упоминание доходит до конца строки: правая часть пустая.
        end_word = len(parts) - 1

    # Собрать до `words` слов слева от упоминания.
    left: list[str] = []
    idx = start_word - 1
    while idx >= 0 and len(left) < words:
        if parts[idx].strip():
            left.insert(0, parts[idx])
        idx -= 1

    # Собрать до `words` слов справа от упоминания (начиная с конца упоминания).
    right: list[str] = []
    idx = end_word + 1
    while idx < len(parts) and len(right) < words:
        if parts[idx].strip():
            right.append(parts[idx])
        idx += 1

    return " ".join(left) + " " + text[start:end] + " " + " ".join(right)


def classify(text: str, name: str, start: int, end: int) -> str:
    """Вернуть 'famous' или 'unknown' для упоминания персоны по контексту."""
    model, tokenizer, device = get_model()
    ctx = _context_window(text, start, end).lower()  # регистр нормализован при обучении
    enc = tokenizer(ctx, truncation=True, padding="max_length", max_length=64, return_tensors="pt")
    enc = {k: v.to(device) for k, v in enc.items()}
    with torch.no_grad():
        logits = model(**enc).logits
    pred = logits.argmax(dim=-1).item()
    return "famous" if pred == 1 else "unknown"


def is_famous(text: str, name: str, start: int, end: int) -> bool:
    """Удобная обёртка: True, если персона известная (не маскируем)."""
    return classify(text, name, start, end) == "famous"