"""LLM-сервис NER с тем же контрактом, что и gliner_famous.

Принимает текст по HTTP (`POST /process`) и WebSocket (`WS /ws`) и возвращает
найденные сущности ПД в том же формате, что и gliner_famous, но вместо локальной
модели GLiNER использует запрос к LLM (провайдер ALFA).

Ориентирован на скорость: один запрос к LLM возвращает все сущности сразу,
включая определение известных персон (FAM_FIO) и позиции в тексте.
"""

import asyncio
import json
import logging
import os
import time
from contextlib import asynccontextmanager

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("llm_service")

LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://alfagen.alfabank.ru/continue-dev/").rstrip("/")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "deepseek-ai/DeepSeek-V4-Flash-0731")
LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "30"))
# Внутренний эндпоинт ALFA использует приватный CA — отключаем проверку SSL,
# если задано LLM_VERIFY_SSL=false (см. .env).
LLM_VERIFY_SSL = os.getenv("LLM_VERIFY_SSL", "true").lower() not in ("false", "0", "no")

# Коды типов ПД, которые может вернуть LLM (совпадают с реестром gliner_famous).
PII_CODES = [
    "PASSPORT", "LICENSE", "CITIZENSHIP", "ISSUING_AUTHORITY", "ISSUE_CODE",
    "DATE", "ADDRESS", "FIO", "FAM_FIO", "EMAIL", "PHONE", "INN",
    "CARD_NUMBER", "CVV", "PIN", "CARDHOLDER", "MILITARY_ID",
    "FOREIGN_PASSPORT", "SNILS", "BIRTH_CERT", "OMS", "DMC",
    "MIGRATION_CARD", "SOCIAL_LOGIN", "IP_ADDRESS", "MAC_ADDRESS",
    "PASSWORD", "PROFESSION", "COMPANY",
]

SYSTEM_PROMPT = """Ты — система распознавания персональных данных (ПД) в русском тексте.
Найди ВСЕ сущности, содержащие персональные данные, и верни их строго в формате JSON.

Допустимые коды типов ПД:
PASSPORT, LICENSE, CITIZENSHIP, ISSUING_AUTHORITY, ISSUE_CODE, DATE, ADDRESS,
FIO, FAM_FIO, EMAIL, PHONE, INN, CARD_NUMBER, CVV, PIN, CARDHOLDER,
MILITARY_ID, FOREIGN_PASSPORT, SNILS, BIRTH_CERT, OMS, DMC, MIGRATION_CARD,
SOCIAL_LOGIN, IP_ADDRESS, MAC_ADDRESS, PASSWORD, PROFESSION, COMPANY.

Правила:
- FIO — ФИО обычного человека (маскируется).
- FAM_FIO — ФИО известной/публичной персоны (не маскируется). Используй FAM_FIO
  только для реально известных личностей (политики, актёры, писатели, спортсмены,
  учёные и т.п.), а не для обычных людей.
- COMPANY — название организации/компании (не маскируется).
- ADDRESS — полный адрес.
- Для каждого найденного фрагмента укажи точные позиции start и end (индексы
  символов в исходном тексте, [start, end)).
- score — уверенность от 0 до 1.
- will_be_used — false для FAM_FIO и COMPANY (не маскируются), true для остальных.

Верни ТОЛЬКО JSON-массив объектов вида:
[{"text": "...", "type": ["FIO"], "score": 0.95, "slice": [start, end], "will_be_used": true}]
Без пояснений и markdown-обёрток."""


class ProcessRequest(BaseModel):
    text: str = Field(..., description="Текст для NER-обработки")


class Entity(BaseModel):
    text: str = Field(..., description="Найденная сущность")
    type: list[str] = Field(..., description="Коды типов ПД")
    score: float = Field(..., description="Уверенность модели")
    slice: list[int] = Field(..., description="[start, end) позиции в тексте")
    will_be_used: bool = Field(..., description="Будет ли сущность использована")


class ProcessResponse(BaseModel):
    work_time: float = Field(..., description="Время обработки, сек")
    length: int = Field(..., description="Длина входного текста")
    count: int = Field(..., description="Количество найденных сущностей")
    data: list[Entity] = Field(..., description="Найденные сущности")


