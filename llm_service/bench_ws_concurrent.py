"""Конкурентный замер WS llm_service: 5 запросов отправляются сразу."""

import asyncio
import json
import time

import websockets

URL = "ws://127.0.0.1:8003/ws"

TEXTS = [
    "Меня зовут Иван Петров, мой паспорт 4509 123456 выдан 12.03.2015, "
    "телефон +7 912 345-67-89, email ivan.petrov@mail.ru.",
    "Компания ООО Ромашка, ИНН 7701234567, адрес: г. Москва, ул. Ленина, д. 5.",
    "Клиент Анна Смирнова, СНИЛС 123-456-789 01, карта 4276 1234 5678 9012, "
    "срок действия 12/27.",
    "Документ: паспорт 4510 987654, выдан ОВД района Хамовники, код подразделения "
    "770-123, дата рождения 05.06.1990.",
    "Президент Владимир Путин посетил завод компании Газпром в Санкт-Петербурге, "
    "адрес: Невский проспект, д. 28.",
]


async def main() -> None:
    async with websockets.connect(URL) as ws:
        start_all = time.perf_counter()
        # Отправляем все 5 запросов сразу
        for text in TEXTS:
            await ws.send(text)

        # Собираем 5 ответов
        results = []
        for i in range(len(TEXTS)):
            resp = json.loads(await ws.recv())
            results.append(resp)
            ok = resp.get("ok")
            wt = resp.get("work_time")
            count = resp.get("count")
            print(f"[{i + 1}] ok={ok} work_time={wt} count={count}")

        total = time.perf_counter() - start_all
        print(f"\nВсего 5 запросов: {total:.3f}s (в среднем {total / len(TEXTS):.3f}s/запрос)")


if __name__ == "__main__":
    asyncio.run(main())