from datetime import datetime, timedelta, timezone
from uuid import UUID

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.user import AuditLog, User
from app.schemas.user import TokenResponse, UserPublic

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return pwd_context.verify(password, hashed)


def _build_token(user: User, token_type: str, expires_delta: timedelta) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "role": user.role,
        "iat": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
        "type": token_type,
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def create_access_token(user: User) -> str:
    return _build_token(user, "access", timedelta(minutes=settings.JWT_EXPIRY_MINUTES))


def create_refresh_token(user: User) -> str:
    return _build_token(user, "refresh", timedelta(days=settings.JWT_REFRESH_EXPIRY_DAYS))


def decode_token(token: str, expected_type: str) -> dict:
    payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    if payload.get("type") != expected_type:
        raise JWTError(f"Expected {expected_type} token, got {payload.get('type')}")
    return payload


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: UUID) -> User | None:
    return await db.get(User, user_id)


async def log_action(db: AsyncSession, actor_id: UUID | None, action: str, target: str | None = None, details: dict | None = None) -> None:
    db.add(AuditLog(actor_id=actor_id, action=action, target_entity=target, details=details))
    await db.commit()


async def authenticate(db: AsyncSession, email: str, password: str) -> TokenResponse | None:
    user = await get_user_by_email(db, email)
    if user is None or not user.is_active or not verify_password(password, user.hashed_password):
        return None
    access = create_access_token(user)
    refresh = create_refresh_token(user)
    await log_action(db, user.id, "login", target=user.email)
    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        user=UserPublic.model_validate(user),
    )


async def refresh_access_token(db: AsyncSession, refresh_token: str) -> str | None:
    try:
        payload = decode_token(refresh_token, "refresh")
    except JWTError:
        return None
    user = await get_user_by_id(db, UUID(payload["sub"]))
    if user is None or not user.is_active:
        return None
    return create_access_token(user)


async def ensure_default_admin(db: AsyncSession) -> None:
    existing = await db.execute(select(User).limit(1))
    if existing.scalar_one_or_none() is not None:
        return
    admin = User(
        email=settings.DEFAULT_ADMIN_EMAIL,
        hashed_password=hash_password(settings.DEFAULT_ADMIN_PASSWORD),
        full_name=settings.DEFAULT_ADMIN_NAME,
        role="admin",
        is_active=True,
    )
    db.add(admin)
    await db.commit()
    await db.refresh(admin)
    await log_action(db, admin.id, "seed_admin", target=admin.email)
