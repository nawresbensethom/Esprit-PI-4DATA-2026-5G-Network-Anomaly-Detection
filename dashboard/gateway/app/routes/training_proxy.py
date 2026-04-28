"""
Gateway → moe-training-svc + moe-inference-svc proxy for training operations.
JWT-validated; write endpoints require the 'admin' role.
"""
from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response

from app.config import settings
from app.middleware.auth import CurrentUser, get_current_user, require_roles

router = APIRouter(prefix="/api/train", tags=["training"])


async def _forward(
    method: str,
    upstream_base: str,
    path: str,
    request: Request,
    user: CurrentUser,
) -> Response:
    url = f"{upstream_base}{path}"
    headers = {
        k: v for k, v in request.headers.items()
        if k.lower() not in {"host", "content-length"}
    }
    headers["X-User-Id"] = user.id
    headers["X-User-Role"] = user.role
    headers["X-Api-Key"] = settings.INTERNAL_API_KEY
    body = await request.body()
    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            resp = await client.request(
                method, url,
                content=body,
                headers=headers,
                params=request.query_params,
            )
        except httpx.RequestError as exc:
            raise HTTPException(status_code=502, detail=f"Training service unreachable: {exc}")
    return Response(
        content=resp.content,
        status_code=resp.status_code,
        media_type=resp.headers.get("content-type"),
    )


@router.post("/start")
async def train_start(
    request: Request,
    user: CurrentUser = Depends(require_roles("admin")),
):
    """Kick off a training run. Admin only."""
    return await _forward("POST", settings.TRAINING_SERVICE_URL, "/admin/train", request, user)


@router.get("/status")
async def train_status(
    request: Request,
    user: CurrentUser = Depends(get_current_user),
):
    """Poll the running training job. Any authenticated user."""
    return await _forward(
        "GET", settings.TRAINING_SERVICE_URL, "/admin/train/status", request, user
    )


@router.post("/reload")
async def train_reload(
    request: Request,
    user: CurrentUser = Depends(require_roles("admin")),
):
    """Hot-reload the in-memory model on the inference service. Admin only."""
    return await _forward(
        "POST", settings.INFERENCE_SERVICE_URL, "/admin/reload", request, user
    )
