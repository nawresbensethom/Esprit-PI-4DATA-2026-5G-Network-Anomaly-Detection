"""
POST /predict/realtime — placeholder for the Phase-5 Redis-Streams consumer.
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["inference"])


@router.post("/predict/realtime")
def predict_realtime() -> dict:
    return {"detail": "Realtime path is implemented in Phase 5 (Redis Streams consumer)."}
