"""Поиск адресов по справочнику КЛАДР (города и улицы).

Загружает KLADR.dbf (населённые пункты) и STREET.dbf (улицы) в память
и ищет город, улицу и дом в тексте. Возвращает одну сущность ADDRESS.

Чтобы не путать названия из справочника с обычными словами и фамилиями,
город и улица считаются найденными только при наличии явного маркера
(г., ул., пр-т, ...) рядом с названием, либо города рядом с улицей.
"""

import re
from pathlib import Path

from dbfread import DBF

# Типы населённых пунктов, которые считаем городами/населёнными пунктами.
CITY_SOCR = {
    "г", "пгт", "п", "с", "д", "х", "ст", "рп", "м", "нп", "сл", "аул",
    "кп", "п/ст", "ж/д_ст", "мкр", "тер", "снт", "дп", "с/с", "с/п",
}

# Маркеры города (перед названием).
CITY_MARKERS = {"г", "город", "гор", "г."}

# Маркеры улицы, которые могут стоять перед или после названия.
STREET_MARKERS = {
    "ул", "улица", "пр-т", "проспект", "пер", "переулок", "ш", "шоссе",
    "пл", "площадь", "аллея", "бульвар", "б-р", "наб", "набережная",
    "проезд", "пр-д", "туп", "тупик", "линия", "кв-л", "мкр",
}

# Слово: кириллица/латиница/цифры/дефис.
WORD_RE = re.compile(r"[А-ЯЁа-яёA-Za-z0-9\-]+")


def _norm(s: str) -> str:
    """Нормализует название: нижний регистр, без лишних пробелов."""
    return re.sub(r"\s+", " ", s.strip().lower())


class AddressBook:
    """Справочник городов и улиц из КЛАДР."""

    def __init__(self, base_dir: str | Path = "BASE"):
        self.base_dir = Path(base_dir)
        self.cities: set[str] = set()
        self.streets: set[str] = set()
        self._load()

    def _load(self) -> None:
        """Загружает города и улицы из DBF-файлов КЛАДР."""
        kladr = self.base_dir / "KLADR.dbf"
        street = self.base_dir / "STREET.dbf"

        if kladr.exists():
            for rec in DBF(str(kladr), encoding="cp866"):
                socr = _norm(rec["SOCR"])
                if socr in CITY_SOCR:
                    name = _norm(rec["NAME"])
                    if len(name) >= 3 and not name.isdigit():
                        self.cities.add(name)

        if street.exists():
            for rec in DBF(str(street), encoding="cp866"):
                name = _norm(rec["NAME"])
                if len(name) >= 3 and not name.isdigit():
                    self.streets.add(name)

    def find_address(self, text: str) -> str | None:
        """Ищет первый адрес в тексте. Возвращает фрагмент или None."""
        addrs = self.find_addresses(text)
        return addrs[0] if addrs else None

    def find_addresses(self, text: str) -> list[str]:
        """Ищет все адреса в тексте. Возвращает список фрагментов."""
        tokens = [(m.group(0), m.start(), m.end()) for m in WORD_RE.finditer(text)]
        if not tokens:
            return []

        words = [t[0] for t in tokens]

        # Находим все улицы (не пересекающиеся).
        streets = self._find_streets(words)
        if not streets:
            return []

        results = []
        for street in streets:
            city = self._find_city(words, street)
            house = self._find_house(text, tokens, words, street)
            frag = self._assemble(text, tokens, city, street, house)
            if frag:
                results.append(frag)
        return results

    def _find_city(
        self,
        words: list[str],
        street: tuple[int, int] | None,
    ) -> tuple[int, int] | None:
        """Ищет город рядом с улицей. Возвращает (start_idx, end_idx).

        Ищет название города в пределах 4 слов до улицы.
        """
        if not street:
            return None
        start = max(0, street[0] - 4)
        for i in range(start, street[0]):
            if _norm(words[i]) in self.cities:
                return (i, i + 1)
        return None

    def _find_streets(self, words: list[str]) -> list[tuple[int, int]]:
        """Ищет все улицы в списке слов. Возвращает список (start_idx, end_idx).

        Улица считается найденной, если непосредственно рядом с названием
        есть маркер (ул., улица, пр-т, ...). Возвращает непересекающиеся
        совпадения, отсортированные по позиции.
        """
        n = len(words)
        found: list[tuple[int, int]] = []

        for size in (3, 2, 1):
            for i in range(n - size + 1):
                name = _norm(" ".join(words[i : i + size]))
                if name not in self.streets:
                    continue
                # Если перед названием маркер города — это город, не улица.
                if i > 0 and _norm(words[i - 1]) in CITY_MARKERS:
                    continue
                span = None
                # Маркер перед названием.
                if i > 0 and _norm(words[i - 1]) in STREET_MARKERS:
                    span = (i, i + size)
                # Маркер после названия — включаем его в диапазон.
                elif i + size < n and _norm(words[i + size]) in STREET_MARKERS:
                    span = (i, i + size + 1)
                if span is None:
                    continue
                # Пропускаем, если пересекается с уже найденной улицей.
                if any(
                    span[0] < s_end and span[1] > s_start
                    for s_start, s_end in found
                ):
                    continue
                found.append(span)

        found.sort(key=lambda s: s[0])
        return found

    def _find_house(
        self,
        text: str,
        tokens: list[tuple[str, int, int]],
        words: list[str],
        street: tuple[int, int] | None,
    ) -> tuple[int, int] | None:
        """Ищет дом в тексте. Возвращает (start, end).

        Ищет «д. N»/«дом N» или число сразу после улицы.
        """
        if not street:
            return None

        # Ищем дом в токенах сразу после улицы.
        after = street[1]
        for j in range(after, min(after + 3, len(tokens))):
            w = words[j]
            # «д. N» / «дом N» — маркер дома, затем число.
            if _norm(w) in {"д", "дом", "д."}:
                if j + 1 < len(tokens) and words[j + 1].isdigit():
                    return (tokens[j][1], tokens[j + 1][2])
                return (tokens[j][1], tokens[j][2])
            # Число сразу после улицы.
            if w.isdigit() and len(w) <= 4:
                return (tokens[j][1], tokens[j][2])
        return None

    def _assemble(
        self,
        text: str,
        tokens: list[tuple[str, int, int]],
        city: tuple[int, int] | None,
        street: tuple[int, int] | None,
        house: tuple[int, int] | None,
    ) -> str | None:
        """Собирает адрес в один фрагмент текста."""
        if not city and not street and not house:
            return None

        positions = []
        if city:
            positions.append(tokens[city[0]][1])
            positions.append(tokens[city[1] - 1][2])
        if street:
            positions.append(tokens[street[0]][1])
            positions.append(tokens[street[1] - 1][2])
        if house:
            positions.append(house[0])
            positions.append(house[1])

        start = min(positions)
        end = max(positions)

        return text[start:end].strip(" ,;:")