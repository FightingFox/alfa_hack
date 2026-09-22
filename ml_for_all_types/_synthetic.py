"""Генераторы синтетических данных для каждого типа ПД.

Для каждого типа возвращается список (текст, метка): 1 — текст содержит этот
тип ПД, 0 — не содержит. Негативные примеры включают тексты с другими типами
ПД и случайный «чистый» текст, чтобы модель училась различать именно свой тип.

Тексты генерируются разной длины и формата: короткие шаблоны и длинные списки
полей через запятую (как в реальных анкетах), чтобы модели обобщались на
реальные тексты. Все генераторы детерминированы (фиксированный seed).
"""

from __future__ import annotations

import random

random.seed(42)

# --- Вспомогательные генераторы -------------------------------------------

_FIRST = ["Иван", "Пётр", "Анна", "Мария", "Сергей", "Ольга", "Дмитрий", "Елена", "Алексей", "Наталья"]
_LAST = ["Иванов", "Петров", "Сидоров", "Смирнов", "Кузнецов", "Попов", "Соколов", "Лебедев", "Козлов", "Новиков"]
_MID = ["Иванович", "Петрович", "Сергеевич", "Андреевич", "Николаевич", "Александровна", "Дмитриевна", "Олеговна"]
_CITIES = ["Москва", "Санкт-Петербург", "Новосибирск", "Екатеринбург", "Казань", "Нижний Новгород", "Самара", "Омск"]
_STREETS = ["Ленина", "Пушкина", "Гагарина", "Советская", "Мира", "Центральная", "Победы", "Лесная"]
_ORGS = ["Альфа-Банк", "Газпром", "Сбербанк", "Яндекс", "РЖД", "Лукойл", "МТС", "Ростелеком"]
_PROF = ["сварщик", "инженер", "врач", "учитель", "программист", "бухгалтер", "юрист", "менеджер"]
_COUNTRIES = ["РФ", "Россия", "Казахстан", "Беларусь", "Украина", "Германия", "Китай", "США"]
_DOMAINS = ["mail.ru", "gmail.com", "yandex.ru", "bk.ru", "inbox.ru", "list.ru", "rambler.ru"]
_SOCIAL = ["vk.com", "t.me", "instagram.com", "ok.ru", "facebook.com", "twitter.com"]
_MONTHS = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря"]


def _fio() -> str:
    return f"{random.choice(_LAST)} {random.choice(_FIRST)} {random.choice(_MID)}"


def _fio_short() -> str:
    return f"{random.choice(_LAST)} {random.choice(_FIRST)}"


def _phone() -> str:
    return f"+7 ({random.randint(900, 999)}) {random.randint(100, 999)}-{random.randint(10, 99)}-{random.randint(10, 99)}"


def _email() -> str:
    return f"{random.choice(_LAST).lower()}.{random.choice(_FIRST).lower()}{random.randint(1, 99)}@{random.choice(_DOMAINS)}"


def _date() -> str:
    return f"{random.randint(1, 28)} {random.choice(_MONTHS)} {random.randint(1950, 2005)} года"


def _address() -> str:
    return (f"{random.randint(100000, 999999)}, г. {random.choice(_CITIES)}, "
            f"ул. {random.choice(_STREETS)}, д. {random.randint(1, 200)}, кв. {random.randint(1, 500)}")


def _card() -> str:
    return f"{random.randint(4000, 4999)} {random.randint(1000, 9999)} {random.randint(1000, 9999)} {random.randint(1000, 9999)}"


def _passport() -> str:
    return f"{random.randint(1000, 9999)} {random.randint(100000, 999999)}"


def _inn() -> str:
    return str(random.randint(10**11, 10**12 - 1))


def _snils() -> str:
    return f"{random.randint(100, 999)}-{random.randint(100, 999)}-{random.randint(100, 999)} {random.randint(10, 99)}"


