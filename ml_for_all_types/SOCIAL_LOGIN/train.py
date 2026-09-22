"""Обучить и сохранить модель-детектор типа ПД SOCIAL_LOGIN."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from _train import train  # noqa: E402

CODE = "SOCIAL_LOGIN"
NAME = "SOCIAL_LOGIN"


def main() -> None:
    result = train(CODE, NAME)
    print(result)


if __name__ == "__main__":
    main()
