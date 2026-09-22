"""Тесты для модуля определения персональных данных (scan.py)."""

import unittest

from data_type import DataType
from scan import scan


class TestScan(unittest.TestCase):
    def assert_found(self, text, pii_type, expected_value):
        """Проверяет, что в text найден фрагмент expected_value типа pii_type."""
        results = scan(text)
        matches = [r for r in results if r["type"] == pii_type]
        self.assertTrue(
            matches,
            f"Не найден тип {pii_type!r} в {text!r}. Результаты: {results}",
        )
        self.assertIn(
            expected_value,
            [r["text"] for r in matches],
            f"Ожидался фрагмент {expected_value!r} типа {pii_type!r} в {text!r}",
        )

    def test_phone_international(self):
        self.assert_found("+7 (916) 123-45-67", DataType.PHONE, "+7 (916) 123-45-67")

    def test_phone_compact(self):
        self.assert_found("+79161234567", DataType.PHONE, "+79161234567")

    def test_phone_russian(self):
        self.assert_found("8 495 123-45-67", DataType.PHONE, "8 495 123-45-67")

    def test_email_simple(self):
        self.assert_found("user@example.com", DataType.EMAIL, "user@example.com")

    def test_email_with_dots(self):
        self.assert_found("first.last@sub.domain.ru", DataType.EMAIL, "first.last@sub.domain.ru")

    def test_inn_10(self):
        self.assert_found("ИНН 7707083893", DataType.INN, "7707083893")

    def test_inn_12(self):
        self.assert_found("ИНН 500100732259", DataType.INN, "500100732259")

    def test_snils(self):
        self.assert_found("СНИЛС 112-233-445 95", DataType.SNILS, "112-233-445 95")

    def test_passport(self):
        self.assert_found("Паспорт 4510 123456", DataType.PASSPORT, "4510 123456")

    def test_card_spaced(self):
        self.assert_found("Карта 4111 1111 1111 1111", DataType.CARD_NUMBER, "4111 1111 1111 1111")

    def test_card_compact(self):
        self.assert_found("Карта 4111111111111111", DataType.CARD_NUMBER, "4111111111111111")

    def test_date_dotted(self):
        self.assert_found("Дата рождения 12.05.1990", DataType.DATE, "12.05.1990")

    def test_date_iso(self):
        self.assert_found("Дата 1990-05-12", DataType.DATE, "1990-05-12")

    def test_fio_full(self):
        self.assert_found("Пушкин Александр Сергеевич", DataType.FIO, "Пушкин Александр Сергеевич")

    def test_fio_two_words(self):
        self.assert_found("Иванов Иван", DataType.FIO, "Иванов Иван")

    def test_license(self):
        self.assert_found("Водительское удостоверение 7712 345678", DataType.LICENSE, "7712 345678")

    def test_citizenship(self):
        self.assert_found("гражданство: РФ", DataType.CITIZENSHIP, "РФ")

    def test_issuing_authority(self):
        self.assert_found("выдан ОВД Ленинского района г. Москвы", DataType.ISSUING_AUTHORITY, "ОВД Ленинского района г. Москвы")

    def test_issue_code(self):
        self.assert_found("код подразделения 770-001", DataType.ISSUE_CODE, "770-001")

    def test_address(self):
        self.assert_found("125167, г. Москва, ул. Правды, д. 24, кв. 5", DataType.ADDRESS, "125167, г. Москва, ул. Правды, д. 24, кв. 5")

    def test_cvv(self):
        self.assert_found("CVV: 123", DataType.CVV, "123")

    def test_pin(self):
        self.assert_found("пин: 1234", DataType.PIN, "1234")

    def test_cardholder(self):
        self.assert_found("cardholder: IVAN PETROV", DataType.CARDHOLDER, "IVAN PETROV")

    def test_military_id(self):
        self.assert_found("военный билет АБ 12 1234567", DataType.MILITARY_ID, "АБ 12 1234567")

    def test_foreign_passport(self):
        self.assert_found("загранпаспорт 75 №1234567", DataType.FOREIGN_PASSPORT, "75 №1234567")

    def test_birth_cert(self):
        self.assert_found("свидетельство о рождении I-МЮ №123456", DataType.BIRTH_CERT, "I-МЮ №123456")

    def test_oms(self):
        self.assert_found("полис ОМС 5400000000000000", DataType.OMS, "5400000000000000")

    def test_dmc(self):
        self.assert_found("полис ДМС 0123456789", DataType.DMC, "0123456789")

    def test_migration_card(self):
        self.assert_found("миграционная карта 0012345678", DataType.MIGRATION_CARD, "0012345678")

    def test_social_login(self):
        self.assert_found("@petr_ivanov87", DataType.SOCIAL_LOGIN, "@petr_ivanov87")

    def test_ip_address(self):
        self.assert_found("IP 192.168.1.105", DataType.IP_ADDRESS, "192.168.1.105")

    def test_mac_address(self):
        self.assert_found("MAC 00:1A:2B:3C:4D:5E", DataType.MAC_ADDRESS, "00:1A:2B:3C:4D:5E")

    def test_password(self):
        self.assert_found("пароль: Qwerty!2024#Secure", DataType.PASSWORD, "Qwerty!2024#Secure")

    def test_result_fields(self):
        text = "Позвоните +7 (916) 123-45-67"
        results = scan(text)
        self.assertTrue(results)
        for r in results:
            self.assertIn("text", r)
            self.assertIn("type", r)
            self.assertIn("score", r)
            self.assertIn("slice", r)
            self.assertEqual(r["score"], 1.0)
            self.assertIsInstance(r["type"], DataType)
            start, end = r["slice"]
            self.assertEqual(r["text"], text[start:end])

    def test_empty_text(self):
        self.assertEqual(scan(""), [])

    def test_no_pii(self):
        self.assertEqual(scan("обычный текст без данных"), [])

    def test_sorted_by_slice(self):
        text = "email ivan@mail.ru, тел +7 (916) 123-45-67, паспорт 4510 123456"
        results = scan(text)
        self.assertTrue(results)
        slices = [r["slice"] for r in results]
        self.assertEqual(slices, sorted(slices))


if __name__ == "__main__":
    unittest.main()