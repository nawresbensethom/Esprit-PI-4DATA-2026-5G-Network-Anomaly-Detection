"""
Gateway → moe-monitoring-svc proxy for drift detection endpoints.
JWT-validated; drift runs require the 'admin' role.
"""
from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response

from app.config import settings
from app.middleware.auth import CurrentUser, get_current_user, require_roles

router = APIRouter(prefix="/api/drift", tags=["monitoring"])


async def _forward(method: str, path: str, request: Request, user: CurrentUser) -> Response:
    url = f"{settings.MONITORING_SERVICE_URL}{path}"
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
            raise HTTPException(status_code=502, detail=f"Monitoring service unreachable: {exc}")
    return Response(
        content=resp.content,
        status_code=resp.status_code,
        media_type=resp.headers.get("content-type"),
    )


@router.post("/run")
async def drift_run(
    request: Request,
    user: CurrentUser = Depends(require_roles("admin")),
):
    """Execute a drift check now. Admin only."""
    return await _forward("POST", "/drift", request, user)


@router.get("/last")
async def drift_last(
    request: Request,
    user: CurrentUser = Depends(get_current_user),
):
    """Return the most recent drift report (in-process cache)."""
    return await _forward("GET", "/drift/last", request, user)
