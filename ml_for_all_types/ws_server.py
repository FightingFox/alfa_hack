"""FastAPI WebSocket-обвязка для ансамбля ML-детекторов ПД.

Принимает текст по WebSocket и возвращает найденные типы ПД (ансамбль
лёгковесных моделей из ml_for_all_types). Формат ответа полностью совпадает
с gliner_famous/ws_server.py и llm_service/ws_server.py: сущности с полями
text, type, score, slice, will_be_used.

Модели загружаются при старте (лениво, через ensemble.load_all).
"""

import asyncio
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

import ensemble

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ws_server_ml")


class ProcessRequest(BaseModel):
    text: str = Field(..., description="Текст для детекции типов ПД")


class Entity(BaseModel):
    text: str = Field(..., description="Фрагмент текста, где найден тип ПД")
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


def process_text(text: str, threshold: float = ensemble.DEFAULT_THRESHOLD) -> ProcessResponse:
    """Прогнать текст через ансамбль и вернуть сущности в формате gliner_famous."""
    start = time.perf_counter()
    detected = ensemble.detect_spans_with_positions(text, threshold=threshold)
    elapsed = time.perf_counter() - start
    entities = [
        Entity(
            text=d["text"],
            type=[d["code"]],
            score=round(d["score"], 3),
            slice=d["slice"],
            will_be_used=True,
        )
        for d in detected
    ]
    return ProcessResponse(
        work_time=round(elapsed, 3),
        length=len(text),
        count=len(entities),
        data=entities,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Загрузка моделей ансамбля...")
    await asyncio.to_thread(ensemble.load_all)
    logger.info("Модели готовы: %d типов", len(ensemble.available_types()))
    yield


app = FastAPI(title="ML Ensemble PII Detector", version="1.0.0", lifespan=lifespan)


@app.post("/process", response_model=ProcessResponse)
async def process_endpoint(request: ProcessRequest) -> ProcessResponse:
    """Обработать текст и вернуть найденные типы ПД."""
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

    uvicorn.run(app, host="127.0.0.1", port=8001)