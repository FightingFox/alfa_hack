"""Синтетика для типа ПД DATE (см. _synthetic.generate)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from _synthetic import generate, SAMPLES_PER_TYPE  # noqa: E402

CODE = "DATE"


def make(n: int = SAMPLES_PER_TYPE) -> list[tuple[str, int]]:
    """Сгенерировать (текст, метка) для типа DATE."""
    return generate(CODE, n)
