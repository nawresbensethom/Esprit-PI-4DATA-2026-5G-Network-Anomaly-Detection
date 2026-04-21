"""
POST /admin/train — triggers a training run and logs to MLflow.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from pydantic import BaseModel

from moe_ids.config import settings
from services.api.dependencies import AuthDep, reload_predictor

router = APIRouter(tags=["admin"])

ROOT = Path(__file__).parent.parent.parent


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


class TrainResponse(BaseModel):
    status: str
    message: str


_training_status: dict = {"running": False, "last_result": None}


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

        import os
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(ROOT),
            env={**os.environ, "PYTHONUTF8": "1"},
        )
        if result.returncode == 0:
            _training_status["last_result"] = {"success": True, "output": result.stdout[-3000:]}
            try:
                reload_predictor()
            except Exception:
                pass
        else:
            _training_status["last_result"] = {"success": False, "error": result.stderr[-3000:]}
    finally:
        _training_status["running"] = False


@router.post("/admin/train", response_model=TrainResponse, status_code=status.HTTP_202_ACCEPTED)
def trigger_training(
    req: TrainRequest,
    background_tasks: BackgroundTasks,
    _auth: AuthDep,
) -> TrainResponse:
    """Trigger a training run in the background. Logs to MLflow if no_mlflow=false."""
    if _training_status["running"]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A training run is already in progress.",
        )
    # Guard against Swagger's "string" placeholder being submitted unchanged
    for field_name, value in [("data_5g", req.data_5g), ("data_6g", req.data_6g), ("artefacts_dir", req.artefacts_dir)]:
        if value.strip() in ("", "string"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid {field_name!r}: {value!r}. Provide a real path (defaults are /app/data/*.csv).",
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
    """Check whether training is running and the result of the last run."""
    return {
        "running": _training_status["running"],
        "last_result": _training_status["last_result"],
    }