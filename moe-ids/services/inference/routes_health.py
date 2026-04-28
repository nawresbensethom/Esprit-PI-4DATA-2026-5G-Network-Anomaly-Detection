from __future__ import annotations

import subprocess

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import Response

from moe_ids import __version__
from services.common.metrics import prometheus_response
from services.common.predictor import get_predictor

router = APIRouter(tags=["health"])


@router.get("/healthz")
def liveness() -> dict:
    return {"status": "ok", "service": "inference"}


@router.get("/readyz")
def readiness() -> dict:
    try:
        predictor = get_predictor()
    except HTTPException:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Model not loaded.",
        )

    import pandas as pd

    try:
        from moe_ids.schemas import ARGUS_SIGNATURE_COLUMNS

        argus_dummy = pd.DataFrame(columns=ARGUS_SIGNATURE_COLUMNS)
        argus_dummy.loc[0] = 0.0
        predictor.predict(argus_dummy)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Warmup prediction failed: {e}",
        )

    return {"status": "ready", "model_version": predictor._a.version}


@router.get("/version")
def version() -> dict:
    try:
        predictor = get_predictor()
        model_version = predictor._a.version
        manifest = predictor._a.manifest
    except HTTPException:
        model_version = "not_loaded"
        manifest = {}

    try:
        git_commit = (
            subprocess.check_output(
                ["git", "rev-parse", "--short", "HEAD"], stderr=subprocess.DEVNULL
            )
            .decode()
            .strip()
        )
    except Exception:
        git_commit = "unknown"

    return {
        "api_version": __version__,
        "service": "inference",
        "model_version": model_version,
        "git_commit": git_commit,
        "manifest_seed": manifest.get("seed"),
    }


@router.get("/metrics", include_in_schema=False)
def metrics() -> Response:
    return Response(content=prometheus_response(), media_type="text/plain; version=0.0.4")
