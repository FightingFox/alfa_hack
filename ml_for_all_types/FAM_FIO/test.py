"""Протестировать модель-детектор типа ПД FAM_FIO."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from _test import evaluate  # noqa: E402

CODE = "FAM_FIO"


def main() -> None:
    print(evaluate(CODE))


if __name__ == "__main__":
    main()
