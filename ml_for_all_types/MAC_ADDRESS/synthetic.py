"""Синтетика для типа ПД MAC_ADDRESS (см. _synthetic.generate)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from _synthetic import generate, SAMPLES_PER_TYPE  # noqa: E402

CODE = "MAC_ADDRESS"


def make(n: int = SAMPLES_PER_TYPE) -> list[tuple[str, int]]:
    """Сгенерировать (текст, метка) для типа MAC_ADDRESS."""
    return generate(CODE, n)
