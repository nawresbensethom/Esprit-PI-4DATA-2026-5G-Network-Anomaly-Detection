"""
Thin proxy to the moe-ids API. Forwards a CSV upload and returns the
prediction payload as-is. No persistence yet — Phase A smoke test only.
"""
from __future__ import annotations

import os

import httpx
from fastapi import APIRouter, HTTPException, UploadFile

router = APIRouter(prefix="/predict", tags=["predict"])

MLOPS_BASE_URL = os.environ.get("MLOPS_BASE_URL", "http://host.docker.internal:8000")
MLOPS_API_KEY = os.environ.get("MLOPS_API_KEY", "changeme")
TIMEOUT = float(os.environ.get("MLOPS_TIMEOUT", "60"))


@router.post("/batch")
async def predict_batch(file: UploadFile):
    raw = await file.read()
    files = {"file": (file.filename or "upload.csv", raw, "text/csv")}
    headers = {"X-Api-Key": MLOPS_API_KEY}
    url = f"{MLOPS_BASE_URL}/predict/batch"

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            resp = await client.post(url, files=files, headers=headers)
        except httpx.RequestError as exc:
            raise HTTPException(status_code=502, detail=f"moe-ids unreachable: {exc}")

    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=resp.json())
    return resp.json()


@router.get("/health")
async def upstream_health():
    """Confirms the inference-svc can reach the moe-ids API."""
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            resp = await client.get(f"{MLOPS_BASE_URL}/healthz")
            return {"upstream": MLOPS_BASE_URL, "status": resp.status_code, "body": resp.json()}
        except httpx.RequestError as exc:
            raise HTTPException(status_code=502, detail=f"moe-ids unreachable: {exc}")