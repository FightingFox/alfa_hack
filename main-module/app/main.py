from fastapi import FastAPI

from app.config import get_settings
from app.routers import health, process


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        debug=settings.debug,
    )

    app.include_router(health.router)
    app.include_router(process.router)

    return app


app = create_app()
