"""
Internal API-key check used between the gateway and the ML microservices.
The gateway injects X-Api-Key on every forwarded request; external callers
never reach these services directly.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from moe_ids.config import settings


def verify_api_key(x_api_key: Annotated[str | None, Header()] = None) -> None:
    if settings.api_key == "changeme":
        return
    if x_api_key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-Api-Key header.",
        )


AuthDep = Annotated[None, Depends(verify_api_key)]
