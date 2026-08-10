import logging

from fastapi import FastAPI

from app.api.routes.auth import router as auth_router
from app.api.routes.chat import router as chat_router
from app.api.routes.health import router as health_router
from app.core.config import get_settings
from app.core.exception_handlers import app_exception_handler, unhandled_exception_handler
from app.core.exceptions import AppException
from app.middleware.request_logging import request_logging_middleware

settings = get_settings()


def create_app() -> FastAPI:
    """Application factory."""

    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Production-grade AI API powered by FastAPI and DeepSeek.",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.middleware("http")(request_logging_middleware)

    app.add_exception_handler(
        AppException,
        app_exception_handler,
    )
    app.add_exception_handler(
        Exception,
        unhandled_exception_handler,
    )

    @app.get("/")
    def root():
        return {
            "service": "ai-demo-api",
            "version": "0.1.0",
            "status": "running",
        }

    app.include_router(health_router)
    app.include_router(chat_router)
    app.include_router(auth_router)

    return app


app = create_app()
