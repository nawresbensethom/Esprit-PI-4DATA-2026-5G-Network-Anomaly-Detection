"""
Gateway → inference-svc proxy. JWT-protected pass-through for predict + admin.
"""
from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response

from app.config import settings
from app.middleware.auth import CurrentUser, get_current_user

router = APIRouter(prefix="/api", tags=["inference"])


async def _forward(method: str, path: str, request: Request, user: CurrentUser) -> Response:
    url = f"{settings.INFERENCE_SERVICE_URL}{path}"
    headers = {
        k: v for k, v in request.headers.items()
        if k.lower() not in {"host", "content-length"}
    }
    headers["X-User-Id"] = user.id
    headers["X-User-Role"] = user.role
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
            raise HTTPException(status_code=502, detail=f"Inference service unreachable: {exc}")
    return Response(
        content=resp.content,
        status_code=resp.status_code,
        media_type=resp.headers.get("content-type"),
    )


@router.post("/predict/batch")
async def predict_batch(request: Request, user: CurrentUser = Depends(get_current_user)):
    return await _forward("POST", "/predict/batch", request, user)


@router.get("/predict/health")
async def predict_health(request: Request, user: CurrentUser = Depends(get_current_user)):
    return await _forward("GET", "/predict/health", request, user)