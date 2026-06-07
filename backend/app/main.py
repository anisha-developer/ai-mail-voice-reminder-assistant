from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import api_router
from app.config import settings
from app.core.scheduler import start_scheduler, stop_scheduler


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name)
    cors_origins = [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router)

    @app.on_event("startup")
    def startup_event() -> None:
        start_scheduler()

    @app.on_event("shutdown")
    def shutdown_event() -> None:
        stop_scheduler()

    return app


app = create_app()
