from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import Response

from moe_ids import __version__
from services.common.metrics import prometheus_response

router = APIRouter(tags=["health"])


@router.get("/healthz")
def liveness() -> dict:
    return {"status": "ok", "service": "training"}


@router.get("/version")
def version() -> dict:
    return {"api_version": __version__, "service": "training"}


@router.get("/metrics", include_in_schema=False)
def metrics() -> Response:
    return Response(content=prometheus_response(), media_type="text/plain; version=0.0.4")
