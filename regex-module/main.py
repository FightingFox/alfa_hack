"""FastAPI-приложение: WebSocket-эндпоинт для определения персональных данных.

Принимает строку текста по WebSocket и возвращает результат scan() из scan.py.
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from scan import scan

app = FastAPI(
    title="PII Scanner", description="Определение персональных данных в тексте"
)


@app.websocket("/scan")
async def scan_endpoint(websocket: WebSocket) -> None:
    """Принимает текст по WebSocket и возвращает список найденных персональных данных."""
    await websocket.accept()
    try:
        while True:
            text = await websocket.receive_text()
            await websocket.send_json(scan(text))
    except WebSocketDisconnect:
        return
