from app.masker import mask_text


def _entity(text, types, score, start, end, will_be_used=True):
    return {
        "text": text,
        "type": types,
        "score": score,
        "slice": [start, end],
        "will_be_used": will_be_used,
    }


def _results(**services):
    return {
        name: {"result": entities, "elapsed": 0.1}
        for name, entities in services.items()
    }


def test_filters_out_non_explicit_types() -> None:
    text = "компания Иванов"
    results = _results(
        regex=[
            _entity("компания", ["COMPANY"], 1.0, 0, 8),
            _entity("Иванов", ["FIO"], 1.0, 9, 15),
        ]
    )
    result = mask_text(text, results)
    assert result.masked_text == "компания {{ FIO 1 }}"
    assert len(result.replacements) == 1
    assert result.replacements[0].types == ["FIO"]


def test_merges_overlapping_slices() -> None:
    text = "Иванов Иван"
    results = _results(
        regex=[
            _entity("Иванов", ["FIO"], 0.9, 0, 6),
            _entity("Иванов Иван", ["FIO"], 0.8, 0, 11),
        ]
    )
    result = mask_text(text, results)
    assert len(result.replacements) == 1
    assert result.replacements[0].mask == "{{ FIO 1 }}"


def test_merges_nested_slices() -> None:
    text = "Иванов Иван"
    results = _results(
        regex=[
            _entity("Иванов Иван", ["FIO"], 0.8, 0, 11),
            _entity("Иванов", ["FIO"], 0.9, 0, 6),
        ]
    )
    result = mask_text(text, results)
    assert len(result.replacements) == 1
    assert result.replacements[0].mask == "{{ FIO 1 }}"


def test_touching_slices_do_not_merge() -> None:
    text = "Иванов Петров"
    results = _results(
        regex=[
            _entity("Иванов", ["FIO"], 1.0, 0, 6),
            _entity("Петров", ["FIO"], 1.0, 7, 13),
        ]
    )
    result = mask_text(text, results)
    assert len(result.replacements) == 2
    assert result.masked_text == "{{ FIO 1 }} {{ FIO 2 }}"


def test_representative_by_max_score() -> None:
    text = "Иванов Иван"
    results = _results(
        regex=[
            _entity("Иванов", ["FIO"], 0.7, 0, 6),
            _entity("Иванов Иван", ["FIO"], 0.9, 0, 11),
        ]
    )
    result = mask_text(text, results)
    assert len(result.replacements) == 1
    assert result.replacements[0].slice == [0, 11]
    assert result.replacements[0].original_text == "Иванов Иван"


def test_tie_break_by_service_priority() -> None:
    text = "Иванов"
    results = _results(
        ml=[_entity("Иванов", ["FIO"], 1.0, 0, 6)],
        regex=[_entity("Иванов", ["FIO"], 1.0, 0, 6)],
    )
    result = mask_text(text, results)
    assert len(result.replacements) == 1
    assert result.replacements[0].mask == "{{ FIO 1 }}"


def test_tie_break_by_longer_slice() -> None:
    text = "Иванов Иван"
    results = _results(
        regex=[
            _entity("Иванов", ["FIO"], 1.0, 0, 6),
            _entity("Иванов Иван", ["FIO"], 1.0, 0, 11),
        ]
    )
    result = mask_text(text, results)
    assert len(result.replacements) == 1
    assert result.replacements[0].slice == [0, 11]


def test_sequential_numbering_by_position() -> None:
    text = "Иванов Петров"
    results = _results(
        regex=[
            _entity("Петров", ["FIO"], 1.0, 7, 13),
            _entity("Иванов", ["FIO"], 1.0, 0, 6),
        ]
    )
    result = mask_text(text, results)
    assert result.masked_text == "{{ FIO 1 }} {{ FIO 2 }}"


def test_mask_with_multiple_types() -> None:
    text = "7701234567"
    results = _results(
        gliner=[
            _entity("7701234567", ["PASSPORT", "LICENSE", "INN"], 0.9, 0, 10),
        ]
    )
    result = mask_text(text, results)
    assert result.masked_text == "{{ PASSPORT,LICENSE,INN 1 }}"
    assert result.replacements[0].mask == "{{ PASSPORT,LICENSE,INN 1 }}"


def test_replaces_right_to_left() -> None:
    text = "Иванов Петров"
    results = _results(
        regex=[
            _entity("Иванов", ["FIO"], 1.0, 0, 6),
            _entity("Петров", ["FIO"], 1.0, 7, 13),
        ]
    )
    result = mask_text(text, results)
    assert result.masked_text == "{{ FIO 1 }} {{ FIO 2 }}"


def test_will_be_used_false_is_kept() -> None:
    text = "Иванов"
    results = _results(
        gliner=[_entity("Иванов", ["FIO"], 1.0, 0, 6, will_be_used=False)],
    )
    result = mask_text(text, results)
    assert len(result.replacements) == 1
    assert result.masked_text == "{{ FIO 1 }}"


def test_none_result_is_skipped() -> None:
    text = "Иванов"
    results = {
        "regex": {"result": [_entity("Иванов", ["FIO"], 1.0, 0, 6)], "elapsed": 0.1},
        "llm": {"result": None, "elapsed": 0.1},
    }
    result = mask_text(text, results)
    assert len(result.replacements) == 1
    assert result.masked_text == "{{ FIO 1 }}"


def test_fio_without_known_name_is_filtered() -> None:
    text = "ла, который должен стать настольной книгой для сотрудников н"
    results = _results(
        ml=[_entity(text, ["FIO"], 0.998, 0, len(text))],
    )
    result = mask_text(text, results)
    assert result.masked_text == text
    assert result.replacements == []


def test_fio_with_known_name_is_kept() -> None:
    text = "Иван Петров"
    results = _results(
        ml=[_entity(text, ["FIO"], 0.998, 0, len(text))],
    )
    result = mask_text(text, results)
    assert result.masked_text == "{{ FIO 1 }}"
    assert len(result.replacements) == 1


def test_no_explicit_entities_returns_unchanged() -> None:
    text = "компания"
    results = _results(
        ml=[_entity("компания", ["COMPANY"], 1.0, 0, 8)],
    )
    result = mask_text(text, results)
    assert result.masked_text == "компания"
    assert result.replacements == []
