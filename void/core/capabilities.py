"""Persistent capability tracking for Void."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from void.core.safety import PROJECT_ROOT

CAPABILITY_DIR = PROJECT_ROOT / "memory" / "capabilities"
INSTALLED_PATH = CAPABILITY_DIR / "installed.json"
REQUESTED_PATH = CAPABILITY_DIR / "requested.json"
REJECTED_PATH = CAPABILITY_DIR / "rejected.json"
VALID_STATUSES = {"installed", "requested", "rejected"}


@dataclass
class CapabilityRecord:
    id: str
    name: str
    status: str
    description: str
    problem: str | None
    reason: str | None
    created_at: str
    updated_at: str


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _normalize_name(name: str) -> str:
    return name.strip()


def _name_key(name: str) -> str:
    return _normalize_name(name).casefold()


def _paths() -> tuple[Path, Path, Path]:
    return INSTALLED_PATH, REQUESTED_PATH, REJECTED_PATH


def ensure_capability_storage() -> None:
    CAPABILITY_DIR.mkdir(parents=True, exist_ok=True)
    for path in _paths():
        if not path.exists():
            path.write_text("[]\n", encoding="utf-8")


def _load(path: Path) -> list[dict]:
    ensure_capability_storage()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []

    if not isinstance(payload, list):
        return []
    return [item for item in payload if isinstance(item, dict)]


def _save(path: Path, records: list[dict]) -> None:
    ensure_capability_storage()
    path.write_text(
        json.dumps(records, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def load_installed() -> list[dict]:
    return _load(INSTALLED_PATH)


def load_requested() -> list[dict]:
    return _load(REQUESTED_PATH)


def load_rejected() -> list[dict]:
    return _load(REJECTED_PATH)


def save_installed(records: list[dict]) -> None:
    _save(INSTALLED_PATH, records)


def save_requested(records: list[dict]) -> None:
    _save(REQUESTED_PATH, records)


def save_rejected(records: list[dict]) -> None:
    _save(REJECTED_PATH, records)


def list_capabilities() -> dict:
    return {
        "installed": load_installed(),
        "requested": load_requested(),
        "rejected": load_rejected(),
    }


def _find_by_id_or_name(records: list[dict], value: str) -> tuple[int, dict] | None:
    needle = value.strip()
    needle_key = _name_key(needle)
    for index, record in enumerate(records):
        record_id = str(record.get("id", "")).strip()
        record_name = str(record.get("name", "")).strip()
        if record_id == needle or _name_key(record_name) == needle_key:
            return index, record
    return None


def _find_by_name(records: list[dict], name: str) -> dict | None:
    name_key = _name_key(name)
    for record in records:
        if _name_key(str(record.get("name", ""))) == name_key:
            return record
    return None


def _dedupe_by_name(records: list[dict]) -> list[dict]:
    seen: set[str] = set()
    deduped: list[dict] = []
    for record in records:
        name = str(record.get("name", "")).strip()
        if not name:
            continue
        key = _name_key(name)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(record)
    return deduped


def add_requested_capability(
    name: str,
    description: str,
    problem: str,
    reason: str,
) -> dict:
    clean_name = _normalize_name(name)
    if not clean_name:
        return {"ok": False, "error": "Capability name is required."}

    installed = _dedupe_by_name(load_installed())
    requested = _dedupe_by_name(load_requested())
    save_installed(installed)
    save_requested(requested)

    existing_installed = _find_by_name(installed, clean_name)
    if existing_installed is not None:
        return {"ok": True, "duplicate": True, "record": existing_installed}

    existing_requested = _find_by_name(requested, clean_name)
    if existing_requested is not None:
        return {"ok": True, "duplicate": True, "record": existing_requested}

    rejected = _dedupe_by_name(load_rejected())
    rejected_match = _find_by_name(rejected, clean_name)
    if rejected_match is not None:
        rejected = [
            record
            for record in rejected
            if _name_key(str(record.get("name", ""))) != _name_key(clean_name)
        ]
        record = dict(rejected_match)
        record["status"] = "requested"
        record["description"] = description.strip()
        record["problem"] = problem.strip() if problem else None
        record["reason"] = reason.strip() if reason else None
        record["updated_at"] = _now()
        requested.append(record)
        save_rejected(rejected)
        save_requested(requested)
        return {"ok": True, "duplicate": False, "record": record}

    timestamp = _now()
    record = CapabilityRecord(
        id=uuid4().hex[:8],
        name=clean_name,
        status="requested",
        description=description.strip(),
        problem=problem.strip() if problem else None,
        reason=reason.strip() if reason else None,
        created_at=timestamp,
        updated_at=timestamp,
    )
    payload = asdict(record)
    requested.append(payload)
    save_requested(requested)
    return {"ok": True, "duplicate": False, "record": payload}


def mark_capability_installed(capability_id_or_name: str) -> dict:
    requested = _dedupe_by_name(load_requested())
    match = _find_by_id_or_name(requested, capability_id_or_name)
    if match is None:
        existing = _find_by_id_or_name(load_installed(), capability_id_or_name)
        if existing is not None:
            return {"ok": True, "duplicate": True, "record": existing[1]}
        return {"ok": False, "error": "Requested capability not found."}

    index, record = match
    requested.pop(index)
    record = dict(record)
    record["status"] = "installed"
    record["updated_at"] = _now()

    installed = _dedupe_by_name(load_installed())
    existing_installed = _find_by_name(installed, str(record.get("name", "")))
    if existing_installed is None:
        installed.append(record)

    save_requested(requested)
    rejected = [
        rejected_record
        for rejected_record in _dedupe_by_name(load_rejected())
        if _name_key(str(rejected_record.get("name", "")))
        != _name_key(str(record.get("name", "")))
    ]
    save_rejected(rejected)
    save_installed(installed)
    return {"ok": True, "duplicate": existing_installed is not None, "record": record}


def reject_capability(capability_id_or_name: str, reason: str) -> dict:
    requested = _dedupe_by_name(load_requested())
    match = _find_by_id_or_name(requested, capability_id_or_name)
    if match is None:
        existing_installed = _find_by_id_or_name(load_installed(), capability_id_or_name)
        if existing_installed is not None:
            return {"ok": True, "duplicate": True, "record": existing_installed[1]}

        existing_rejected = _find_by_id_or_name(load_rejected(), capability_id_or_name)
        if existing_rejected is not None:
            return {"ok": True, "duplicate": True, "record": existing_rejected[1]}

        clean_name = _normalize_name(capability_id_or_name)
        if not clean_name:
            return {"ok": False, "error": "Capability name is required."}

        timestamp = _now()
        record = asdict(
            CapabilityRecord(
                id=uuid4().hex[:8],
                name=clean_name,
                status="rejected",
                description=f"Rejected capability: {clean_name}",
                problem=None,
                reason=reason.strip(),
                created_at=timestamp,
                updated_at=timestamp,
            )
        )
        rejected = _dedupe_by_name(load_rejected())
        rejected.append(record)
        save_rejected(rejected)
        return {"ok": True, "duplicate": False, "record": record}

    index, record = match
    requested.pop(index)
    record = dict(record)
    record["status"] = "rejected"
    record["reason"] = reason.strip()
    record["updated_at"] = _now()

    rejected = _dedupe_by_name(load_rejected())
    existing_rejected = _find_by_name(rejected, str(record.get("name", "")))
    if existing_rejected is None:
        rejected.append(record)

    save_requested(requested)
    save_rejected(rejected)
    return {"ok": True, "duplicate": existing_rejected is not None, "record": record}


def capability_exists(name: str) -> bool:
    return _find_by_name(load_installed(), name) is not None or _find_by_name(
        load_requested(),
        name,
    ) is not None
