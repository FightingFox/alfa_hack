"""Обучить и сохранить модель-детектор типа ПД BIRTH_CERT."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from _train import train  # noqa: E402

CODE = "BIRTH_CERT"
NAME = "BIRTH_CERT"


def main() -> None:
    result = train(CODE, NAME)
    print(result)


if __name__ == "__main__":
    main()