def _ip() -> str:
    return f"{random.randint(1, 254)}.{random.randint(0, 254)}.{random.randint(0, 254)}.{random.randint(1, 254)}"


def _mac() -> str:
    return ":".join(f"{random.randint(0, 255):02X}" for _ in range(6))


def _cardholder() -> str:
    return f"{random.choice(_LAST).upper()} {random.choice(_FIRST).upper()}"


def _clean_text() -> str:
    """Случайный текст без ПД."""
    templates = [
        "Сегодня хорошая погода на улице.",
        "Документ подписан в установленном порядке.",
        "Прошу рассмотреть моё заявление.",
        "Отчёт за квартал готов к проверке.",
        "Встреча назначена на следующей неделе.",
        "Сотрудник выполнил поставленную задачу.",
        "Договор вступает в силу с момента подписания.",
        "Необходимо согласовать бюджет проекта.",
        "План работ утверждён руководством.",
        "Заявка зарегистрирована в системе.",
    ]
    return random.choice(templates)


def _list_text(*fields: str) -> str:
    """Собрать длинный текст-анкету из полей через запятую."""
    return ", ".join(f for f in fields if f)


# --- Генераторы по типам ---------------------------------------------------

def _gen_passport(n: int) -> list[tuple[str, int]]:
    out = []
    for _ in range(n):
        p = _passport()
        out.append((f"Паспорт РФ серия {p}, выдан ОВД.", 1))
        out.append((f"Серия и номер паспорта: {p}.", 1))
        out.append((_list_text(f"ФИО {_fio()}", f"паспорт {p}", f"тел {_phone()}"), 1))
        # Паспорт рядом с ИНН — модель должна всё равно видеть паспорт.
        out.append((_list_text(f"паспорт {p}", f"ИНН {_inn()}"), 1))
        out.append((_clean_text(), 0))
        out.append((f"ИНН {_inn()}", 0))
        out.append((_list_text(f"ФИО {_fio()}", f"ИНН {_inn()}", f"тел {_phone()}"), 0))
        # «порт» — подстрока «паспорт»; учим не путать с портом сервера.
        out.append((f"Сервер {_ip()}, порт {random.randint(1024, 65535)}", 0))
        out.append((f"MAC {_mac()}", 0))
    return out


def _gen_license(n: int) -> list[tuple[str, int]]:
    out = []
    for _ in range(n):
        p = _passport()
        out.append((f"Водительское удостоверение {p}.", 1))
        out.append((f"Серия и номер прав: {p}.", 1))
        out.append((_list_text(f"ФИО {_fio()}", f"права {p}", f"тел {_phone()}"), 1))
        out.append((_clean_text(), 0))
        out.append((f"Паспорт {_passport()}", 0))
        out.append((_list_text(f"ФИО {_fio()}", f"паспорт {_passport()}", f"тел {_phone()}"), 0))
        out.append((f"MAC {_mac()}", 0))
        out.append((f"IP {_ip()}", 0))
    return out


def _gen_citizenship(n: int) -> list[tuple[str, int]]:
    out = []
    for _ in range(n):
        c = random.choice(_COUNTRIES)
        out.append((f"Гражданство: {c}.", 1))
        out.append((f"Является гражданином {c}.", 1))
        out.append((_list_text(f"ФИО {_fio()}", f"гражданство {c}", f"тел {_phone()}"), 1))
        out.append((_clean_text(), 0))
        out.append((f"Адрес: {_address()}", 0))
        out.append((_list_text(f"ФИО {_fio()}", f"адрес {_address()}", f"тел {_phone()}"), 0))
    return out


