from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate
from app.services.auth_service import hash_password, log_action


async def list_users(db: AsyncSession) -> list[User]:
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    return list(result.scalars().all())


async def get_user(db: AsyncSession, user_id: UUID) -> User | None:
    return await db.get(User, user_id)


async def create_user(db: AsyncSession, payload: UserCreate, actor_id: UUID) -> User:
    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
        role=payload.role,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    await log_action(db, actor_id, "create_user", target=user.email, details={"role": user.role})
    return user


async def update_user(db: AsyncSession, user_id: UUID, payload: UserUpdate, actor_id: UUID) -> User | None:
    user = await db.get(User, user_id)
    if user is None:
        return None
    changes = payload.model_dump(exclude_unset=True)
    for k, v in changes.items():
        setattr(user, k, v)
    await db.commit()
    await db.refresh(user)
    await log_action(db, actor_id, "update_user", target=user.email, details=changes)
    return user


async def soft_delete_user(db: AsyncSession, user_id: UUID, actor_id: UUID) -> bool:
    user = await db.get(User, user_id)
    if user is None:
        return False
    user.is_active = False
    await db.commit()
    await log_action(db, actor_id, "delete_user", target=user.email)
    return True
