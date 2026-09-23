"""FastAPI WebSocket-обвязка для NER-обработки текста.

Принимает текст по WebSocket и возвращает результат в том же формате,
что и ner.py. Модели прогреваются при старте.
"""

import asyncio
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import BaseModel, Field

from model_interfaces.gliner_model import LABELS, extract_entities_long, warmup
from model_interfaces.pii_types import map_to_pii_types
from model_interfaces.context_fame import is_famous

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ws_server")


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


def process_text(text: str) -> ProcessResponse:
    """Обработать текст и вернуть результат в формате ner.py."""
    start = time.perf_counter()
    entities = extract_entities_long(text, LABELS, threshold=0.3)
    entities = map_to_pii_types(entities)

    result: list[Entity] = []
    for e in entities:
        codes = list(e["pii_codes"])
        famous = False
        if e["label"] == "person":
            famous = is_famous(text, e["text"], e["start"], e["end"])
            if famous:
                codes = ["FAM_FIO" if c == "FIO" else c for c in codes]
        if not codes:
            continue
        result.append(Entity(
            text=e["text"],
            type=codes,
            score=round(e["score"], 3),
            slice=[e["start"], e["end"]],
            will_be_used=not famous,
        ))

    elapsed = time.perf_counter() - start
    return ProcessResponse(
        work_time=round(elapsed, 3),
        length=len(text),
        count=len(result),
        data=result,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Прогрев моделей...")
    await asyncio.to_thread(warmup)
    logger.info("Модели готовы")
    yield


app = FastAPI(title="NER WebSocket", version="1.0.0", lifespan=lifespan)

Instrumentator().instrument(app).expose(app, endpoint="/metrics")


@app.post("/process", response_model=ProcessResponse)
async def process_endpoint(request: ProcessRequest) -> ProcessResponse:
    """Обработать текст и вернуть результат в формате ner.py."""
    try:
        return await asyncio.to_thread(process_text, request.text)
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
                result = await asyncio.to_thread(process_text, text)
                await websocket.send_json(WsResponse(ok=True, **result.model_dump()).model_dump())
            except Exception as exc:  # noqa: BLE001
                logger.exception("Ошибка обработки")
                await websocket.send_json(WsResponse(ok=False, error=str(exc)).model_dump())
    except WebSocketDisconnect:
        logger.info("Клиент отключился")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)