import json
from dataclasses import dataclass

import redis

from app.config import get_settings


@dataclass
class Record:
    original: str
    masked: dict[str, dict[str, list[dict] | float | None]]
    masked_text: str | None = None
    replacements: list[dict] | None = None


class CorrelationStore:
    """Хранит соответствие payload_id -> (исходная, замаскированная) строка в Redis."""

    def __init__(self, redis_url: str, ttl: int = 3600) -> None:
        self._redis = redis.Redis.from_url(redis_url, decode_responses=True)
        self._ttl = ttl

    def get(self, payload_id: str) -> Record | None:
        raw = self._redis.get(f"pd:{payload_id}")
        if raw is None:
            return None
        data = json.loads(raw)
        return Record(
            original=data["original"],
            masked=data["masked"],
            masked_text=data.get("masked_text"),
            replacements=data.get("replacements"),
        )

    def put(self, payload_id: str, record: Record) -> None:
        raw = json.dumps(
            {
                "original": record.original,
                "masked": record.masked,
                "masked_text": record.masked_text,
                "replacements": record.replacements,
            }
        )
        self._redis.set(f"pd:{payload_id}", raw, ex=self._ttl)


_store: CorrelationStore | None = None


def get_store() -> CorrelationStore:
    global _store
    if _store is None:
        settings = get_settings()
        _store = CorrelationStore(redis_url=settings.redis_url)
    return _store
