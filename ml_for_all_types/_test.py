"""Общий тест модели-детектора одного типа ПД.

Генерирует свежую синтетику (не ту, что использовалась при обучении), прогоняет
модель и считает точность/полноту/F1. Используется каждым подкаталогом типа.
"""

from __future__ import annotations

import sys
from pathlib import Path

import _common
import _synthetic

ROOT = Path(__file__).resolve().parent


def evaluate(code: str, n: int = 200) -> dict:
    """Оценить сохранённую модель типа ПД на свежей синтетике."""
    folder = ROOT / code
    detector = _common.PiiDetector.load(folder)

    data = _synthetic.generate(code, n)
    texts = [t for t, _ in data]
    labels = [l for _, l in data]

    tp = fp = tn = fn = 0
    for t, l in zip(texts, labels):
        p = detector.detect(t)
        if p and l:
            tp += 1
        elif p and not l:
            fp += 1
        elif not p and not l:
            tn += 1
        else:
            fn += 1

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    acc = (tp + tn) / len(texts)

    return {
        "code": code,
        "name": detector.name,
        "tp": tp, "fp": fp, "tn": tn, "fn": fn,
        "accuracy": round(acc, 4),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
    }


def main() -> None:
    code = sys.argv[1] if len(sys.argv) > 1 else None
    if code is None:
        print("Usage: python _test.py <CODE>")
        sys.exit(1)
    print(evaluate(code))


if __name__ == "__main__":
    main()