"""
POST /drift     — run a drift check now, return the report + persist it
GET  /drift/last — return the most recent drift report (in-process cache)

Wraps the standalone `scripts/detect_drift.py` CLI as an HTTP service.
On drift detection, posts an alert to SLACK_WEBHOOK_URL if configured.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import httpx
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from moe_ids.config import settings
from scripts.detect_drift import run_drift_check
from services.common.auth import AuthDep
from services.common.metrics import DRIFT_CHECKS, LAST_DRIFT_PSI

SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "")


def _post_drift_alert(report: dict) -> None:
    if not SLACK_WEBHOOK_URL or report.get("status") != "drift_detected":
        return
    payload = {
        "attachments": [
            {
                "color": "warning",
                "title": ":warning: MoE IDS — Drift detected",
                "fields": [
                    {
                        "title": "PSI (attack rate)",
                        "value": f"{report.get('psi_attack_rate', '?')}",
                        "short": True,
                    },
                    {
                        "title": "Threshold",
                        "value": f"{report.get('psi_threshold', '?')}",
                        "short": True,
                    },
                    {
                        "title": "Recent attack rate",
                        "value": f"{report.get('recent_mean_attack_rate', '?')}",
                        "short": True,
                    },
                    {
                        "title": "Baseline",
                        "value": f"{report.get('baseline_attack_rate', '?')}",
                        "short": True,
                    },
                    {
                        "title": "Window",
                        "value": f"{report.get('window_days', '?')} days",
                        "short": True,
                    },
                    {
                        "title": "Requests",
                        "value": f"{report.get('n_requests', '?')}",
                        "short": True,
                    },
                ],
                "footer": "moe-monitoring-svc",
            }
        ]
    }
    try:
        with httpx.Client(timeout=5.0) as client:
            client.post(SLACK_WEBHOOK_URL, content=json.dumps(payload))
    except Exception:
        pass

router = APIRouter(tags=["monitoring"])


class DriftRequest(BaseModel):
    window_days: int = 7
    psi_threshold: float = 0.2
    ks_p_threshold: float = 0.05


_last_report: dict | None = None


@router.post("/drift")
def run_drift(req: DriftRequest, _auth: AuthDep) -> dict:
    global _last_report
    artefacts_dir = Path(settings.artefacts_dir) / "production"
    log_dir = Path(settings.log_dir)

    if not artefacts_dir.exists():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Artefacts directory not found: {artefacts_dir}",
        )

    try:
        report = run_drift_check(
            artefacts_dir=artefacts_dir,
            log_dir=log_dir,
            window_days=req.window_days,
            psi_threshold=req.psi_threshold,
            ks_p_threshold=req.ks_p_threshold,
        )
    except SystemExit as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Drift check aborted: {exc}",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Drift check failed: {exc}",
        )

    _last_report = report
    DRIFT_CHECKS.labels(result=report.get("status", "unknown")).inc()
    psi = report.get("psi_attack_rate")
    if isinstance(psi, (int, float)):
        LAST_DRIFT_PSI.set(float(psi))
    _post_drift_alert(report)
    return report


@router.get("/drift/last")
def last_drift_report() -> dict:
    if _last_report is None:
        return {"status": "no_run_yet"}
    return _last_report
