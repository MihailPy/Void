"""Shared browser URL validation and safety constants."""

from __future__ import annotations

from urllib.parse import urlparse, urlunparse

BLOCKED_SCHEMES = {"file", "javascript", "data"}
ALLOWED_SCHEMES = {"http", "https"}
DEFAULT_TIMEOUT_MS = 15000


def validate_url(url: str) -> str:
    """Normalize and validate a browser URL."""
    clean_url = url.strip()
    if not clean_url:
        raise ValueError("URL is required.")

    parsed = urlparse(clean_url)
    if parsed.scheme.casefold() in BLOCKED_SCHEMES:
        raise ValueError(f"URL scheme is blocked: {parsed.scheme}")

    if not parsed.scheme:
        clean_url = f"https://{clean_url}"
        parsed = urlparse(clean_url)

    scheme = parsed.scheme.casefold()
    if scheme not in ALLOWED_SCHEMES:
        raise ValueError("Only http and https URLs are allowed.")
    if not parsed.netloc:
        raise ValueError("URL host is required.")

    return urlunparse(
        (
            scheme,
            parsed.netloc,
            parsed.path or "",
            parsed.params,
            parsed.query,
            parsed.fragment,
        )
    )


def browser_allowed(url: str) -> bool:
    try:
        validate_url(url)
    except ValueError:
        return False
    return True