def _gen_issuing_authority(n: int) -> list[tuple[str, int]]:
    out = []
    for _ in range(n):
        out.append((f"ОВД Ленинского района г. {random.choice(_CITIES)}", 1))
        out.append((f"УФМС России по г. {random.choice(_CITIES)}", 1))
        out.append((_list_text(f"паспорт {_passport()}", f"выдан ОВД г. {random.choice(_CITIES)}"), 1))
        out.append((_clean_text(), 0))
        out.append((f"Паспорт {_passport()}", 0))
        out.append((_list_text(f"ФИО {_fio()}", f"паспорт {_passport()}", f"тел {_phone()}"), 0))
        out.append((f"MAC {_mac()}", 0))
        out.append((f"IP {_ip()}", 0))
    return out


def _gen_issue_code(n: int) -> list[tuple[str, int]]:
    out = []
    for _ in range(n):
        code = f"{random.randint(100, 999)}-{random.randint(100, 999)}"
        out.append((f"Код подразделения {code}.", 1))
        out.append((f"Подразделение: {code}.", 1))
        out.append((_list_text(f"паспорт {_passport()}", f"код подразделения {code}"), 1))
        out.append((_clean_text(), 0))
        out.append((f"Телефон {_phone()}", 0))
        out.append((_list_text(f"ФИО {_fio()}", f"тел {_phone()}", f"email {_email()}"), 0))
    return out


def _gen_date(n: int) -> list[tuple[str, int]]:
    out = []
    for _ in range(n):
        d = _date()
        out.append((f"Дата рождения: {d}.", 1))
        out.append((f"Родился {d}.", 1))
        out.append((_list_text(f"ФИО {_fio()}", f"дата рождения {d}", f"тел {_phone()}"), 1))
        out.append((_clean_text(), 0))
        out.append((f"ИНН {_inn()}", 0))
        out.append((_list_text(f"ФИО {_fio()}", f"ИНН {_inn()}", f"тел {_phone()}"), 0))
    return out


def _gen_address(n: int) -> list[tuple[str, int]]:
    out = []
    for _ in range(n):
        a = _address()
        out.append((f"Адрес регистрации: {a}.", 1))
        out.append((f"Проживает по адресу {a}.", 1))
        out.append((_list_text(f"ФИО {_fio()}", f"адрес {a}", f"тел {_phone()}"), 1))
        out.append((_clean_text(), 0))
        out.append((f"ФИО: {_fio()}", 0))
        out.append((_list_text(f"ФИО {_fio()}", f"ИНН {_inn()}", f"тел {_phone()}"), 0))
    return out


def _gen_fio(n: int) -> list[tuple[str, int]]:
    out = []
    for _ in range(n):
        f = _fio()
        out.append((f"ФИО: {f}.", 1))
        out.append((f"Сотрудник {_fio_short()}.", 1))
        out.append((_list_text(f"ФИО {f}", f"тел {_phone()}", f"email {_email()}"), 1))
        out.append((_clean_text(), 0))
        out.append((f"Компания {random.choice(_ORGS)}", 0))
        out.append((_list_text(f"компания {random.choice(_ORGS)}", f"тел {_phone()}", f"email {_email()}"), 0))
        # Латиница/hex-строки, похожие на имя, но не ФИО.
        out.append((f"MAC {_mac()}", 0))
        out.append((f"Cardholder {_cardholder()}", 0))
    return out


def _gen_fam_fio(n: int) -> list[tuple[str, int]]:
    famous = [
        "Александр Сергеевич Пушкин",
        "Лев Николаевич Толстой",
        "Фёдор Михайлович Достоевский",
        "Владимир Владимирович Путин",
        "Юрий Алексеевич Гагарин",
        "Пётр Ильич Чайковский",
        "Дмитрий Иванович Менделеев",
        "Михаил Васильевич Ломоносов",
    ]
    out = []
    for _ in range(n):
        f = random.choice(famous)
        out.append((f"Поэт {f}.", 1))
        out.append((f"Президент {f}.", 1))
        out.append((_list_text(f"писатель {f}", f"родился в {random.randint(1700, 1900)} году"), 1))
        out.append((_clean_text(), 0))
        out.append((f"ФИО: {_fio()}", 0))
        out.append((_list_text(f"ФИО {_fio()}", f"тел {_phone()}", f"email {_email()}"), 0))
    return out


