"""Синтетика для типа ПД ISSUE_CODE (см. _synthetic.generate)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from _synthetic import generate, SAMPLES_PER_TYPE  # noqa: E402

CODE = "ISSUE_CODE"


def make(n: int = SAMPLES_PER_TYPE) -> list[tuple[str, int]]:
    """Сгенерировать (текст, метка) для типа ISSUE_CODE."""
    return generate(CODE, n)