class WsResponse(BaseModel):
    ok: bool = Field(..., description="Успех обработки")
    work_time: float | None = Field(None, description="Время обработки, сек")
    length: int | None = Field(None, description="Длина входного текста")
    count: int | None = Field(None, description="Количество найденных сущностей")
    data: list[Entity] | None = Field(None, description="Найденные сущности")
    error: str | None = Field(None, description="Сообщение об ошибке")


_client: httpx.AsyncClient | None = None


def get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(
            base_url=LLM_BASE_URL,
            headers={"Authorization": f"Bearer {LLM_API_KEY}"},
            timeout=LLM_TIMEOUT,
            verify=LLM_VERIFY_SSL,
        )
    return _client


def _parse_entities(raw: str, text: str) -> list[Entity]:
    """Разобрать JSON-ответ LLM в список сущностей с валидацией."""
    raw = raw.strip()
    # Снять возможные markdown-обёртки ```json ... ```
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    # Взять первый JSON-массив, если LLM добавил текст вокруг.
    start = raw.find("[")
    end = raw.rfind("]")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("LLM не вернул JSON-массив")
    raw = raw[start:end + 1]

    items = json.loads(raw)
    if not isinstance(items, list):
        raise ValueError("Ожидался JSON-массив")

    result: list[Entity] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        ent_text = str(it.get("text", "")).strip()
        if not ent_text:
            continue
        types = it.get("type") or []
        if isinstance(types, str):
            types = [types]
        types = [t for t in types if isinstance(t, str) and t in PII_CODES]
        if not types:
            continue
        sl = it.get("slice") or it.get("start_end") or []
        if len(sl) != 2:
            # Позиции не указаны — ищем фрагмент в тексте.
            pos = text.find(ent_text)
            if pos == -1:
                continue
            sl = [pos, pos + len(ent_text)]
        try:
            s, e = int(sl[0]), int(sl[1])
        except (TypeError, ValueError):
            continue
        s = max(0, min(s, len(text)))
        e = max(s, min(e, len(text)))
        score = float(it.get("score", 0.9))
        score = max(0.0, min(1.0, score))
        will_be_used = bool(it.get("will_be_used", True))
        result.append(Entity(
            text=ent_text,
            type=types,
            score=round(score, 3),
            slice=[s, e],
            will_be_used=will_be_used,
        ))
    return result


async def extract_entities_llm(text: str) -> list[Entity]:
    """Один запрос к LLM возвращает все сущности ПД.

    Эндпоинт ALFA работает только в режиме стриминга (SSE), поэтому читаем
    поток и собираем контент по частям.
    """
    client = get_client()
    payload = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
        "temperature": 0.0,
        "max_tokens": 4096,
        "stream": True,
    }
    content = ""
    async with client.stream("POST", "/chat/completions", json=payload) as resp:
        resp.raise_for_status()
        async for line in resp.aiter_lines():
            if not line or not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            try:
                chunk = json.loads(data)
            except json.JSONDecodeError:
                continue
            delta = chunk.get("choices", [{}])[0].get("delta", {})
            piece = delta.get("content")
            if piece:
                content += piece
    return _parse_entities(content, text)


async def process_text(text: str) -> ProcessResponse:
    """Обработать текст и вернуть результат в формате gliner_famous."""
    start = time.perf_counter()
    entities = await extract_entities_llm(text)
    elapsed = time.perf_counter() - start
    return ProcessResponse(
        work_time=round(elapsed, 3),
        length=len(text),
        count=len(entities),
        data=entities,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("LLM-сервис запущен (модель %s)", LLM_MODEL)
    yield
    if _client is not None:
        await _client.aclose()


app = FastAPI(title="LLM NER Service", version="1.0.0", lifespan=lifespan)


@app.post("/process", response_model=ProcessResponse)
async def process_endpoint(request: ProcessRequest) -> ProcessResponse:
    """Обработать текст и вернуть результат в формате gliner_famous."""
    try:
        return await process_text(request.text)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Ошибка обработки")
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        while True:
            text = await websocket.receive_text()
            try:
                result = await process_text(text)
                await websocket.send_json(WsResponse(ok=True, **result.model_dump()).model_dump())
            except Exception as exc:  # noqa: BLE001
                logger.exception("Ошибка обработки")
                await websocket.send_json(WsResponse(ok=False, error=str(exc)).model_dump())
    except WebSocketDisconnect:
        logger.info("Клиент отключился")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)