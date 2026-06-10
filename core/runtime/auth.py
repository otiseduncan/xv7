from __future__ import annotations

import os
from hmac import compare_digest

from fastapi import Header, HTTPException, status


def configured_api_key() -> str | None:
    value = os.getenv("XV7_API_KEY")
    if value is None:
        return None

    value = value.strip()
    return value or None


def _bearer_token(authorization: str | None) -> str | None:
    if authorization is None:
        return None

    prefix = "Bearer "
    if not authorization.startswith(prefix):
        return None

    token = authorization[len(prefix) :].strip()
    return token or None


async def require_api_key(
    x_xv7_api_key: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
) -> None:
    expected = configured_api_key()
    if expected is None:
        return

    presented = x_xv7_api_key or _bearer_token(authorization)

    if presented is not None and compare_digest(presented, expected):
        return

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="XV7 API key required",
    )
