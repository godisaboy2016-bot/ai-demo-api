import logging

from fastapi import FastAPI

from app.api.routes.health import router as health_router
from app.core.config import get_settings

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
        description="Production-grade FastAPI demo API.",
    )


    @app.get("/")
    def root():
        return {
           "service": "ai-demo-api",
           "version": "0.1.0",
           "status": "running"
        }


    @app.get("/health")
    def health():
        return {
           "status": "ok",
           "service": "ai-demo-api",
           "version": "0.1.0",
           "environment": "production"
        }
    app.include_router(health_router)
    return app


app = create_app()
