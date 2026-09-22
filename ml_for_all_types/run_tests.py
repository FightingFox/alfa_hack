"""Сводный прогон тестов всех моделей-детекторов и ансамбля.

Запуск:  python run_tests.py
Выводит таблицу метрик по каждому типу ПД и проверку ансамбля на
реалистичных текстах. Возвращает ненулевой код, если хоть одна модель
не прошла порог качества.
"""

from __future__ import annotations

import sys
from pathlib import Path

import _common
import _synthetic
import ensemble

ROOT = Path(__file__).resolve().parent

# Минимальный допустимый F1 для каждой модели.
MIN_F1 = 0.95
# Число свежих примеров для оценки каждой модели.
EVAL_N = 200


def run_per_type_tests() -> list[dict]:
    """Оценить каждую модель на свежей синтетике."""
    results = []
    for code in _synthetic.all_codes():
        folder = ROOT / code
        det = _common.PiiDetector.load(folder)
        data = _synthetic.generate(code, EVAL_N)
        texts = [t for t, _ in data]
        labels = [l for _, l in data]
        tp = fp = tn = fn = 0
        for t, l in zip(texts, labels):
            p = det.detect(t)
            if p and l:
                tp += 1
            elif p and not l:
                fp += 1
            elif not p and not l:
                tn += 1
            else:
                fn += 1
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
        results.append({
            "code": code,
            "tp": tp, "fp": fp, "tn": tn, "fn": fn,
            "precision": round(precision, 3),
            "recall": round(recall, 3),
            "f1": round(f1, 3),
            "pass": f1 >= MIN_F1,
        })
    return results


def run_ensemble_smoke() -> list[dict]:
    """Проверка ансамбля на реалистичных текстах."""
    cases = [
        ("Иван Петров, паспорт 4510 123456, ИНН 770123456789, email ivan.petrov@mail.ru, тел +7 (903) 123-45-67",
         {"PASSPORT", "INN", "EMAIL", "PHONE", "FIO"}),
        ("Карта 4111 1111 1111 1111, CVV 123, PIN 1234, держатель IVAN PETROV",
         {"CARD_NUMBER", "CVV", "PIN", "CARDHOLDER"}),
        ("СНИЛС 112-233-445 95, адрес 125167, г. Москва, ул. Правды, д. 24, кв. 5",
         {"SNILS", "ADDRESS"}),
        ("Сегодня хорошая погода на улице.", set()),
        ("Поэт Александр Сергеевич Пушкин родился в 1799 году.", {"FAM_FIO"}),
        ("Сервер 192.168.1.105, MAC 00:1A:2B:3C:4D:5E, порт 8080", {"IP_ADDRESS", "MAC_ADDRESS"}),
    ]
    out = []
    for text, expected in cases:
        found = set(ensemble.detect_types_spans(text))
        out.append({
            "text": text,
            "expected": sorted(expected),
            "found": sorted(found),
            "hit": bool(expected & found),
        })
    return out


def main() -> int:
    print("=" * 70)
    print("СВОДНЫЙ ТЕСТ МОДЕЛЕЙ-ДЕТЕКТОРОВ ПД (ансамбль)")
    print("=" * 70)

    per_type = run_per_type_tests()
    print(f"\n{'Тип':<20}{'TP':>5}{'FP':>5}{'TN':>5}{'FN':>5}{'Prec':>7}{'Rec':>7}{'F1':>7}  Статус")
    print("-" * 70)
    all_pass = True
    for r in per_type:
        status = "OK" if r["pass"] else "FAIL"
        if not r["pass"]:
            all_pass = False
        print(f"{r['code']:<20}{r['tp']:>5}{r['fp']:>5}{r['tn']:>5}{r['fn']:>5}"
              f"{r['precision']:>7}{r['recall']:>7}{r['f1']:>7}  {status}")

    n_pass = sum(1 for r in per_type if r["pass"])
    print("-" * 70)
    print(f"Моделей прошло порог F1>={MIN_F1}: {n_pass}/{len(per_type)}")

    print("\n" + "=" * 70)
    print("ПРОВЕРКА АНСАМБЛЯ НА РЕАЛИСТИЧНЫХ ТЕКСТАХ")
    print("=" * 70)
    for c in run_ensemble_smoke():
        print(f"\nTEXT: {c['text']}")
        print(f"  expected: {c['expected']}")
        print(f"  found:    {c['found']}")
        print(f"  hit:      {c['hit']}")

    print("\n" + "=" * 70)
    if all_pass:
        print("ИТОГ: ВСЕ МОДЕЛИ ПРОШЛИ ТЕСТЫ")
    else:
        print("ИТОГ: ЕСТЬ МОДЕЛИ, НЕ ПРОШЕДШИЕ ТЕСТ")
    print("=" * 70)
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())