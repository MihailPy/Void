"""Domain-specific deterministic route matchers."""

from __future__ import annotations

import re


def clean(value: str) -> str:
    return value.strip().strip('"').strip("'").strip()


def capability_name(value: str) -> str:
    value = clean(value)
    value = re.sub(r"\s+", "_", value)
    value = re.sub(r"[^0-9A-Za-zА-Яа-я_-]+", "", value)
    return value or "requested_capability"


def task_id(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z_-]+", "", clean(value))


def task_title(value: str) -> str:
    cleaned = clean(value)
    return cleaned[:80] or "Scheduled task"


def extract_url(value: str) -> str | None:
    match = re.search(r"https?://[^\s\"'<>]+", value)
    if match:
        return clean(match.group(0)).rstrip(".,;)")

    match = re.search(
        r"(?<!@)\b[A-Za-z0-9.-]+\.[A-Za-z]{2,}[^\s\"'<>]*",
        value,
    )
    if not match:
        return None
    return clean(match.group(0)).rstrip(".,;)")
