"""FastAPI app — MoE IDS monitoring / drift microservice (port 8011)."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from moe_ids.config import settings
from moe_ids.logging import configure_logging
from services.monitoring.routes_drift import router as drift_router
from services.monitoring.routes_health import router as health_router


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(
        title="MoE IDS — Monitoring Service",
        version="0.1.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.webapp_origin],
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    app.include_router(health_router)
    app.include_router(drift_router)

    return app


app = create_app()
