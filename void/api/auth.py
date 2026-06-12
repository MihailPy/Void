"""Simple API token authentication for remote Void access."""

import os
from secrets import compare_digest

from fastapi import HTTPException, Request, status


def get_api_token() -> str | None:
    token = os.getenv("VOID_API_TOKEN")
    if token is None or token == "":
        return None
    return token


def require_api_token(request: Request) -> None:
    expected_token = get_api_token()
    if expected_token is None:
        return

    authorization = request.headers.get("Authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized. Check your API token.",
        )

    if not compare_digest(token, expected_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized. Check your API token.",
        )
