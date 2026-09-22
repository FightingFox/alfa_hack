"""Общий скрипт обучения модели-детектора одного типа ПД.

Используется каждым подкаталогом типа: генерирует синтетику, обучает
лёгковесную модель и сохраняет веса (model.npz + meta.json) в свой каталог.
"""

from __future__ import annotations

import sys
from pathlib import Path

import _common
import _synthetic

ROOT = Path(__file__).resolve().parent


def train(code: str, name: str, n: int = _synthetic.SAMPLES_PER_TYPE) -> dict:
    """Обучить и сохранить модель для типа ПД. Возвращает сводку."""
    data = _synthetic.generate(code, n)
    texts = [t for t, _ in data]
    labels = [l for _, l in data]

    detector = _common.PiiDetector(code, name)
    history = detector.fit(texts, labels)

    folder = ROOT / code
    detector.save(folder)

    # Быстрая оценка на той же выборке (для отчёта).
    preds = [detector.detect(t) for t in texts]
    acc = sum(1 for p, l in zip(preds, labels) if p == l) / len(labels)

    return {
        "code": code,
        "name": name,
        "samples": len(texts),
        "final_loss": round(history[-1], 4),
        "train_acc": round(acc, 4),
        "saved_to": str(folder),
    }


def main() -> None:
    code = sys.argv[1] if len(sys.argv) > 1 else None
    if code is None:
        print("Usage: python _train.py <CODE> [name]")
        sys.exit(1)
    name = sys.argv[2] if len(sys.argv) > 2 else code
    result = train(code, name)
    print(result)


if __name__ == "__main__":
    main()