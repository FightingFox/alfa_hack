"""Обучить и сохранить модель-детектор типа ПД ISSUING_AUTHORITY."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from _train import train  # noqa: E402

CODE = "ISSUING_AUTHORITY"
NAME = "ISSUING_AUTHORITY"


def main() -> None:
    result = train(CODE, NAME)
    print(result)


if __name__ == "__main__":
    main()
