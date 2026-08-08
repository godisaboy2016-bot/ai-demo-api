import logging

from fastapi import FastAPI

from app.api.routes.chat import router as chat_router
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
       description="""
    # AI Demo API

    Production-grade AI API powered by FastAPI and DeepSeek.

    ## Features

    - Chat completion API
    - Async DeepSeek integration
    - Docker deployment
    - Automated testing

    ## Environment

    - Python 3.12
    - FastAPI
    - Docker
    """,
       docs_url="/docs",
       redoc_url="/redoc",
       openapi_tags=[
           {
               "name": "health",
               "description": "Service health check endpoints",
           },
           {
               "name": "chat",
               "description": "AI conversation endpoints",
           },
       ],
    )


    @app.get("/")
    def root():
        return {
           "service": "ai-demo-api",
           "version": "0.1.0",
           "status": "running"
        }


    app.include_router(health_router)
    app.include_router(chat_router)
    return app


app = create_app()
