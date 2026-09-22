"""Перечисление типов персональных данных (ПДн)."""

from enum import Enum


class DataType(str, Enum):
    """Типы персональных данных, распознаваемые модулем."""

    PASSPORT = "Серия и номер паспорта"
    LICENSE = "Серия и номер водительского удостоверения"
    CITIZENSHIP = "Гражданство"
    ISSUING_AUTHORITY = "Орган, выдавший паспорт"
    ISSUE_CODE = "Код подразделения"
    DATE = "Дата"
    ADDRESS = "Адрес (полный)"
    FIO = "ФИО"
    EMAIL = "Email"
    INN = "ИНН"
    CARD_NUMBER = "Номер платёжной карты"
    CVV = "CVV-код"
    PIN = "Пин-код карты"
    CARDHOLDER = "Имя держателя карты"
    MILITARY_ID = "Военный билет"
    FOREIGN_PASSPORT = "Заграничный паспорт"
    SNILS = "СНИЛС"
    BIRTH_CERT = "Свидетельство о рождении"
    OMS = "Полис ОМС"
    DMC = "Полис ДМС"
    MIGRATION_CARD = "Номер миграционной карты"
    SOCIAL_LOGIN = "Логин в соцсети"
    IP_ADDRESS = "IP-адрес"
    MAC_ADDRESS = "MAC-адрес"
    PASSWORD = "Пароль"
    PHONE = "Номер телефона"