def _gen_email(n: int) -> list[tuple[str, int]]:
    out = []
    for _ in range(n):
        e = _email()
        out.append((f"Email: {e}.", 1))
        out.append((f"Почта {e}.", 1))
        out.append((_list_text(f"ФИО {_fio()}", f"email {e}", f"тел {_phone()}"), 1))
        out.append((_clean_text(), 0))
        out.append((f"Телефон {_phone()}", 0))
        out.append((_list_text(f"ФИО {_fio()}", f"тел {_phone()}", f"адрес {_address()}"), 0))
        out.append((f"MAC {_mac()}", 0))
        out.append((f"IP {_ip()}", 0))
    return out


def _gen_phone(n: int) -> list[tuple[str, int]]:
    out = []
    for _ in range(n):
        p = _phone()
        out.append((f"Телефон: {p}.", 1))
        out.append((f"Мобильный {p}.", 1))
        out.append((_list_text(f"ФИО {_fio()}", f"тел {p}", f"email {_email()}"), 1))
        out.append((_clean_text(), 0))
        out.append((f"Email {_email()}", 0))
        out.append((_list_text(f"ФИО {_fio()}", f"email {_email()}", f"адрес {_address()}"), 0))
    return out


def _gen_inn(n: int) -> list[tuple[str, int]]:
    out = []
    for _ in range(n):
        i = _inn()
        out.append((f"ИНН: {i}.", 1))
        out.append((f"ИНН налогоплательщика {i}.", 1))
        out.append((_list_text(f"ФИО {_fio()}", f"ИНН {i}", f"тел {_phone()}"), 1))
        out.append((_clean_text(), 0))
        out.append((f"Паспорт {_passport()}", 0))
        out.append((_list_text(f"ФИО {_fio()}", f"паспорт {_passport()}", f"тел {_phone()}"), 0))
    return out


def _gen_card_number(n: int) -> list[tuple[str, int]]:
    out = []
    for _ in range(n):
        c = _card()
        out.append((f"Номер карты: {c}.", 1))
        out.append((f"Карта {c}.", 1))
        out.append((_list_text(f"держатель {_cardholder()}", f"карта {c}", f"CVV {random.randint(100, 999)}"), 1))
        out.append((_clean_text(), 0))
        out.append((f"ИНН {_inn()}", 0))
        out.append((_list_text(f"ФИО {_fio()}", f"ИНН {_inn()}", f"тел {_phone()}"), 0))
    return out


def _gen_cvv(n: int) -> list[tuple[str, int]]:
    out = []
    for _ in range(n):
        cvv = random.randint(100, 999)
        out.append((f"CVV: {cvv}.", 1))
        out.append((f"CVC-код {cvv}.", 1))
        out.append((_list_text(f"карта {_card()}", f"CVV {cvv}", f"держатель {_cardholder()}"), 1))
        out.append((_clean_text(), 0))
        out.append((f"Пин-код {random.randint(1000, 9999)}", 0))
        out.append((_list_text(f"карта {_card()}", f"PIN {random.randint(1000, 9999)}"), 0))
    return out


def _gen_pin(n: int) -> list[tuple[str, int]]:
    out = []
    for _ in range(n):
        pin = random.randint(1000, 9999)
        out.append((f"Пин-код: {pin}.", 1))
        out.append((f"PIN {pin}.", 1))
        out.append((_list_text(f"карта {_card()}", f"PIN {pin}", f"держатель {_cardholder()}"), 1))
        out.append((_clean_text(), 0))
        out.append((f"CVV {random.randint(100, 999)}", 0))
        out.append((_list_text(f"карта {_card()}", f"CVV {random.randint(100, 999)}"), 0))
        # Длинные цифровые строки — не пин-код.
        out.append((f"ИНН {_inn()}", 0))
        out.append((f"Телефон {_phone()}", 0))
    return out


