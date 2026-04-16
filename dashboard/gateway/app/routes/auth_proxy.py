import httpx
from fastapi import APIRouter, Depends, Request, Response, HTTPException

from app.config import settings
from app.middleware.auth import CurrentUser, get_current_user, require_roles

router = APIRouter(prefix="/api", tags=["auth"])


async def _forward(method: str, path: str, request: Request, user: CurrentUser | None = None) -> Response:
    url = f"{settings.AUTH_SERVICE_URL}{path}"
    headers = {k: v for k, v in request.headers.items() if k.lower() not in {"host", "content-length"}}
    if user is not None:
        headers["X-User-Id"] = user.id
        headers["X-User-Role"] = user.role
    body = await request.body()
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.request(method, url, content=body, headers=headers, params=request.query_params)
        except httpx.RequestError as exc:
            raise HTTPException(status_code=502, detail=f"Auth service unreachable: {exc}")
    return Response(content=resp.content, status_code=resp.status_code, media_type=resp.headers.get("content-type"))


@router.post("/auth/login")
async def login(request: Request):
    return await _forward("POST", "/auth/login", request)


@router.post("/auth/refresh")
async def refresh(request: Request):
    return await _forward("POST", "/auth/refresh", request)


@router.get("/auth/verify")
async def verify(request: Request, user: CurrentUser = Depends(get_current_user)):
    return await _forward("GET", "/auth/verify", request, user)


@router.post("/auth/register")
async def register(request: Request, user: CurrentUser = Depends(require_roles("admin"))):
    return await _forward("POST", "/auth/register", request, user)


@router.get("/users")
async def list_users(request: Request, user: CurrentUser = Depends(require_roles("admin"))):
    return await _forward("GET", "/users", request, user)


@router.get("/users/{user_id}")
async def get_user(user_id: str, request: Request, user: CurrentUser = Depends(require_roles("admin"))):
    return await _forward("GET", f"/users/{user_id}", request, user)


@router.put("/users/{user_id}")
async def update_user(user_id: str, request: Request, user: CurrentUser = Depends(require_roles("admin"))):
    return await _forward("PUT", f"/users/{user_id}", request, user)


@router.delete("/users/{user_id}")
async def delete_user(user_id: str, request: Request, user: CurrentUser = Depends(require_roles("admin"))):
    return await _forward("DELETE", f"/users/{user_id}", request, user)
