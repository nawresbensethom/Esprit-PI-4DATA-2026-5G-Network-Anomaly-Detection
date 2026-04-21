"""
POST /predict/realtime — accepts a JSON payload of one or more flow records.
Phase 5 placeholder: currently delegates to the same batch predictor path.
"""
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["inference"])


@router.post("/predict/realtime")
def predict_realtime() -> dict:
    return {"detail": "Realtime path is implemented in Phase 5 (Redis Streams consumer)."}
