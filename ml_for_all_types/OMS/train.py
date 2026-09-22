"""Обучить и сохранить модель-детектор типа ПД OMS."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from _train import train  # noqa: E402

CODE = "OMS"
NAME = "OMS"


def main() -> None:
    result = train(CODE, NAME)
    print(result)


if __name__ == "__main__":
    main()
