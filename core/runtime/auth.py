from __future__ import annotations

import os
from hmac import compare_digest
from typing import Literal

from fastapi import Header, HTTPException, status


def _normalized_env(name: str) -> str | None:
    """Return a stripped env value, treating empty/whitespace as unset."""
    value = os.getenv(name)
    if value is None:
        return None

    value = value.strip()
    return value or None


def configured_api_key_source() -> Literal["XV7_API_KEY", "CORE_API_KEY"] | None:
    """Return which env var currently configures auth, if any.

    Precedence is explicit and stable:
    1) XV7_API_KEY
    2) CORE_API_KEY
    """
    if _normalized_env("XV7_API_KEY") is not None:
        return "XV7_API_KEY"
    if _normalized_env("CORE_API_KEY") is not None:
        return "CORE_API_KEY"
    return None


def configured_api_key() -> str | None:
    """Return the effective API key value used for request comparison."""
    source = configured_api_key_source()
    if source is None:
        return None
    return _normalized_env(source)


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
