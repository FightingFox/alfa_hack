import re
from functools import lru_cache
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
NAMES_FILE = DATA_DIR / "names.txt"

FIO_TYPES = {"FIO", "FAM_FIO"}

# Имена короче этой длины матчатся только как целое слово (без падежных форм),
# чтобы избежать ложных срабатываний на случайных префиксах (кот, ста, нас).
MIN_PREFIX_LEN = 4

# Частые короткие имена, для которых разрешён префиксный матчинг падежных форм
# (Иван -> Ивана, Ивану, Иваном; Анна -> Анны, Анне). Редкие короткие имена
# (абас, абел, ...) не включены, чтобы не плодить ложные срабатывания.
# Для этих имён допускаются префиксы на 1 букву короче (Анна -> Анн-ы).
COMMON_SHORT_NAMES = frozenset(
    {
        "иван",
        "петр",
        "олег",
        "анна",
        "инна",
        "алла",
        "вера",
        "нина",
        "юлия",
        "саша",
        "миша",
        "лена",
        "оля",
        "даша",
        "коля",
        "гриша",
        "ваня",
        "петя",
        "катя",
        "таня",
        "настя",
        "маша",
        "дима",
        "женя",
        "вася",
        "толя",
        "боря",
        "федя",
        "ольга",
        "мария",
        "наталья",
        "татьяна",
        "ирина",
        "елена",
        "надежда",
        "любовь",
        "светлана",
        "екатерина",
        "ксения",
        "дарья",
        "александра",
        "виктория",
        "полина",
        "валерия",
        "вероника",
        "софья",
        "софия",
        "ульяна",
        "арина",
        "кристина",
        "марина",
        "лариса",
        "диана",
        "карина",
        "эльвира",
        "гульнара",
        "алия",
        "лейла",
        "динара",
        "регина",
        "сергей",
        "андрей",
        "алексей",
        "александр",
        "дмитрий",
        "николай",
        "михаил",
        "владимир",
        "антон",
        "артем",
        "артём",
        "павел",
        "роман",
        "виктор",
        "юрий",
        "егор",
        "кирилл",
        "денис",
        "виталий",
        "вадим",
        "григорий",
        "степан",
        "федор",
        "фёдор",
        "тимофей",
        "георгий",
        "константин",
        "валерий",
        "борис",
        "геннадий",
        "леонид",
        "станислав",
        "вячеслав",
        "руслан",
        "тимур",
        "марат",
        "ильдар",
        "ринат",
        "айрат",
        "булат",
        "дамир",
    }
)

# Максимальная разница длин между словом и именем для падежной формы.
MAX_SUFFIX_LEN = 4

_WORD_RE = re.compile(r"[а-яё]+")


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


@lru_cache(maxsize=1)
def _name_prefixes() -> frozenset[str]:
    """Множество всех префиксов имён, допускающих падежные формы.

    Для обычных имён включаются префиксы длиной >= MIN_PREFIX_LEN. Для частых
    коротких имён (COMMON_SHORT_NAMES) — префиксы на 1 букву короче, чтобы
    ловить склонения с изменением основы (Анна -> Анн-ы, Ольга -> Ольг-и).
    """
    prefixes: set[str] = set()
    for name in load_names():
        if name in COMMON_SHORT_NAMES:
            start = max(3, len(name) - 1)
        else:
            start = MIN_PREFIX_LEN
        for i in range(start, len(name) + 1):
            prefixes.add(name[:i])
    return frozenset(prefixes)


def _contains_name(text: str) -> bool:
    """Проверяет, встречается ли в тексте имя из справочника (с учётом падежей).

    Имя считается найденным, если какое-либо слово в тексте начинается с него
    (ловит падежные формы: Иван, Ивана, Ивану, Иваном; Анна, Анны, Анне).
    Для редких коротких имён (не в COMMON_SHORT_NAMES) допускается только
    точное совпадение по слову.
    """
    names = load_names()
    if not names:
        return True
    prefixes = _name_prefixes()
    lowered = text.lower()
    for word in _WORD_RE.findall(lowered):
        if word in names:
            return True
        for i in range(3, len(word) + 1):
            prefix = word[:i]
            if prefix in prefixes and len(word) - len(prefix) <= MAX_SUFFIX_LEN:
                return True
    return False


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
