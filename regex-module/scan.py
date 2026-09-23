"""Модуль определения персональных данных (ПДн) с помощью регулярных выражений.

Использует только стандартную библиотеку Python (re).
"""

import re
import time
from typing import Any

from data_type import DataType
from models import Entity, ProcessResponse
from address_book import AddressBook

# Справочник адресов (КЛАДР). Загружается лениво при первом обращении.
_address_book: AddressBook | None = None


def _get_address_book() -> AddressBook:
    """Возвращает загруженный справочник адресов (с ленивой загрузкой)."""
    global _address_book
    if _address_book is None:
        _address_book = AddressBook()
    return _address_book


def preload_address_book() -> None:
    """Принудительно загружает справочник адресов (вызывается при старте сервиса)."""
    _get_address_book()

# Типы ПДн и соответствующие регулярные выражения.
# Порядок в словаре определяет порядок результатов в scan().
RULES: dict[DataType, re.Pattern[str]] = {
    # Паспорт: серия (4 цифры) + номер (6 цифр), с пробелом/дефисом или без.
    DataType.PASSPORT: re.compile(
        r"(?<!\d)"
        r"(?:\d{4}[\s-]?\d{6}|\d{2}\s\d{2}\s\d{6})"
        r"(?!\d)"
    ),
    # Водительское удостоверение: серия (4 цифры или 2 цифры + 2 буквы) + номер.
    DataType.LICENSE: re.compile(
        r"(?<!\d)"
        r"(?:\d{4}[\s-]?\d{6}|\d{2}\s[А-ЯЁ]{2}\s\d{6})"
        r"(?!\d)"
    ),
    # Гражданство: «РФ», известные страны или значение после слова «гражданство».
    DataType.CITIZENSHIP: re.compile(
        r"(?:РФ|Российской Федерации|Казахстан|(?:[Гг]ражданство|[Гг]ражданин|[Гг]ражданка)\s*[:—-]?\s*([А-ЯЁ]{2,}|[А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ][а-яё]+)?))"
    ),
    # Орган, выдавший паспорт: ОВД|УФМС|МВД + название.
    DataType.ISSUING_AUTHORITY: re.compile(
        r"(?:ОВД|УФМС|МВД|ГУВД|УВД)"
        r"(?:\s+[А-ЯЁа-яё0-9№.\-]+){0,4}"
        r"(?!\.)"
    ),
    # Код подразделения: \d{3}[-.]?\d{3} (по формату).
    DataType.ISSUE_CODE: re.compile(
        r"(?<!\d)(?<!\d\.)\d{3}[-.]?\d{3}(?!\d)(?!\.\d{1,3}\.)"
    ),
    # Дата: DD.MM.YYYY, DD/MM/YYYY, YYYY-MM-DD, DD-MM-YYYY, DD.MM.YY.
    DataType.DATE: re.compile(
        r"(?<!\d)"
        r"(?:"
        r"\d{2}[./\-]\d{2}[./\-]\d{2,4}"
        r"|"
        r"\d{4}[\-]\d{2}[\-]\d{2}"
        r")"
        r"(?!\d)"
    ),
    # ФИО: кириллические слова с заглавной буквы (Фамилия Имя Отчество).
    DataType.FIO: re.compile(
        r"(?<![А-ЯЁа-яё])"
        r"(?:"
        r"[А-ЯЁ][а-яё]+[\s\-]+[А-ЯЁ][а-яё]+(?:-[А-ЯЁ][а-яё]+)?"
        r"(?:[\s\-]+[А-ЯЁ][а-яё]+(?:-[А-ЯЁ][а-яё]+)?)?"
        r"|"
        r"[А-ЯЁ][а-яё]+[\s\-]+[А-ЯЁ]\.[А-ЯЁ]\."
        r")"
        r"(?![а-яё])"
    ),
    # Email: local@domain.tld
    DataType.EMAIL: re.compile(
        r"(?<![\w\\])"
        r"[A-Za-z0-9][A-Za-z0-9._%+\-]*"
        r"@"
        r"[A-Za-z0-9.\-]+"
        r"\.[A-Za-z]{1,}"
        r"(?!\w)"
    ),
    # ИНН: 10 (юр.) или 12 (физ.) цифр.
    DataType.INN: re.compile(
        r"(?<!\d)\d{10}(?!\d)|(?<!\d)\d{12}(?!\d)"
    ),
    # Номер платёжной карты: PAN, 16 цифр, сгруппированы по 4.
    DataType.CARD_NUMBER: re.compile(
        r"(?<!\d)(?:\d{4}[ -]?){3}\d{4}(?!\d)"
    ),
    # CVV-код: \d{3} рядом с «CVV|CVC».
    DataType.CVV: re.compile(
        r"(?:CVV|CVC|cvv|cvc)\s*(?:[:=—-]|<<)?\s*(?<!\d)(\d{3})(?!\d)"
    ),
    # Пин-код: \d{4} рядом с «пин|PIN|ПИН-код».
    DataType.PIN: re.compile(
        r"(?:пин|PIN|pin|ПИН|ПИН-код|Пин-код)\s*(?:[:=—-]|<<)?\s*(?<!\d)(\d{4})(?!\d)"
    ),
    # Имя держателя карты: латиница CAPS (2+ слова).
    DataType.CARDHOLDER: re.compile(
        r"(?<![A-Z])[A-Z]{2,}(?:\s+[A-Z]{2,})+(?![A-Z])"
    ),
    # Военный билет: серия (2 буквы + 2 цифры) и номер (7-8 цифр).
    DataType.MILITARY_ID: re.compile(
        r"(?<![А-ЯЁа-яё])[А-ЯЁ]{2}\s?\d{2}\s?\d{7,8}(?!\d)"
    ),
    # Заграничный паспорт: серия (2 цифры) и номер (7 цифр).
    DataType.FOREIGN_PASSPORT: re.compile(
        r"(?<!\d)\d{2}\s?(?:No|№)?\s?\d{7}(?!\d)"
    ),
    # СНИЛС: 9 цифр + 2 контрольных, с разделителями или без.
    DataType.SNILS: re.compile(
        r"(?<!\d)\d{3}[\s-]?\d{3}[\s-]?\d{3}\s?\d{2}(?!\d)"
    ),
    # Свидетельство о рождении: серия (римские + 2 буквы) и номер (6 цифр).
    DataType.BIRTH_CERT: re.compile(
        r"(?<![А-ЯЁа-яё])[IVXLCDM]+-[А-ЯЁ]{2}\s?(?:№|No)?\s?\d{6}(?!\d)"
    ),
    # Полис ОМС: единый номер, 16 цифр.
    DataType.OMS: re.compile(
        r"(?<!\d)\d{16}(?!\d)"
    ),
    # Полис ДМС: 10 цифр.
    DataType.DMC: re.compile(
        r"(?<!\d)\d{10}(?!\d)"
    ),
    # Номер миграционной карты: 10 цифр.
    DataType.MIGRATION_CARD: re.compile(
        r"(?<!\d)\d{10}(?!\d)"
    ),
    # Логин в соцсети: @username (не внутри email).
    DataType.SOCIAL_LOGIN: re.compile(
        r"(?<![A-Za-z0-9._%+\-])@[A-Za-z0-9_]{3,}(?![A-Za-z0-9_])(?!\.[A-Za-z]{2,})"
    ),
    # IP-адрес: IPv4 или IPv6.
    DataType.IP_ADDRESS: re.compile(
        r"(?:\b(?:(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\.){3}"
        r"(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\b)"
        r"|"
        r"(?:\b(?:[0-9A-Fa-f]{1,4}:){7}[0-9A-Fa-f]{1,4}\b)"
    ),
    # MAC-адрес: физический адрес сетевого интерфейса.
    DataType.MAC_ADDRESS: re.compile(
        r"(?<![0-9A-Fa-f])(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}(?![0-9A-Fa-f])"
    ),
    # Пароль: только контекст «пароль», «password», «pwd».
    DataType.PASSWORD: re.compile(
        r"(?:[Пп]ароль|password|pwd)\s*(?:[:=—-]|<<)?\s*(\S+?)(?=[\s,;:&>.]|$)"
    ),
    # Номер телефона: международный формат E.164 или российский.
    DataType.PHONE: re.compile(
        r"(?<!\d)"
        r"(?=(?:\D*\d){10,11}(?:\D|$))"
        r"(?:"
        r"(?:\+[1-9]\d{0,2}|8)[\s.-]?(?:\(\d{1,5}\)|\d{1,5})?(?<!\s)[\s.-]?\d{1,7}(?:[\s.-]?\d{1,7}){1,3}"
        r"|"
        r"(?=(?:\d[\s.-]?){9}\d(?![\s.-]?\d))\d{1,7}(?:[\s.-]?\d{1,7}){1,3}"
        r")"
    ),
}

