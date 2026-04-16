from uuid import UUID

from fastapi import Header, HTTPException


def actor_from_headers(
    x_user_id: str | None = Header(default=None),
    x_user_role: str | None = Header(default=None),
) -> tuple[UUID, str]:
    """Gateway-provided identity headers (internal trust boundary)."""
    if not x_user_id or not x_user_role:
        raise HTTPException(status_code=401, detail="Missing gateway identity headers")
    try:
        return UUID(x_user_id), x_user_role
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid X-User-Id header")
