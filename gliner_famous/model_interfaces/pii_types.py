"""Реестр типов ПД и маппинг на метки GLiNER.

Каждый тип ПД описывается:
- кодом (PASSPORT, INN, ...),
- русским названием и описанием,
- регулярным выражением и контекстными словами для regex-детекции,
- примером,
- признаком нейтрализатора (маскируется только при наличии в белом списке).

Часть типов детектируется моделью GLiNER (метки person, email, date, address,
bank card number, id number), остальные — регулярными выражениями. Маппинг
gliner_label связывает тип с меткой GLiNER, когда она есть.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from functools import lru_cache


class PiiKind(str, Enum):
    """Роль типа ПД при маскировании."""

    REGULAR = "regular"          # Обычный параметр — маскируется всегда.
    NEUTRALIZER = "neutralizer"  # Нейтрализатор — маскируется только в белом списке.


@dataclass(frozen=True)
class PiiType:
    """Описание одного типа ПД."""

    code: str
    name: str
    description: str
    kind: PiiKind
    gliner_label: str | None = None
    gliner_labels: tuple[str, ...] = ()
    pattern: str | None = None
    context: tuple[str, ...] = ()
    example: str | None = None

    @property
    def regex(self) -> re.Pattern | None:
        """Скомпилированное регулярное выражение (кэшируется через lru_cache)."""
        if self.pattern is None:
            return None
        return _compile(self.pattern)

    @property
    def labels(self) -> tuple[str, ...]:
        """Все метки GLiNER, соответствующие типу."""
        if self.gliner_labels:
            return self.gliner_labels
        return (self.gliner_label,) if self.gliner_label else ()


@lru_cache(maxsize=256)
def _compile(pattern: str) -> re.Pattern:
    return re.compile(pattern)


# --- Типы ПД ---------------------------------------------------------------

PII_TYPES: tuple[PiiType, ...] = (
    PiiType(
        code="PASSPORT",
        name="Серия и номер паспорта",
        description="Основной идентификатор гражданского паспорта РФ. Серия (4 цифры) и номер (6 цифр).",
        kind=PiiKind.REGULAR,
        gliner_label="id number",
        pattern=r"\d{4}[\s-]?\d{6}",
        context=("паспорт", "РФ"),
        example="4510 123456",
    ),
    PiiType(
        code="LICENSE",
        name="Серия и номер водительского удостоверения",
        description="Идентификатор водительских прав. Формат аналогичен паспорту.",
        kind=PiiKind.REGULAR,
        gliner_label="id number",
        pattern=r"\d{4}[\s-]?\d{6}",
        context=("водительск", "права", "удостоверение"),
        example="4510 123456",
    ),
    PiiType(
        code="CITIZENSHIP",
        name="Гражданство",
        description="Принадлежность лица к государству.",
        kind=PiiKind.REGULAR,
        gliner_labels=("citizenship", "nationality"),
        pattern=r"(?:гражданство|гражданин|гражданка)\s*[:—-]?\s*([А-ЯЁа-яё]+)",
        context=("гражданство",),
        example="гражданство: РФ",
    ),
    PiiType(
        code="ISSUING_AUTHORITY",
        name="Орган, выдавший паспорт",
        description="Наименование подразделения, оформившего документ.",
        kind=PiiKind.REGULAR,
        gliner_labels=("issuing authority", "authority"),
        pattern=r"(?:ОВД|УФМС|МВД)[\s\S]{0,60}?(?:выдан|выдано|выдавший)",
        context=("выдан", "ОВД", "УФМС", "МВД"),
        example="ОВД Ленинского района г. Москвы",
    ),
    PiiType(
        code="ISSUE_CODE",
        name="Код подразделения",
        description="Код подразделения МВД, выдавшего паспорт.",
        kind=PiiKind.REGULAR,
        gliner_labels=("issue code", "department code"),
        pattern=r"\d{3}[-.]?\d{3}",
        context=("подразд",),
        example="770-001",
    ),
    PiiType(
        code="DATE",
        name="Дата",
        description="Дата рождения, выдачи документа и т.п.",
        kind=PiiKind.REGULAR,
        gliner_label="date",
        example="15 марта 1985 года",
    ),
    PiiType(
        code="ADDRESS",
        name="Адрес (полный)",
        description="Почтовый адрес целиком: индекс, город, улица, дом, квартира.",
        kind=PiiKind.NEUTRALIZER,
        gliner_label="address",
        gliner_labels=("address", "location"),
        example="125167, г. Москва, ул. Правды, д. 24, кв. 5",
    ),
    PiiType(
        code="FIO",
        name="ФИО",
        description="Фамилия, имя, отчество (или фамилия и имя) физического лица.",
        kind=PiiKind.NEUTRALIZER,
        gliner_label="person",
        example="Иванов Иван Иванович",
    ),
    PiiType(
        code="FAM_FIO",
        name="ФИО известной персоны",
        description="ФИО публичной/известной личности — не маскируется (не является ПД).",
        kind=PiiKind.NEUTRALIZER,
        example="Александр Сергеевич Пушкин",
    ),
    PiiType(
        code="EMAIL",
        name="Email",
        description="Адрес электронной почты.",
        kind=PiiKind.REGULAR,
        gliner_label="email",
        pattern=r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
        example="ivan.petrov@mail.ru",
    ),
    PiiType(
        code="PHONE",
        name="Телефон",
        description="Номер телефона (мобильный, городской).",
        kind=PiiKind.REGULAR,
        gliner_label="phone number",
        pattern=r"\+?\d[\d\s().-]{6,}\d",
        example="+7 (903) 123-45-67",
    ),
    PiiType(
        code="INN",
        name="ИНН",
        description="Индивидуальный номер налогоплательщика (10 цифр юр., 12 физ.).",
        kind=PiiKind.REGULAR,
        gliner_label="id number",
        pattern=r"\d{10}|\d{12}",
        context=("ИНН", "инн"),
        example="770123456789",
    ),
    PiiType(
        code="CARD_NUMBER",
        name="Номер платёжной карты",
        description="PAN банковской карты.",
        kind=PiiKind.REGULAR,
        gliner_label="bank card number",
        pattern=r"\d{4}([ -]?\d{4}){3}",
        context=("карт", "банк"),
        example="4111 1111 1111 1111",
    ),
    PiiType(
        code="CVV",
        name="CVV-код",
        description="Секретный код верификации карты (CVC/CVV2).",
        kind=PiiKind.REGULAR,
        gliner_labels=("cvv", "cvc"),
        pattern=r"\d{3}",
        context=("CVV", "CVC", "cvv", "cvc"),
        example="123",
    ),
    PiiType(
        code="PIN",
        name="Пин-код карты",
        description="Секретный код доступа к карте.",
        kind=PiiKind.REGULAR,
        gliner_labels=("pin", "pin code"),
        pattern=r"\d{4}",
        context=("пин", "PIN", "pin"),
        example="1234",
    ),
    PiiType(
        code="CARDHOLDER",
        name="Имя держателя карты",
        description="Имя владельца, эмбоссированное на карте (латиница CAPS).",
        kind=PiiKind.REGULAR,
        gliner_labels=("cardholder", "card holder name"),
        pattern=r"\b[A-Z]{2,}(?:\s+[A-Z]{2,})+\b",
        context=("cardholder", "имя на карте", "держатель"),
        example="IVAN PETROV",
    ),
    PiiType(
        code="MILITARY_ID",
        name="Военный билет",
        description="Документ воинского учёта. Серия (2 буквы + 2 цифры) и номер (7–8 цифр).",
        kind=PiiKind.REGULAR,
        gliner_labels=("military id", "military document"),
        pattern=r"[А-ЯЁ]{2}\s?\d{2}\s?\d{7,8}",
        context=("военный билет", "ВБ", "военнообязанный"),
        example="АБ 12 1234567",
    ),
    PiiType(
        code="FOREIGN_PASSPORT",
        name="Заграничный паспорт",
        description="Документ, удостоверяющий личность за рубежом. Серия (2 цифры) и номер (7 цифр).",
        kind=PiiKind.REGULAR,
        gliner_labels=("foreign passport", "passport"),
        pattern=r"\d{2}\s?(?:No|№)?\s?\d{7}",
        context=("загранпаспорт", "заграничный"),
        example="75 №1234567",
    ),
    PiiType(
        code="SNILS",
        name="СНИЛС",
        description="Страховой номер индивидуального лицевого счёта (9 цифр + 2 контрольных).",
        kind=PiiKind.REGULAR,
        gliner_labels=("snils", "insurance number"),
        pattern=r"\d{3}-\d{3}-\d{3}\s?\d{2}",
        context=("СНИЛС", "снилс", "страховой номер"),
        example="112-233-445 95",
    ),
    PiiType(
        code="BIRTH_CERT",
        name="Свидетельство о рождении",
        description="Первичный документ о рождении. Серия — римские цифры + 2 буквы, номер — 6 цифр.",
        kind=PiiKind.REGULAR,
        gliner_labels=("birth certificate",),
        pattern=r"[IVXLCDM]+-[А-ЯЁ]{2}\s?(?:№|No)\s?\d{6}",
        context=("свидетельство о рождении",),
        example="I-МЮ №123456",
    ),
    PiiType(
        code="OMS",
        name="Полис ОМС",
        description="Обязательное медицинское страхование, единый номер полиса.",
        kind=PiiKind.REGULAR,
        gliner_labels=("oms", "insurance policy"),
        pattern=r"\d{16}",
        context=("ОМС", "омс", "полис"),
        example="5400000000000000",
    ),
    PiiType(
        code="DMC",
        name="Полис ДМС",
        description="Добровольное медицинское страхование.",
        kind=PiiKind.REGULAR,
        gliner_labels=("dmc",),
        pattern=r"\d{10}",
        context=("ДМС", "дмс", "полис"),
        example="0123456789",
    ),
    PiiType(
        code="MIGRATION_CARD",
        name="Номер миграционной карты",
        description="Учётный документ иностранного гражданина.",
        kind=PiiKind.REGULAR,
        gliner_labels=("migration card",),
        pattern=r"\d{10}",
        context=("миграционная карта",),
        example="0012345678",
    ),
    PiiType(
        code="SOCIAL_LOGIN",
        name="Логин в соцсети",
        description="Учётная запись/юзернейм в социальных сетях.",
        kind=PiiKind.REGULAR,
        gliner_labels=("social login", "username"),
        pattern=r"@[A-Za-z0-9_.]{3,}",
        context=("vk.com", "t.me", "@", "логин", "соцсет"),
        example="@petr_ivanov87",
    ),
    PiiType(
        code="IP_ADDRESS",
        name="IP-адрес",
        description="Сетевой адрес устройства (IPv4).",
        kind=PiiKind.REGULAR,
        gliner_labels=("ip address",),
        pattern=r"\b(?:(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\.){3}(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\b",
        example="192.168.1.105",
    ),
    PiiType(
        code="MAC_ADDRESS",
        name="MAC-адрес",
        description="Физический адрес сетевого интерфейса.",
        kind=PiiKind.REGULAR,
        gliner_labels=("mac address",),
        pattern=r"(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}",
        example="00:1A:2B:3C:4D:5E",
    ),
    PiiType(
        code="PASSWORD",
        name="Пароль",
        description="Секретная строка доступа.",
        kind=PiiKind.REGULAR,
        gliner_labels=("password", "secret"),
        context=("пароль", "password"),
        example="********",
    ),
    PiiType(
        code="PROFESSION",
        name="Профессия",
        description="Род занятий / профессия физического лица.",
        kind=PiiKind.REGULAR,
        gliner_labels=("profession", "job"),
        example="Сварщик",
    ),
    PiiType(
        code="COMPANY",
        name="Компания",
        description="Наименование организации/компании.",
        kind=PiiKind.NEUTRALIZER,
        gliner_labels=("organization",),
        example="Альфа-Банк",
    ),
)

# --- Индексы ---------------------------------------------------------------

_BY_CODE: dict[str, PiiType] = {t.code: t for t in PII_TYPES}
_BY_GLINER: dict[str, list[PiiType]] = {}
for _t in PII_TYPES:
    for _label in _t.labels:
        _BY_GLINER.setdefault(_label, []).append(_t)


def get_type(code: str) -> PiiType | None:
    """Вернуть тип ПД по коду (PASSPORT, INN, ...)."""
    return _BY_CODE.get(code)


def types_for_gliner(label: str) -> list[PiiType]:
    """Вернуть типы ПД, соответствующие метке GLiNER (person, email, ...)."""
    return _BY_GLINER.get(label, [])


def all_types() -> tuple[PiiType, ...]:
    """Все зарегистрированные типы ПД."""
    return PII_TYPES


def neutralizers() -> tuple[PiiType, ...]:
    """Типы-нейтрализаторы (маскируются только в белом списке)."""
    return tuple(t for t in PII_TYPES if t.kind is PiiKind.NEUTRALIZER)


def map_to_pii_types(entities: list[dict]) -> list[dict]:
    """Сопоставить сущности GLiNER с типами ПД из реестра.

    Каждая сущность получает поле `pii_codes` — список кодов типов ПД
    (PASSPORT, INN, ...), которым соответствует метка GLiNER. Сущности без
    соответствия (например, organization) остаются без pii_codes.
    """
    mapped: list[dict] = []
    for ent in entities:
        ent = dict(ent)
        types = types_for_gliner(ent["label"])
        ent["pii_codes"] = [t.code for t in types]
        mapped.append(ent)
    return mapped