# Слабые правила: совпадения без контекста, score 0.5.
WEAK_RULES: dict[DataType, re.Pattern[str]] = {
    # CVV без контекста: 3 цифры, изолированные от других чисел.
    DataType.CVV: re.compile(
        r"(?<!\d)(?<!\d[\s.-])(?<!\(\d)\d{3}(?!\d)(?![\s.-]\d)(?!\))"
    ),
    # PIN без контекста: 4 цифры, изолированные от других чисел.
    DataType.PIN: re.compile(
        r"(?<!\d)(?<!\d[\s.-])(?<!\(\d)\d{4}(?!\d)(?![\s.-]\d)(?!\))"
    ),
    # Пароль без контекста: строка с латиницей, цифрами и спецсимволами.
    DataType.PASSWORD: re.compile(
        r"(?<![A-Za-z0-9])[A-Za-z0-9!@#$%^&*()_+\-\[\]{};':\"\\|.<>\/?~`]{8,}(?![A-Za-z0-9])"
    ),
}


def _is_valid_date(value: str) -> bool:
    """Проверяет корректность даты."""
    import datetime

    for fmt in ("%d.%m.%Y", "%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d.%m.%y"):
        try:
            datetime.datetime.strptime(value, fmt)
            return True
        except ValueError:
            continue
    return False


