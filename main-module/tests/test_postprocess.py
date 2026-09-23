from app.postprocess import filter_fio_entities, load_names


def _entity(text, types, score=1.0, start=0, end=None, will_be_used=True):
    end = end if end is not None else len(text)
    return {
        "text": text,
        "type": types,
        "score": score,
        "slice": [start, end],
        "will_be_used": will_be_used,
    }


def test_load_names_returns_non_empty() -> None:
    names = load_names()
    assert "иван" in names
    assert "петров" in names
    assert "иванович" in names


def test_keeps_fio_with_known_name() -> None:
    entities = [_entity("Иван Петров", ["FIO"])]
    assert filter_fio_entities(entities) == entities


def test_drops_fio_without_known_name() -> None:
    entities = [_entity("ла, который должен стать настольной книгой", ["FIO"])]
    assert filter_fio_entities(entities) == []


def test_keeps_non_fio_types() -> None:
    entities = [_entity("770123456789", ["INN"])]
    assert filter_fio_entities(entities) == entities


def test_mixed_fio_and_non_fio() -> None:
    entities = [
        _entity("Иван Петров", ["FIO"]),
        _entity("случайный текст", ["FIO"]),
        _entity("770123456789", ["INN"]),
    ]
    result = filter_fio_entities(entities)
    assert len(result) == 2
    assert result[0]["text"] == "Иван Петров"
    assert result[1]["text"] == "770123456789"


def test_fam_fio_is_filtered_too() -> None:
    entities = [_entity("случайный текст", ["FAM_FIO"])]
    assert filter_fio_entities(entities) == []


def test_case_insensitive_match() -> None:
    entities = [_entity("ИВАН ПЕТРОВ", ["FIO"])]
    assert filter_fio_entities(entities) == entities
