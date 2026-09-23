from dataclasses import dataclass

from app.postprocess import filter_fio_entities

EXPLICIT_PII_TYPES = {
    "FIO",
    "PHONE",
    "EMAIL",
    "SNILS",
    "INN",
    "PASSPORT",
    "CARD_NUMBER",
    "CVV",
    "PIN",
    "ISSUE_CODE",
    "LICENSE",
    "MIGRATION_CARD",
}

SERVICE_PRIORITY = {"regex": 0, "ml": 1, "gliner": 2, "llm": 3}


@dataclass
class Replacement:
    slice: list[int]
    types: list[str]
    mask: str
    original_text: str


@dataclass
class MaskResult:
    masked_text: str
    replacements: list[Replacement]


def _is_explicit(entity: dict) -> bool:
    return bool(set(entity["type"]) & EXPLICIT_PII_TYPES)


def _service_rank(service: str) -> int:
    return SERVICE_PRIORITY.get(service, len(SERVICE_PRIORITY))


def _pick_representative(entities: list[tuple[str, dict]]) -> tuple[str, dict]:
    def key(item: tuple[str, dict]) -> tuple[float, int, int]:
        service, entity = item
        start, end = entity["slice"]
        return entity["score"], -_service_rank(service), end - start

    return max(entities, key=key)


def mask_text(text: str, results: dict[str, dict]) -> MaskResult:
    """Заменяет явные ПДн в тексте на маски вида `{{ TYPE1,TYPE2 N }}`."""
    entities: list[tuple[str, dict]] = []
    for service, entry in results.items():
        result = entry.get("result")
        if result is None:
            continue
        for entity in filter_fio_entities(result):
            if _is_explicit(entity):
                entities.append((service, entity))

    entities.sort(key=lambda item: item[1]["slice"][0])

    clusters: list[list[tuple[str, dict]]] = []
    for item in entities:
        if clusters:
            current_end = max(e[1]["slice"][1] for e in clusters[-1])
            if item[1]["slice"][0] < current_end:
                clusters[-1].append(item)
                continue
        clusters.append([item])

    representatives = [_pick_representative(cluster) for cluster in clusters]
    representatives.sort(key=lambda item: item[1]["slice"][0])

    replacements: list[Replacement] = []
    for idx, (_, entity) in enumerate(representatives, start=1):
        start, end = entity["slice"]
        types = entity["type"]
        mask = "{{ " + ",".join(types) + " " + str(idx) + " }}"
        replacements.append(
            Replacement(
                slice=[start, end],
                types=types,
                mask=mask,
                original_text=text[start:end],
            )
        )

    masked = text
    for rep in reversed(replacements):
        start, end = rep.slice
        masked = masked[:start] + rep.mask + masked[end:]

    return MaskResult(masked_text=masked, replacements=replacements)
