import asyncio

import websockets

from app.config import WebSocketPoolConfig
from app.ws_pool import WebSocketPool


async def _echo_server(ws):
    async for message in ws:
        await ws.send(message)


async def _serve():
    server = await websockets.serve(_echo_server, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    return server, f"ws://127.0.0.1:{port}"


def test_pool_reuses_connections() -> None:
    async def run() -> None:
        server, url = await _serve()
        try:
            pool = WebSocketPool(url, WebSocketPoolConfig(min_connections=1, max_connections=4))
            await pool.start()
            try:
                async with pool.connection() as ws1:
                    await ws1.send("hello")
                    assert await ws1.recv() == "hello"
                async with pool.connection() as ws2:
                    await ws2.send("world")
                    assert await ws2.recv() == "world"
                # Оба запроса должны переиспользовать одно и то же соединение.
                assert pool.total == 1
                assert pool.idle_count == 1
            finally:
                await pool.close()
        finally:
            server.close()
            await server.wait_closed()

    asyncio.run(run())


def test_pool_grows_under_concurrency() -> None:
    async def run() -> None:
        server, url = await _serve()
        try:
            pool = WebSocketPool(url, WebSocketPoolConfig(min_connections=1, max_connections=8))
            await pool.start()
            try:
                async def worker(i: int) -> str:
                    async with pool.connection() as ws:
                        await ws.send(str(i))
                        return await ws.recv()

                results = await asyncio.gather(*(worker(i) for i in range(8)))
                assert results == [str(i) for i in range(8)]
                # Под нагрузкой пул расширился до нескольких соединений.
                assert pool.total > 1
            finally:
                await pool.close()
        finally:
            server.close()
            await server.wait_closed()

    asyncio.run(run())


def test_pool_shrinks_when_idle() -> None:
    async def run() -> None:
        server, url = await _serve()
        try:
            pool = WebSocketPool(
                url,
                WebSocketPoolConfig(
                    min_connections=1,
                    max_connections=8,
                    idle_shrink_interval=0.05,
                    idle_shrink_ratio=0.5,
                ),
            )
            await pool.start()
            try:
                async def worker(i: int) -> str:
                    async with pool.connection() as ws:
                        await ws.send(str(i))
                        return await ws.recv()

                await asyncio.gather(*(worker(i) for i in range(8)))
                grown = pool.total
                assert grown > 1
                # Ждём цикл сжатия — пул должен вернуться к min_connections.
                await asyncio.sleep(0.2)
                assert pool.total == 1
            finally:
                await pool.close()
        finally:
            server.close()
            await server.wait_closed()

    asyncio.run(run())


def test_pool_start_retries_when_backend_unavailable() -> None:
    async def run() -> None:
        # Выбираем свободный порт, но не поднимаем сервер сразу.
        probe = await asyncio.start_server(lambda r, w: None, "127.0.0.1", 0)
        port = probe.sockets[0].getsockname()[1]
        probe.close()
        await probe.wait_closed()

        url = f"ws://127.0.0.1:{port}"
        pool = WebSocketPool(
            url,
            WebSocketPoolConfig(
                min_connections=1,
                max_connections=4,
                connect_retry_delay=0.01,
                connect_retry_max_delay=0.05,
            ),
        )
        start_task = asyncio.create_task(pool.start())
        # Даём пулу время провалить первую попытку и начать ретраить.
        await asyncio.sleep(0.05)
        assert pool.total == 0

        # Поднимаем сервер на том же порту — пул должен донабрать min_connections.
        server = await websockets.serve(_echo_server, "127.0.0.1", port)
        try:
            await asyncio.wait_for(start_task, timeout=2.0)
            assert pool.total == 1
            assert pool.idle_count == 1
        finally:
            server.close()
            await server.wait_closed()
        await pool.close()

    asyncio.run(run())


def test_pool_respects_max_connections() -> None:
    async def run() -> None:
        server, url = await _serve()
        try:
            pool = WebSocketPool(url, WebSocketPoolConfig(min_connections=1, max_connections=3))
            await pool.start()
            try:
                async def worker(i: int) -> str:
                    async with pool.connection() as ws:
                        await ws.send(str(i))
                        return await ws.recv()

                await asyncio.gather(*(worker(i) for i in range(10)))
                assert pool.total <= 3
            finally:
                await pool.close()
        finally:
            server.close()
            await server.wait_closed()

    asyncio.run(run())
