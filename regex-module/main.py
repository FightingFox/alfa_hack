"""FastAPI-приложение: WebSocket-эндпоинт для определения персональных данных.

Принимает строку текста по WebSocket и возвращает результат process_text() из scan.py.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from prometheus_fastapi_instrumentator import Instrumentator

from scan import preload_address_book, process_text


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Загружает справочник адресов (КЛАДР) при старте сервиса."""
    preload_address_book()
    yield


app = FastAPI(
    title="PII Scanner",
    description="Определение персональных данных в тексте",
    lifespan=lifespan,
)

Instrumentator().instrument(app).expose(app, endpoint="/metrics")


@app.websocket("/scan")
async def scan_endpoint(websocket: WebSocket) -> None:
    """Принимает текст по WebSocket и возвращает список найденных персональных данных."""
    await websocket.accept()
    try:
        while True:
            text = await websocket.receive_text()
            await websocket.send_json(process_text(text).model_dump())
    except WebSocketDisconnect:
        return
