"""
POST /admin/train        — triggers a training run (subprocess + MLflow)
GET  /admin/train/status — polls the running run

On success, the training service calls the inference service's /admin/reload
over HTTP so the fresh artefacts go live without a restart.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import httpx
from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from pydantic import BaseModel

from services.common.auth import AuthDep
from services.common.metrics import TRAINING_RUNS

router = APIRouter(tags=["admin"])

ROOT = Path(__file__).parent.parent.parent

INFERENCE_BASE_URL = os.environ.get("INFERENCE_BASE_URL", "http://moe-inference-svc:8000")
INTERNAL_API_KEY = os.environ.get("API_KEY", "changeme")


class TrainRequest(BaseModel):
    data_5g: str = "/app/data/Global_CLEANED.csv"
    data_6g: str = "/app/data/AIoT_6G_CLEANED.csv"
    artefacts_dir: str = "/app/artefacts/production"
    seed: int = 42
    ae_epochs: int = 10
    gate_epochs: int = 10
    xgb_n_estimators: int = 100
    mlflow_tracking_uri: str = "http://mlflow:5000"
    experiment: str = "unified_moe"
    no_mlflow: bool = False
    reload_inference: bool = True


class TrainResponse(BaseModel):
    status: str
    message: str


_training_status: dict = {"running": False, "last_result": None}


def _reload_inference_service() -> dict:
    url = f"{INFERENCE_BASE_URL}/admin/reload"
    headers = {"X-Api-Key": INTERNAL_API_KEY}
    try:
        with httpx.Client(timeout=30) as client:
            resp = client.post(url, headers=headers)
            return {"status_code": resp.status_code, "ok": resp.is_success}
    except Exception as exc:
        return {"status_code": None, "ok": False, "error": str(exc)}


def _run_training(req: TrainRequest) -> None:
    global _training_status
    _training_status["running"] = True
    try:
        cmd = [
            sys.executable,
            str(ROOT / "scripts" / "train.py"),
            "--data-5g", req.data_5g,
            "--data-6g", req.data_6g,
            "--artefacts-dir", req.artefacts_dir,
            "--seed", str(req.seed),
            "--ae-epochs", str(req.ae_epochs),
            "--gate-epochs", str(req.gate_epochs),
            "--xgb-n-estimators", str(req.xgb_n_estimators),
            "--mlflow-tracking-uri", req.mlflow_tracking_uri,
            "--experiment", req.experiment,
        ]
        if req.no_mlflow:
            cmd.append("--no-mlflow")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(ROOT),
            env={**os.environ, "PYTHONUTF8": "1"},
        )
        if result.returncode == 0:
            last: dict = {"success": True, "output": result.stdout[-3000:]}
            if req.reload_inference:
                last["reload_inference"] = _reload_inference_service()
            _training_status["last_result"] = last
            TRAINING_RUNS.labels(status="success").inc()
        else:
            _training_status["last_result"] = {
                "success": False,
                "error": result.stderr[-3000:],
            }
            TRAINING_RUNS.labels(status="failure").inc()
    finally:
        _training_status["running"] = False


@router.post("/admin/train", response_model=TrainResponse, status_code=status.HTTP_202_ACCEPTED)
def trigger_training(
    req: TrainRequest,
    background_tasks: BackgroundTasks,
    _auth: AuthDep,
) -> TrainResponse:
    if _training_status["running"]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A training run is already in progress.",
        )
    for field_name, value in [
        ("data_5g", req.data_5g),
        ("data_6g", req.data_6g),
        ("artefacts_dir", req.artefacts_dir),
    ]:
        if value.strip() in ("", "string"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid {field_name!r}: {value!r}. Provide a real path.",
            )
    if not Path(req.data_5g).is_file():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"data_5g not found in container: {req.data_5g}",
        )
    if not Path(req.data_6g).is_file():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"data_6g not found in container: {req.data_6g}",
        )
    background_tasks.add_task(_run_training, req)
    return TrainResponse(
        status="accepted",
        message="Training started in background. Check /admin/train/status for progress.",
    )


@router.get("/admin/train/status")
def training_status() -> dict:
    return {
        "running": _training_status["running"],
        "last_result": _training_status["last_result"],
    }