def _is_valid_card(value: str) -> bool:
    """Проверяет контрольную сумму номера карты (алгоритм Луна)."""
    digits = [int(c) for c in value if c.isdigit()]
    if len(digits) < 13 or len(digits) > 19:
        return False
    total = 0
    for i, d in enumerate(reversed(digits)):
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def _is_valid_inn(value: str) -> bool:
    """Проверяет контрольную сумму ИНН (10 или 12 цифр)."""
    if len(value) == 10:
        weights = [2, 4, 10, 3, 5, 9, 4, 6, 8]
        check = sum(int(value[i]) * weights[i] for i in range(9)) % 11 % 10
        return check == int(value[9])
    if len(value) == 12:
        weights1 = [7, 2, 4, 10, 3, 5, 9, 4, 6, 8]
        weights2 = [3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8]
        check1 = sum(int(value[i]) * weights1[i] for i in range(10)) % 11 % 10
        check2 = sum(int(value[i]) * weights2[i] for i in range(11)) % 11 % 10
        return check1 == int(value[10]) and check2 == int(value[11])
    return False


def _is_strong_password(value: str) -> bool:
    """Проверяет, что строка похожа на пароль.

    Латиница, минимум 1 заглавная и 1 строчная буква, число, спецсимвол,
    длина не менее 8 символов.
    """
    if len(value) < 8:
        return False
    has_upper = any(c.isupper() and c.isascii() for c in value)
    has_lower = any(c.islower() and c.isascii() for c in value)
    has_digit = any(c.isdigit() for c in value)
    has_special = any(not c.isalnum() for c in value)
    return has_upper and has_lower and has_digit and has_special


def scan(text: str) -> list[dict[str, Any]]:
    """Находит персональные данные в тексте.

    Возвращает список словарей вида:
        {"text": str, "type": DataType, "score": float, "slice": (start, end)}

    Возвращаются все совпадения, включая пересекающиеся.
    Результаты отсортированы по slice: по возрастанию start, затем end.
    """
    results: list[dict[str, Any]] = []

    def _add(pii_type, pattern, score):
        for match in pattern.finditer(text):
            if match.lastindex:
                value = match.group(match.lastindex)
                start, end = match.span(match.lastindex)
            else:
                value = match.group(0)
                start, end = match.span(0)

            if pii_type == DataType.DATE and not _is_valid_date(value):
                continue
            if pii_type == DataType.INN and not _is_valid_inn(value):
                continue
            if pii_type == DataType.CARD_NUMBER and not _is_valid_card(value):
                continue
            if pii_type == DataType.PASSWORD and score < 1.0 and not _is_strong_password(value):
                continue

            if pii_type == DataType.ISSUING_AUTHORITY:
                value = value.rstrip(".,;:!?")
                end = start + len(value)

            results.append(
                {
                    "text": value,
                    "type": pii_type,
                    "score": score,
                    "slice": (start, end),
                }
            )

    for pii_type, pattern in RULES.items():
        _add(pii_type, pattern, 1.0)

    # Адрес ищется по справочнику КЛАДР (город, улица, дом).
    for address in _get_address_book().find_addresses(text):
        start = text.find(address)
        results.append(
            {
                "text": address,
                "type": DataType.ADDRESS,
                "score": 1.0,
                "slice": (start, start + len(address)),
            }
        )

    # Слабые правила (score 0.5), пропускаем пересечения с сильными того же типа.
    strong_spans: dict[DataType, list[tuple[int, int]]] = {}
    for r in results:
        strong_spans.setdefault(r["type"], []).append(r["slice"])

    for pii_type, pattern in WEAK_RULES.items():
        for match in pattern.finditer(text):
            if match.lastindex:
                value = match.group(match.lastindex)
                start, end = match.span(match.lastindex)
            else:
                value = match.group(0)
                start, end = match.span(0)

            if pii_type == DataType.PASSWORD and not _is_strong_password(value):
                continue

            # Пропускаем, если пересекается с сильным совпадением того же типа.
            if any(
                start < s_end and end > s_start
                for s_start, s_end in strong_spans.get(pii_type, [])
            ):
                continue

            results.append(
                {
                    "text": value,
                    "type": pii_type,
                    "score": 0.5,
                    "slice": (start, end),
                }
            )

    results.sort(key=lambda r: (r["slice"][0], r["slice"][1]))
    return results


def process_text(text: str) -> ProcessResponse:
    """Прогнать текст через regex-правила и вернуть сущности в формате gliner_famous."""
    start = time.perf_counter()
    detected = scan(text)
    elapsed = time.perf_counter() - start
    entities = [
        Entity(
            text=d["text"],
            type=[d["type"].name],
            score=round(d["score"], 3),
            slice=[d["slice"][0], d["slice"][1]],
            will_be_used=True,
        )
        for d in detected
    ]
    return ProcessResponse(
        work_time=round(elapsed, 3),
        length=len(text),
        count=len(entities),
        data=entities,
    )