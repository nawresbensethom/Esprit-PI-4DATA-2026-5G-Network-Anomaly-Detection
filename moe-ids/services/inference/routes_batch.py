"""
POST /predict/batch — accepts a CSV file, returns predictions for every row.
POST /admin/reload  — hot-reloads the model without a restart.

Lives in the inference service because that's where the model is resident.
"""
from __future__ import annotations

import io
import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException, Request, UploadFile, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from moe_ids.config import settings
from moe_ids.gate import EXPERT_NAMES
from moe_ids.schemas import SchemaError, detect_schema
from services.common.auth import AuthDep
from services.common.db import log_prediction
from services.common.metrics import (
    ATTACK_PREDICTIONS,
    ATTACK_RATE_GAUGE,
    MODEL_RELOAD_COUNT,
    REQUEST_COUNT,
    REQUEST_LATENCY,
    ROWS_PROCESSED,
)
from services.common.predictor import PredictorDep, reload_predictor


class BatchSummary(BaseModel):
    n_attack_predicted: int
    n_benign_predicted: int
    mean_probability: float
    attack_rate: float


class BatchPredictionResponse(BaseModel):
    request_id: str
    model_version: str
    schema: str
    n_rows: int
    predictions: list[int]
    probabilities: list[float]
    gate_weights: list[list[float]]
    expert_order: list[str]
    summary: BatchSummary


router = APIRouter(tags=["inference"])

_MAX_BYTES = settings.max_batch_file_mb * 1024 * 1024


def _ensure_log_dir() -> Path:
    log_dir = Path(settings.log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def _append_prediction_log(record: dict) -> None:
    try:
        log_dir = _ensure_log_dir()
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        log_file = log_dir / f"predictions_{today}.jsonl"
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
    except Exception:
        pass


@router.post("/predict/batch", response_model=BatchPredictionResponse)
async def predict_batch(
    request: Request,
    file: UploadFile,
    predictor: PredictorDep,
    _auth: AuthDep,
) -> JSONResponse:
    request_id = str(uuid.uuid4())
    _t0 = time.perf_counter()

    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > _MAX_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds {settings.max_batch_file_mb} MB limit.",
        )

    raw = await file.read()
    if len(raw) > _MAX_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds {settings.max_batch_file_mb} MB limit.",
        )

    try:
        df = pd.read_csv(io.BytesIO(raw))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not parse CSV: {exc}",
        )

    if df.empty:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CSV is empty.",
        )

    schema = detect_schema(df)
    if schema == "unknown":
        detected_cols = list(df.columns[:15])
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "unrecognised schema",
                "detected_columns": detected_cols,
                "hint": "Expected Argus (5G) or CICFlowMeter (6G) column names.",
            },
        )

    try:
        result = predictor.predict(df)
    except SchemaError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Prediction error: {exc}",
        )

    n_attack = int(result.predictions.sum())
    attack_rate = float(n_attack / len(result.predictions))
    summary = {
        "n_attack_predicted": n_attack,
        "n_benign_predicted": len(result.predictions) - n_attack,
        "mean_probability": float(np.mean(result.probabilities)),
        "attack_rate": attack_rate,
    }

    REQUEST_COUNT.labels(schema=schema, status="ok").inc()
    REQUEST_LATENCY.labels(schema=schema).observe(time.perf_counter() - _t0)
    ROWS_PROCESSED.labels(schema=schema).inc(len(result.predictions))
    ATTACK_PREDICTIONS.labels(schema=schema).inc(n_attack)
    ATTACK_RATE_GAUGE.labels(schema=schema).set(attack_rate)

    response_body = {
        "request_id": request_id,
        "model_version": result.model_version,
        "schema": schema,
        "n_rows": len(df),
        "predictions": result.predictions.tolist(),
        "probabilities": [round(float(p), 6) for p in result.probabilities],
        "gate_weights": result.gate_weights.tolist(),
        "expert_order": EXPERT_NAMES,
        "summary": summary,
    }

    _append_prediction_log(
        {
            "request_id": request_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "model_version": result.model_version,
            "schema": schema,
            "n_rows": len(df),
            "summary": summary,
        }
    )
    log_prediction(
        settings.monitoring_db_url or None,
        {
            "request_id": request_id,
            "model_version": result.model_version,
            "schema": schema,
            "n_rows": len(df),
            "n_attack": n_attack,
            "n_benign": len(result.predictions) - n_attack,
            "mean_probability": float(np.mean(result.probabilities)),
            "attack_rate": attack_rate,
        },
    )

    return JSONResponse(content=response_body)


@router.post("/admin/reload", status_code=status.HTTP_204_NO_CONTENT)
def admin_reload(_auth: AuthDep) -> None:
    """Hot-reload the model from disk. Called by the gateway after training."""
    try:
        reload_predictor()
        MODEL_RELOAD_COUNT.inc()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Reload failed: {exc}",
        )
