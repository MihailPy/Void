"""Pending approval storage for state-changing tool actions."""

from __future__ import annotations

import json
from datetime import datetime
from uuid import uuid4

from void.core.safety import PROJECT_ROOT
from void.core.types import AgentAction

APPROVALS_PATH = PROJECT_ROOT / "memory" / "pending_approvals.json"


def _load() -> list[dict]:
    if not APPROVALS_PATH.exists():
        return []

    try:
        payload = json.loads(APPROVALS_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []

    if not isinstance(payload, list):
        return []
    return [item for item in payload if isinstance(item, dict)]


def _save(approvals: list[dict]) -> None:
    APPROVALS_PATH.parent.mkdir(parents=True, exist_ok=True)
    APPROVALS_PATH.write_text(
        json.dumps(approvals, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def create_approval(action: AgentAction) -> str:
    approval_id = uuid4().hex[:12]
    approvals = _load()
    approvals.append(
        {
            "id": approval_id,
            "action": action.action,
            "arguments": action.arguments,
            "reason": action.reason,
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
    )
    _save(approvals)
    return approval_id


def list_approvals() -> list[dict]:
    return _load()


def approve(id: str) -> AgentAction | None:
    for approval in _load():
        if approval.get("id") != id:
            continue

        action = approval.get("action")
        arguments = approval.get("arguments", {})
        reason = approval.get("reason", "")

        if not isinstance(action, str) or not isinstance(arguments, dict):
            return None
        if not isinstance(reason, str):
            reason = str(reason)

        return AgentAction(action=action, arguments=arguments, reason=reason)

    return None


def reject(id: str) -> bool:
    approvals = _load()
    remaining = [approval for approval in approvals if approval.get("id") != id]
    if len(remaining) == len(approvals):
        return False

    _save(remaining)
    return True


def clear_approval(id: str) -> None:
    approvals = _load()
    _save([approval for approval in approvals if approval.get("id") != id])
