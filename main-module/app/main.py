from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import get_settings
from app.orchestrator import get_orchestrator
from app.routers import health, process


@asynccontextmanager
async def lifespan(app: FastAPI):
    orchestrator = get_orchestrator()
    await orchestrator.start()
    try:
        yield
    finally:
        await orchestrator.close()


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        debug=settings.debug,
        lifespan=lifespan,
    )

    app.include_router(health.router)
    app.include_router(process.router)

    return app


app = create_app()
