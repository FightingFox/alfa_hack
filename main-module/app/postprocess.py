from functools import lru_cache
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
NAMES_FILE = DATA_DIR / "names.txt"

FIO_TYPES = {"FIO", "FAM_FIO"}


@lru_cache(maxsize=1)
def load_names() -> frozenset[str]:
    """Загружает справочник имён из data/names.txt в нижнем регистре."""
    if not NAMES_FILE.exists():
        return frozenset()
    names: set[str] = set()
    for line in NAMES_FILE.read_text(encoding="utf-8").splitlines():
        name = line.strip()
        if name:
            names.add(name.lower())
    return frozenset(names)


def _contains_name(text: str) -> bool:
    """Проверяет, встречается ли в тексте хотя бы одно имя из справочника."""
    names = load_names()
    if not names:
        return True
    lowered = text.lower()
    return any(name in lowered for name in names)


def filter_fio_entities(entities: list[dict]) -> list[dict]:
    """Удаляет из нахождений сущности ФИО, не содержащие имён из справочника.

    Сущности других типов (не ФИО) возвращаются без изменений.
    """
    filtered: list[dict] = []
    for entity in entities:
        types = set(entity["type"])
        if types & FIO_TYPES and not _contains_name(entity["text"]):
            continue
        filtered.append(entity)
    return filtered
