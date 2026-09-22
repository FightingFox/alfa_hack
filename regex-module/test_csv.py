"""Тесты, читающие тест-кейсы из CSV-файла.

Формат CSV: колонки text, expected_json.
expected_json — JSON-массив ожидаемых совпадений вида:
    [{"text": "...", "type": "PHONE"}, ...]
Пустой массив [] означает, что ПДн не должны быть найдены.
"""

import csv
import json
import os
import unittest

from data_type import DataType
from scan import scan

CSV_PATH = os.path.join(os.path.dirname(__file__), "test_cases.csv")


def load_cases():
    """Загружает тест-кейсы из CSV-файла.

    Пропускает повторные строки-заголовки и строки с некорректным JSON.
    """
    cases = []
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            text = row.get("text")
            expected_raw = row.get("expected_json")
            if text is None or expected_raw is None:
                continue
            if text == "text" and expected_raw == "expected_json":
                continue
            try:
                expected = json.loads(expected_raw)
            except json.JSONDecodeError:
                continue
            cases.append({"text": text, "expected": expected})
    return cases


class TestScanFromCSV(unittest.TestCase):
    def test_cases_from_csv(self):
        cases = load_cases()
        self.assertTrue(cases, "CSV-файл с тест-кейсами пуст или не найден")

        for case in cases:
            text = case["text"]
            expected = case["expected"]
            with self.subTest(text=text):
                results = scan(text)

                if not expected:
                    self.assertEqual(
                        results,
                        [],
                        f"Ожидалось отсутствие ПДн в {text!r}, но найдено: {results}",
                    )
                    continue

                for exp in expected:
                    exp_type = DataType[exp["type"]]
                    exp_text = exp["text"]
                    matches = [
                        r for r in results
                        if r["type"] == exp_type and r["text"] == exp_text
                    ]
                    self.assertTrue(
                        matches,
                        f"Не найдено совпадение {exp_text!r} типа {exp_type!r} "
                        f"в {text!r}. Результаты: {results}",
                    )


if __name__ == "__main__":
    unittest.main()