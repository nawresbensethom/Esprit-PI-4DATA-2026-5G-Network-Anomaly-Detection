"""FastAPI app — MoE IDS inference microservice (port 8000)."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from moe_ids.config import settings
from moe_ids.logging import configure_logging
from services.common.predictor import load_predictor_at_startup
from services.inference.routes_batch import router as batch_router
from services.inference.routes_health import router as health_router
from services.inference.routes_metrics import router as metrics_router
from services.inference.routes_realtime import router as realtime_router


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[type-arg]
    configure_logging()
    load_predictor_at_startup()
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="MoE IDS — Inference Service",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.webapp_origin],
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    app.include_router(health_router)
    app.include_router(batch_router)
    app.include_router(realtime_router)
    app.include_router(metrics_router)

    return app


app = create_app()
