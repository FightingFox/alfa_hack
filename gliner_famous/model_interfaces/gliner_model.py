"""Единая точка вызова модели GLiNER.

Обёртка над моделью: ленивая загрузка весов и извлечение сущностей ПД.
Используется сервисом (app/) и скриптами вроде ner.py.
"""

from functools import lru_cache
from pathlib import Path
import logging
import warnings

from gliner import GLiNER

MODEL_DIR = str(Path(__file__).resolve().parent.parent / "models" / "gliner_small-v2.1")

# Ложное предупреждение transformers: модель обучена на ▁-токенах DebertaV2,
# а fix_mistral_regex=True сломал бы токенизацию (проверено). Подавляем.
warnings.filterwarnings(
    "ignore",
    message=".*incorrect regex pattern.*fix_mistral_regex.*",
)
logging.getLogger("transformers.tokenization_utils_tokenizers").setLevel(logging.ERROR)

# Размер чанка в токенах при обработке длинных текстов. Один прогон GLiNER
# не может обработать очень длинный текст (память), поэтому текст режется
# на чанки этого размера. 512 — оптимум по скорости (бенчмарк).
MAX_LENGTH = 512

# Сколько чанков обрабатывать за один вызов модели.
BATCH_SIZE = 8

# Перекрытие соседних чанков в токенах. Нужно, чтобы сущность, попавшая на
# границу чанка, не разрезалась и не терялась: она будет найдена целиком
# в перекрывающейся зоне соседнего чанка.
CHUNK_OVERLAP = 64

# Порог (в токенах): если текст не длиннее этого — обрабатываем одним прогоном
# (быстрее для средних текстов). Длиннее — чанкинг с MAX_LENGTH.
SINGLE_MAX_LENGTH = 1024

LABELS = [
    "person",
    "phone number",
    "email",
    "date",
    "address",
    "location",
    "organization",
    "bank card number",
    "id number",
    "profession",
    "job",
    "citizenship",
    "nationality",
    "issuing authority",
    "authority",
    "issue code",
    "department code",
    "cardholder",
    "card holder name",
    "military id",
    "military document",
    "foreign passport",
    "passport",
    "snils",
    "insurance number",
    "birth certificate",
    "oms",
    "insurance policy",
    "dmc",
    "migration card",
    "social login",
    "username",
    "ip address",
    "mac address",
    "password",
    "secret",
    "cvv",
    "cvc",
    "pin",
    "pin code",
]


@lru_cache(maxsize=1)
def get_model(model_dir: str = MODEL_DIR, max_length: int = MAX_LENGTH) -> GLiNER:
    """Загрузить модель один раз и переиспользовать её между вызовами."""
    return GLiNER.from_pretrained(model_dir, max_length=max_length)


def extract_entities(
    text: str,
    labels: list[str] | None = None,
    threshold: float = 0.3,
    model_dir: str = MODEL_DIR,
    max_length: int = MAX_LENGTH,
) -> list[dict]:
    """Найти сущности в тексте.

    Возвращает список словарей с ключами text, label, score, start, end.
    """
    model = get_model(model_dir, max_length)
    return model.predict_entities(text, labels or LABELS, threshold=threshold)


def warmup(text: str = "прогрев модели", model_dir: str = MODEL_DIR, max_length: int = MAX_LENGTH) -> None:
    """Прогреть модель: первый инференс заметно медленнее последующих."""
    extract_entities(text, threshold=0.3, model_dir=model_dir, max_length=max_length)


def _chunk_offsets(text: str, max_length: int, overlap: int = CHUNK_OVERLAP) -> list[tuple[int, int]]:
    """Разбить текст на чанки по ~max_length токенов, вернуть (start, end) по символам.

    Токенизируем весь текст один раз и режем по границам токенов, откатываясь
    до границы слова, чтобы не разрывать сущности. Соседние чанки перекрываются
    на overlap токенов, чтобы сущность на границе не терялась.
    """
    tokenizer = get_model(max_length=SINGLE_MAX_LENGTH).data_processor.transformer_tokenizer
    enc = tokenizer(text, add_special_tokens=False, return_offsets_mapping=True)
    offsets = enc["offset_mapping"]
    n = len(text)
    chunks: list[tuple[int, int]] = []
    i = 0
    total = len(offsets)
    while i < total:
        chunk_start_i = i
        start = offsets[i][0]
        j = min(i + max_length, total) - 1
        end = offsets[j][1]
        # Откатываемся до границы слова, чтобы не резать сущность.
        while end > start and end < n and text[end] not in " \n\t.,;:!?()":
            end -= 1
        if end <= start:
            end = offsets[j][1]
        chunks.append((start, end))
        # Следующий чанк начинается с токена, покрывающего end, но с откатом
        # на overlap токенов, чтобы перекрыть границу. Откат не должен вернуть
        # i к началу текущего чанка (иначе зацикливание) и не должен удерживать
        # i на total после обработки последнего чанка.
        while i < total and offsets[i][1] <= end:
            i += 1
        if i >= total:
            break
        i = max(i - overlap, chunk_start_i + 1)
    return chunks


def extract_entities_long(
    text: str,
    labels: list[str] | None = None,
    threshold: float = 0.3,
    model_dir: str = MODEL_DIR,
    max_length: int = MAX_LENGTH,
    batch_size: int = BATCH_SIZE,
    single_max_length: int = SINGLE_MAX_LENGTH,
) -> list[dict]:
    """Найти сущности в длинном тексте (до ~100k токенов).

    Если текст не длиннее single_max_length токенов — обрабатывается одним
    прогоном (быстро). Иначе режется на чанки по max_length токенов, которые
    обрабатываются батчами по batch_size штук. Результаты склеиваются со
    смещением позиций.
    """
    tokenizer = get_model(model_dir, single_max_length).data_processor.transformer_tokenizer
    n_tokens = len(tokenizer.encode(text, add_special_tokens=False))
    if n_tokens <= single_max_length:
        return extract_entities(text, labels, threshold, model_dir, single_max_length)

    model = get_model(model_dir, single_max_length)
    labels = labels or LABELS
    chunks = _chunk_offsets(text, max_length)
    all_entities: list[dict] = []

    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i + batch_size]
        batch_texts = [text[s:e] for s, e in batch]
        results = model.inference(batch_texts, labels, threshold=threshold, batch_size=batch_size)
        for (start, _end), ents in zip(batch, results):
            for ent in ents:
                ent = dict(ent)
                ent["start"] += start
                ent["end"] += start
                all_entities.append(ent)
    return _dedupe_entities(all_entities)


def _dedupe_entities(entities: list[dict]) -> list[dict]:
    """Убрать дубликаты из перекрывающихся чанков.

    Одна и та же сущность может быть найдена в двух соседних чанках (в зоне
    перекрытия). Оставляем экземпляр с наибольшим score. Сущности считаются
    дубликатами, если совпадает label и их интервалы сильно перекрываются.
    """
    best: dict[tuple, dict] = {}
    for ent in entities:
        key = (ent["label"], ent["start"], ent["end"])
        if key in best:
            if ent["score"] > best[key]["score"]:
                best[key] = ent
            continue
        # Ищем пересекающийся дубликат с тем же label.
        dup = None
        for k, e in best.items():
            if e["label"] != ent["label"]:
                continue
            s = max(e["start"], ent["start"])
            e_ = min(e["end"], ent["end"])
            if s < e_:
                dup = (k, e)
                break
        if dup is None:
            best[key] = ent
        elif ent["score"] > dup[1]["score"]:
            del best[dup[0]]
            best[key] = ent
    return list(best.values())
