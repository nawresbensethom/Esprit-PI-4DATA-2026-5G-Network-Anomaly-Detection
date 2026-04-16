from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.routes.deps import actor_from_headers
from app.schemas.user import UserCreate, UserPublic, UserUpdate
from app.services import user_service

router = APIRouter(tags=["users"])


def _require_admin(identity: tuple[UUID, str]) -> UUID:
    actor_id, role = identity
    if role != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")
    return actor_id


@router.post("/auth/register", response_model=UserPublic, status_code=201)
async def register(
    payload: UserCreate,
    identity: tuple[UUID, str] = Depends(actor_from_headers),
    db: AsyncSession = Depends(get_db),
):
    actor_id = _require_admin(identity)
    existing = await user_service.list_users(db)
    if any(u.email == payload.email for u in existing):
        raise HTTPException(status_code=409, detail="Email already registered")
    return await user_service.create_user(db, payload, actor_id)


@router.get("/users", response_model=list[UserPublic])
async def list_users(
    identity: tuple[UUID, str] = Depends(actor_from_headers),
    db: AsyncSession = Depends(get_db),
):
    _require_admin(identity)
    return await user_service.list_users(db)


@router.get("/users/{user_id}", response_model=UserPublic)
async def get_user(
    user_id: UUID,
    identity: tuple[UUID, str] = Depends(actor_from_headers),
    db: AsyncSession = Depends(get_db),
):
    _require_admin(identity)
    user = await user_service.get_user(db, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.put("/users/{user_id}", response_model=UserPublic)
async def update_user(
    user_id: UUID,
    payload: UserUpdate,
    identity: tuple[UUID, str] = Depends(actor_from_headers),
    db: AsyncSession = Depends(get_db),
):
    actor_id = _require_admin(identity)
    if user_id == actor_id and payload.role is not None and payload.role != "admin":
        raise HTTPException(status_code=400, detail="Cannot demote yourself")
    if user_id == actor_id and payload.is_active is False:
        raise HTTPException(status_code=400, detail="Cannot deactivate yourself")
    user = await user_service.update_user(db, user_id, payload, actor_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.delete("/users/{user_id}", status_code=204)
async def delete_user(
    user_id: UUID,
    identity: tuple[UUID, str] = Depends(actor_from_headers),
    db: AsyncSession = Depends(get_db),
):
    actor_id = _require_admin(identity)
    if user_id == actor_id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    ok = await user_service.soft_delete_user(db, user_id, actor_id)
    if not ok:
        raise HTTPException(status_code=404, detail="User not found")
    return None