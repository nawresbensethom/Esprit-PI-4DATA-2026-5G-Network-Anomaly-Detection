"""
GET /model/metrics — fetches the most recent run's metrics from MLflow.

Used by the dashboard front to show the live model accuracy / F1 / AUC card.
Hits MLflow's REST API directly (no SDK dep). Falls back to baseline_stats.json
on the artefacts volume if MLflow is unreachable.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import httpx
from fastapi import APIRouter

from moe_ids.config import settings

router = APIRouter(tags=["model"])

MLFLOW_URL = os.environ.get("MLFLOW_TRACKING_URI", "http://mlflow:5000")
EXPERIMENT_NAME = os.environ.get("MLFLOW_EXPERIMENT_NAME", "unified_moe")
TIMEOUT = 5.0


def _baseline_fallback() -> dict:
    baseline_path = Path(settings.artefacts_dir) / "baseline_stats.json"
    if not baseline_path.exists():
        baseline_path = Path(settings.artefacts_dir) / "production" / "baseline_stats.json"
    if not baseline_path.exists():
        return {"source": "none", "available": False}
    try:
        with open(baseline_path) as f:
            data = json.load(f)
        return {
            "source": "baseline_stats.json",
            "available": True,
            "f1": data.get("moe_f1"),
            "recall": data.get("moe_recall"),
            "pr_auc": data.get("moe_pr_auc"),
            "accuracy": data.get("moe_accuracy"),
            "version": data.get("version"),
        }
    except Exception as exc:
        return {"source": "baseline_stats.json", "available": False, "error": str(exc)}


@router.get("/model/metrics")
async def model_metrics() -> dict:
    """Return the latest training metrics from MLflow, or the baseline fallback."""
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            exp_resp = await client.get(
                f"{MLFLOW_URL}/api/2.0/mlflow/experiments/get-by-name",
                params={"experiment_name": EXPERIMENT_NAME},
            )
            if exp_resp.status_code != 200:
                return {"source": "mlflow_unreachable", "available": False, **_baseline_fallback()}
            exp_id = exp_resp.json()["experiment"]["experiment_id"]

            search = await client.post(
                f"{MLFLOW_URL}/api/2.0/mlflow/runs/search",
                json={
                    "experiment_ids": [exp_id],
                    "max_results": 1,
                    "order_by": ["attributes.start_time DESC"],
                },
            )
            if search.status_code != 200:
                return {
                    "source": "mlflow_search_failed",
                    "available": False,
                    **_baseline_fallback(),
                }
            runs = search.json().get("runs", [])
            if not runs:
                return {"source": "mlflow_no_runs", "available": False, **_baseline_fallback()}

            run = runs[0]
            metrics = {m["key"]: m["value"] for m in run.get("data", {}).get("metrics", [])}
            tags = {t["key"]: t["value"] for t in run.get("data", {}).get("tags", [])}
            info = run.get("info", {})
            return {
                "source": "mlflow",
                "available": True,
                "run_id": info.get("run_id"),
                "run_name": tags.get("mlflow.runName"),
                "experiment": EXPERIMENT_NAME,
                "end_time_ms": info.get("end_time"),
                "status": info.get("status"),
                "accuracy": metrics.get("moe_accuracy"),
                "f1": metrics.get("moe_f1"),
                "recall": metrics.get("moe_recall"),
                "pr_auc": metrics.get("moe_pr_auc"),
                "auc_roc": metrics.get("moe_auc_roc"),
            }
    except Exception as exc:
        return {
            "source": "exception",
            "available": False,
            "error": str(exc),
            **_baseline_fallback(),
        }
