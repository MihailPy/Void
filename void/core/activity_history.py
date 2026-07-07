"""JSON-backed execution activity history."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from uuid import uuid4

from void.core.safety import PROJECT_ROOT

ACTIVITY_HISTORY_PATH = PROJECT_ROOT / "memory" / "activity_history.json"
MAX_ACTIVITIES = 200


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _empty_payload() -> dict[str, list[dict[str, Any]]]:
    return {"activities": []}


def ensure_activity_history() -> None:
    ACTIVITY_HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not ACTIVITY_HISTORY_PATH.exists():
        _save(_empty_payload())


def _load() -> dict[str, list[dict[str, Any]]]:
    ensure_activity_history()
    try:
        payload = json.loads(ACTIVITY_HISTORY_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return _empty_payload()

    if not isinstance(payload, dict):
        return _empty_payload()
    activities = payload.get("activities", [])
    if not isinstance(activities, list):
        activities = []
    return {"activities": [item for item in activities if isinstance(item, dict)]}


def _save(payload: dict[str, list[dict[str, Any]]]) -> None:
    ACTIVITY_HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    ACTIVITY_HISTORY_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def log_activity(
    activity_type: str,
    status: str,
    summary: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Append one execution activity and trim old entries."""
    activity = {
        "id": uuid4().hex[:12],
        "timestamp": _now(),
        "activity_type": str(activity_type).strip() or "unknown",
        "status": str(status).strip() or "unknown",
        "summary": str(summary).strip(),
        "metadata": metadata or {},
    }
    payload = _load()
    payload["activities"].append(activity)
    payload["activities"] = payload["activities"][-MAX_ACTIVITIES:]
    _save(payload)
    return activity


def list_recent(limit: int = 20) -> list[dict[str, Any]]:
    safe_limit = min(MAX_ACTIVITIES, max(1, int(limit)))
    activities = _load()["activities"]
    return list(reversed(activities[-safe_limit:]))


def get_last_activity() -> dict[str, Any] | None:
    activities = _load()["activities"]
    return activities[-1] if activities else None


def clear_history() -> None:
    _save(_empty_payload())