def _gen_cardholder(n: int) -> list[tuple[str, int]]:
    out = []
    for _ in range(n):
        ch = _cardholder()
        out.append((f"Cardholder: {ch}.", 1))
        out.append((f"Имя на карте {ch}.", 1))
        out.append((_list_text(f"карта {_card()}", f"cardholder {ch}", f"CVV {random.randint(100, 999)}"), 1))
        out.append((_clean_text(), 0))
        out.append((f"ФИО: {_fio()}", 0))
        out.append((_list_text(f"ФИО {_fio()}", f"тел {_phone()}", f"email {_email()}"), 0))
    return out


def _gen_military_id(n: int) -> list[tuple[str, int]]:
    out = []
    for _ in range(n):
        m = f"{random.choice(['АБ', 'ВС', 'МК', 'НР'])} {random.randint(10, 99)} {random.randint(1000000, 9999999)}"
        out.append((f"Военный билет {m}.", 1))
        out.append((f"ВБ серия {m}.", 1))
        out.append((_list_text(f"ФИО {_fio()}", f"военный билет {m}", f"тел {_phone()}"), 1))
        out.append((_clean_text(), 0))
        out.append((f"Паспорт {_passport()}", 0))
        out.append((_list_text(f"ФИО {_fio()}", f"паспорт {_passport()}", f"тел {_phone()}"), 0))
        # Длинные цифровые строки (ИНН, ОМС) — не военный билет.
        out.append((f"ИНН {_inn()}", 0))
        out.append((f"Полис ОМС {random.randint(10**15, 10**16 - 1)}", 0))
    return out


def _gen_foreign_passport(n: int) -> list[tuple[str, int]]:
    out = []
    for _ in range(n):
        fp = f"{random.randint(10, 99)} №{random.randint(1000000, 9999999)}"
        out.append((f"Загранпаспорт {fp}.", 1))
        out.append((f"Заграничный паспорт {fp}.", 1))
        out.append((_list_text(f"ФИО {_fio()}", f"загранпаспорт {fp}", f"тел {_phone()}"), 1))
        out.append((_clean_text(), 0))
        out.append((f"Паспорт {_passport()}", 0))
        out.append((_list_text(f"ФИО {_fio()}", f"паспорт {_passport()}", f"тел {_phone()}"), 0))
    return out


def _gen_snils(n: int) -> list[tuple[str, int]]:
    out = []
    for _ in range(n):
        s = _snils()
        out.append((f"СНИЛС: {s}.", 1))
        out.append((f"Страховой номер {s}.", 1))
        out.append((_list_text(f"ФИО {_fio()}", f"СНИЛС {s}", f"тел {_phone()}"), 1))
        out.append((_clean_text(), 0))
        out.append((f"ИНН {_inn()}", 0))
        out.append((_list_text(f"ФИО {_fio()}", f"ИНН {_inn()}", f"тел {_phone()}"), 0))
    return out


def _gen_birth_cert(n: int) -> list[tuple[str, int]]:
    out = []
    for _ in range(n):
        bc = f"{random.choice(['I-МЮ', 'II-ЕВ', 'III-АБ', 'IV-КН'])} №{random.randint(100000, 999999)}"
        out.append((f"Свидетельство о рождении {bc}.", 1))
        out.append((f"Свидетельство о рождении {bc}.", 1))
        out.append((_list_text(f"ФИО {_fio()}", f"свидетельство о рождении {bc}", f"тел {_phone()}"), 1))
        out.append((_clean_text(), 0))
        out.append((f"Паспорт {_passport()}", 0))
        out.append((_list_text(f"ФИО {_fio()}", f"паспорт {_passport()}", f"тел {_phone()}"), 0))
    return out


