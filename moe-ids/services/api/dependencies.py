"""
Model loader singleton and API key auth.
The predictor is loaded once at startup and cached.
POST /admin/reload reloads it without a restart.
"""
from __future__ import annotations

import threading
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from moe_ids.config import settings
from moe_ids.moe import MoEPredictor

_lock = threading.Lock()
_predictor: MoEPredictor | None = None


def _load_predictor() -> MoEPredictor:
    return MoEPredictor.from_artefacts(settings.artefacts_dir)


def load_predictor_at_startup() -> None:
    """Called from app lifespan — loads the model once."""
    global _predictor
    with _lock:
        _predictor = _load_predictor()


def reload_predictor() -> None:
    """Hot-reload without restart. Called by /admin/reload."""
    global _predictor
    new = _load_predictor()  # load outside lock to minimise blocking time
    with _lock:
        _predictor = new


def get_predictor() -> MoEPredictor:
    """FastAPI dependency — returns the cached singleton."""
    if _predictor is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Model not loaded yet. Try /readyz.",
        )
    return _predictor


def verify_api_key(x_api_key: Annotated[str | None, Header()] = None) -> None:
    """Optional API key check. Skip if settings.api_key is the default placeholder."""
    if settings.api_key == "changeme":
        return
    if x_api_key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-Api-Key header.",
        )


PredictorDep = Annotated[MoEPredictor, Depends(get_predictor)]
AuthDep = Annotated[None, Depends(verify_api_key)]
