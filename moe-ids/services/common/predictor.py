"""
Model loader singleton. Only the inference service loads a predictor at
startup; training and monitoring do not carry the model in memory.
"""
from __future__ import annotations

import threading
from typing import Annotated

from fastapi import Depends, HTTPException, status

from moe_ids.config import settings
from moe_ids.moe import MoEPredictor

_lock = threading.Lock()
_predictor: MoEPredictor | None = None


def _load_predictor() -> MoEPredictor:
    return MoEPredictor.from_artefacts(settings.artefacts_dir)


def load_predictor_at_startup() -> None:
    global _predictor
    with _lock:
        _predictor = _load_predictor()


def reload_predictor() -> None:
    global _predictor
    new = _load_predictor()
    with _lock:
        _predictor = new


def get_predictor() -> MoEPredictor:
    if _predictor is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Model not loaded yet. Try /readyz.",
        )
    return _predictor


PredictorDep = Annotated[MoEPredictor, Depends(get_predictor)]