def _gen_oms(n: int) -> list[tuple[str, int]]:
    out = []
    for _ in range(n):
        o = random.randint(10**15, 10**16 - 1)
        out.append((f"Полис ОМС {o}.", 1))
        out.append((f"ОМС {o}.", 1))
        out.append((_list_text(f"ФИО {_fio()}", f"полис ОМС {o}", f"тел {_phone()}"), 1))
        out.append((_clean_text(), 0))
        out.append((f"ИНН {_inn()}", 0))
        out.append((_list_text(f"ФИО {_fio()}", f"ИНН {_inn()}", f"тел {_phone()}"), 0))
    return out


def _gen_dmc(n: int) -> list[tuple[str, int]]:
    out = []
    for _ in range(n):
        d = random.randint(10**9, 10**10 - 1)
        out.append((f"Полис ДМС {d}.", 1))
        out.append((f"ДМС {d}.", 1))
        out.append((_list_text(f"ФИО {_fio()}", f"полис ДМС {d}", f"тел {_phone()}"), 1))
        out.append((_clean_text(), 0))
        out.append((f"ИНН {_inn()}", 0))
        out.append((_list_text(f"ФИО {_fio()}", f"ИНН {_inn()}", f"тел {_phone()}"), 0))
    return out


def _gen_migration_card(n: int) -> list[tuple[str, int]]:
    out = []
    for _ in range(n):
        m = random.randint(10**9, 10**10 - 1)
        out.append((f"Миграционная карта {m}.", 1))
        out.append((f"Номер миграционной карты {m}.", 1))
        out.append((_list_text(f"ФИО {_fio()}", f"миграционная карта {m}", f"тел {_phone()}"), 1))
        out.append((_clean_text(), 0))
        out.append((f"ИНН {_inn()}", 0))
        out.append((_list_text(f"ФИО {_fio()}", f"ИНН {_inn()}", f"тел {_phone()}"), 0))
    return out


def _gen_social_login(n: int) -> list[tuple[str, int]]:
    out = []
    for _ in range(n):
        s = f"@{random.choice(_LAST).lower()}_{random.randint(1, 99)}"
        out.append((f"Логин {random.choice(_SOCIAL)} {s}.", 1))
        out.append((f"Соцсеть {random.choice(_SOCIAL)}: {s}.", 1))
        out.append((_list_text(f"ФИО {_fio()}", f"логин {s}", f"тел {_phone()}"), 1))
        out.append((_clean_text(), 0))
        out.append((f"Email {_email()}", 0))
        out.append((_list_text(f"ФИО {_fio()}", f"email {_email()}", f"тел {_phone()}"), 0))
    return out


def _gen_ip_address(n: int) -> list[tuple[str, int]]:
    out = []
    for _ in range(n):
        ip = _ip()
        out.append((f"IP-адрес: {ip}.", 1))
        out.append((f"Адрес устройства {ip}.", 1))
        out.append((_list_text(f"сервер {ip}", f"порт 8080", f"MAC {_mac()}"), 1))
        out.append((_clean_text(), 0))
        out.append((f"MAC {_mac()}", 0))
        # Почтовый индекс похож на IP-октеты — негатив.
        out.append((f"Индекс {random.randint(100000, 999999)}", 0))
        out.append((_list_text(f"адрес {_address()}", f"тел {_phone()}"), 0))
    return out


def _gen_mac_address(n: int) -> list[tuple[str, int]]:
    out = []
    for _ in range(n):
        m = _mac()
        out.append((f"MAC-адрес: {m}.", 1))
        out.append((f"MAC {m}.", 1))
        out.append((_list_text(f"сервер {_ip()}", f"MAC {m}", f"порт 8080"), 1))
        out.append((_clean_text(), 0))
        out.append((f"IP {_ip()}", 0))
        out.append((_list_text(f"сервер {_ip()}", f"порт 8080"), 0))
        # Длинные цифровые строки — не MAC.
        out.append((f"ИНН {_inn()}", 0))
        out.append((f"Полис ОМС {random.randint(10**15, 10**16 - 1)}", 0))
    return out


def _gen_password(n: int) -> list[tuple[str, int]]:
    out = []
    for _ in range(n):
        p = random.choice(['qwerty123', 'password1', 'secret2024', 'admin123', 'letmein', 'P@ssw0rd!', '12345678'])
        out.append((f"Пароль: {p}.", 1))
        out.append((f"Пароль от аккаунта {p}.", 1))
        out.append((_list_text(f"логин {random.choice(_SOCIAL)}", f"пароль {p}"), 1))
        out.append((_clean_text(), 0))
        out.append((f"ИНН {_inn()}", 0))
        out.append((_list_text(f"ФИО {_fio()}", f"ИНН {_inn()}", f"тел {_phone()}"), 0))
    return out


def _gen_profession(n: int) -> list[tuple[str, int]]:
    out = []
    for _ in range(n):
        p = random.choice(_PROF)
        out.append((f"Профессия: {p}.", 1))
        out.append((f"Работает {p}ом.", 1))
        out.append((_list_text(f"ФИО {_fio()}", f"профессия {p}", f"тел {_phone()}"), 1))
        out.append((_clean_text(), 0))
        out.append((f"ФИО: {_fio()}", 0))
        out.append((_list_text(f"ФИО {_fio()}", f"тел {_phone()}", f"email {_email()}"), 0))
    return out


def _gen_company(n: int) -> list[tuple[str, int]]:
    out = []
    for _ in range(n):
        c = random.choice(_ORGS)
        out.append((f"Компания: {c}.", 1))
        out.append((f"Работает в {c}.", 1))
        out.append((_list_text(f"ФИО {_fio()}", f"компания {c}", f"тел {_phone()}"), 1))
        out.append((_clean_text(), 0))
        out.append((f"ФИО: {_fio()}", 0))
        out.append((_list_text(f"ФИО {_fio()}", f"тел {_phone()}", f"email {_email()}"), 0))
    return out


# --- Реестр генераторов ----------------------------------------------------

_GENERATORS = {
    "PASSPORT": _gen_passport,
    "LICENSE": _gen_license,
    "CITIZENSHIP": _gen_citizenship,
    "ISSUING_AUTHORITY": _gen_issuing_authority,
    "ISSUE_CODE": _gen_issue_code,
    "DATE": _gen_date,
    "ADDRESS": _gen_address,
    "FIO": _gen_fio,
    "FAM_FIO": _gen_fam_fio,
    "EMAIL": _gen_email,
    "PHONE": _gen_phone,
    "INN": _gen_inn,
    "CARD_NUMBER": _gen_card_number,
    "CVV": _gen_cvv,
    "PIN": _gen_pin,
    "CARDHOLDER": _gen_cardholder,
    "MILITARY_ID": _gen_military_id,
    "FOREIGN_PASSPORT": _gen_foreign_passport,
    "SNILS": _gen_snils,
    "BIRTH_CERT": _gen_birth_cert,
    "OMS": _gen_oms,
    "DMC": _gen_dmc,
    "MIGRATION_CARD": _gen_migration_card,
    "SOCIAL_LOGIN": _gen_social_login,
    "IP_ADDRESS": _gen_ip_address,
    "MAC_ADDRESS": _gen_mac_address,
    "PASSWORD": _gen_password,
    "PROFESSION": _gen_profession,
    "COMPANY": _gen_company,
}

# Сколько пар (позитив, негатив) генерировать на тип.
SAMPLES_PER_TYPE = 400


def generate(code: str, n: int = SAMPLES_PER_TYPE) -> list[tuple[str, int]]:
    """Сгенерировать синтетику для типа ПД: список (текст, метка)."""
    gen = _GENERATORS.get(code)
    if gen is None:
        raise KeyError(f"Нет генератора для типа {code}")
    return gen(n)


def all_codes() -> list[str]:
    return list(_GENERATORS.keys())