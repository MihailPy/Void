"""Project registry snapshot storage, validation, diff, and retention."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from void.__version__ import __version__
from void.core import activity_history
from void.core.safety import PROJECT_ROOT

PROJECT_SNAPSHOT_DIR = PROJECT_ROOT / "void" / "project-snapshots"
PROJECT_SNAPSHOT_VERSION = 1
MISSING = {"missing": True}
DEFAULT_RETENTION_CONFIG = {
    "automatic": True,
    "keep_latest": 100,
    "max_age_days": None,
}


def _now() -> datetime:
    return datetime.now().astimezone()


def _slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_-]+", "-", value.strip().casefold()).strip("-_")
    return slug[:80] or "manual"


def _snapshot_path_for_index(created: datetime, reason: str, index: int) -> Path:
    suffix = "" if index == 1 else f"-{index}"
    base = created.strftime("%Y-%m-%d_%H-%M-%S-%f")
    return PROJECT_SNAPSHOT_DIR / f"{base}_{_slug(reason)}{suffix}.json"


def _confined(path: Path) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(PROJECT_SNAPSHOT_DIR.resolve())
    except ValueError as error:
        raise ValueError("Snapshot path must stay inside the project snapshot directory.") from error
    if resolved.suffix != ".json":
        raise ValueError("Snapshot file must be a JSON file.")
    return resolved


def snapshot_path(snapshot_id: str | None = None, filename: str | None = None) -> Path:
    if snapshot_id is not None and str(snapshot_id).strip():
        clean = str(snapshot_id).strip()
        if clean.endswith(".json"):
            clean = clean[:-5]
        candidate = Path(f"{clean}.json")
        if candidate.name != f"{clean}.json":
            raise ValueError("Snapshot id must not contain directories.")
        return _confined(PROJECT_SNAPSHOT_DIR / candidate.name)
    if filename is not None and str(filename).strip():
        clean_filename = str(filename).strip()
        candidate = Path(clean_filename)
        if candidate.name != clean_filename:
            raise ValueError("Snapshot filename must not contain directories.")
        return _confined(PROJECT_SNAPSHOT_DIR / clean_filename)
    raise ValueError("Snapshot id or filename is required.")


def _write_new_snapshot_json(created: datetime, reason: str, payload: dict[str, Any]) -> Path:
    PROJECT_SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    index = 1
    while True:
        candidate = _confined(_snapshot_path_for_index(created, reason, index))
        snapshot_payload = deepcopy(payload)
        snapshot_payload["snapshot"]["id"] = candidate.stem
        content = json.dumps(snapshot_payload, ensure_ascii=False, indent=2) + "\n"
        temp_name = ""
        temp_file = tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=PROJECT_SNAPSHOT_DIR,
            prefix=".snapshot-",
            suffix=".tmp",
            delete=False,
        )
        try:
            with temp_file:
                temp_name = temp_file.name
                temp_file.write(content)
                temp_file.flush()
                os.fsync(temp_file.fileno())
            try:
                os.link(temp_name, candidate)
                return candidate
            except FileExistsError:
                index += 1
        finally:
            if temp_name:
                try:
                    Path(temp_name).unlink()
                except FileNotFoundError:
                    pass


def _metadata_for_registry(registry_payload: dict[str, Any]) -> dict[str, Any]:
    projects = registry_payload.get("projects", [])
    return {
        "project_count": len(projects) if isinstance(projects, list) else 0,
        "current_project": str(registry_payload.get("current_project", "")).strip(),
    }


def retention_config(registry_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    config = deepcopy(DEFAULT_RETENTION_CONFIG)
    source = registry_payload.get("project_snapshots") if isinstance(registry_payload, dict) else None
    if isinstance(source, dict):
        if isinstance(source.get("automatic"), bool):
            config["automatic"] = source["automatic"]
        if isinstance(source.get("keep_latest"), int):
            config["keep_latest"] = max(0, source["keep_latest"])
        if source.get("max_age_days") is None or isinstance(source.get("max_age_days"), int):
            config["max_age_days"] = source.get("max_age_days")
    return config


def create_snapshot(
    registry_payload: dict[str, Any],
    *,
    reason: str = "manual",
    source_action: str = "manual",
    automatic: bool = False,
    log: bool = True,
) -> dict[str, Any]:
    from void.core import project_context

    project_context._read_project_context_raw()
    errors = project_context._strict_registry_errors(registry_payload)
    if errors:
        raise ValueError("\n".join(errors))

    created = _now()
    created_at = created.isoformat(timespec="microseconds")
    clean_reason = str(reason or "").strip() or "manual"
    envelope = {
        "snapshot": {
            "version": PROJECT_SNAPSHOT_VERSION,
            "id": "",
            "created_at": created_at,
            "reason": clean_reason,
            "source_action": str(source_action or clean_reason).strip() or "manual",
            "void_version": __version__,
            "metadata": _metadata_for_registry(registry_payload),
        },
        "registry": deepcopy(registry_payload),
    }
    snapshot_file = _write_new_snapshot_json(created, clean_reason, envelope)
    snapshot_id = snapshot_file.stem
    size = snapshot_file.stat().st_size
    metadata = envelope["snapshot"]["metadata"]
    result = {
        "id": snapshot_id,
        "filename": snapshot_file.name,
        "path": str(snapshot_file),
        "created_at": created_at,
        "reason": clean_reason,
        "source_action": envelope["snapshot"]["source_action"],
        "size": size,
        "project_count": metadata["project_count"],
        "current_project": metadata["current_project"],
    }
    if log:
        activity_history.log_activity(
            "project_snapshot_created",
            "success",
            f"Created project registry snapshot {snapshot_file.name}",
            {
                "automatic": automatic,
                "source_action": result["source_action"],
                "snapshot_id": snapshot_id,
                "filename": snapshot_file.name,
                "project_count": result["project_count"],
                "current_project": result["current_project"],
            },
        )
    return result


def _load_payload(path: Path) -> tuple[Any | None, list[str]]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), []
    except FileNotFoundError:
        return None, [f"Snapshot file not found: {path.name}"]
    except OSError as error:
        return None, [f"Snapshot file could not be read: {error}"]
    except json.JSONDecodeError as error:
        return None, [f"Snapshot JSON is invalid: {error}"]


def _snapshot_sections(payload: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    if not isinstance(payload, dict):
        return {}, {}
    snapshot = payload.get("snapshot")
    registry = payload.get("registry")
    return (
        snapshot if isinstance(snapshot, dict) else {},
        registry if isinstance(registry, dict) else {},
    )


def _preview(path: Path | None, payload: Any, warnings: list[str], errors: list[str]) -> dict[str, Any]:
    snapshot, registry = _snapshot_sections(payload)
    projects = registry.get("projects", []) if isinstance(registry, dict) else []
    if not isinstance(projects, list):
        projects = []
    metadata = snapshot.get("metadata", {}) if isinstance(snapshot, dict) else {}
    if not isinstance(metadata, dict):
        metadata = {}
    project_count = metadata.get("project_count")
    item = {
        "ok": not errors,
        "id": str(snapshot.get("id", "")).strip(),
        "filename": path.name if path is not None else "",
        "created_at": str(snapshot.get("created_at", "")).strip(),
        "reason": str(snapshot.get("reason", "")).strip(),
        "source_action": str(snapshot.get("source_action", "")).strip(),
        "project_count": project_count if isinstance(project_count, int) else len(projects),
        "current_project": str(metadata.get("current_project") or registry.get("current_project") or "").strip(),
        "projects": [
            {"id": str(project.get("id", "")), "name": str(project.get("name", "") or project.get("id", ""))}
            for project in projects
            if isinstance(project, dict)
        ],
        "warnings": warnings,
        "errors": errors,
    }
    item["summary"] = _format_preview(item)
    return item


def _format_preview(preview: dict[str, Any]) -> str:
    lines = [
        "Project snapshot preview",
        "",
        f"Snapshot: {preview.get('filename') or preview.get('id') or 'unknown'}",
        f"Created: {preview.get('created_at') or 'unknown'}",
        f"Reason: {preview.get('reason') or 'unknown'}",
        f"Projects: {preview.get('project_count', 0)}",
        f"Current project: {preview.get('current_project') or 'unknown'}",
    ]
    if preview.get("warnings"):
        lines.extend(["", "Warnings:"])
        lines.extend(f"- {warning}" for warning in preview["warnings"])
    if preview.get("errors"):
        lines.extend(["", "Validation errors:"])
        lines.extend(f"- {error}" for error in preview["errors"])
    return "\n".join(lines)


def validate_payload(payload: Any, path: Path | None = None) -> dict[str, Any]:
    from void.core import project_context

    warnings: list[str] = []
    errors: list[str] = []
    if not isinstance(payload, dict):
        return _preview(path, payload, warnings, ["Snapshot root must be an object."])
    snapshot = payload.get("snapshot")
    registry = payload.get("registry")
    if not isinstance(snapshot, dict):
        errors.append("Snapshot metadata must be an object.")
        snapshot = {}
    if not isinstance(registry, dict):
        errors.append("Snapshot registry must be an object.")
        registry = {}
    if snapshot.get("version") != PROJECT_SNAPSHOT_VERSION:
        errors.append(f"Unsupported snapshot version: {snapshot.get('version')}")
    if not str(snapshot.get("id", "")).strip():
        errors.append("Snapshot id is required.")
    if not str(snapshot.get("created_at", "")).strip():
        errors.append("Snapshot created_at is required.")
    metadata = snapshot.get("metadata", {})
    if not isinstance(metadata, dict):
        errors.append("Snapshot metadata must be an object.")
        metadata = {}
    errors.extend(project_context._strict_registry_errors(registry))
    metadata_count = metadata.get("project_count")
    project_count = len(registry.get("projects", [])) if isinstance(registry.get("projects"), list) else 0
    if metadata_count is not None and metadata_count != project_count:
        warnings.append(
            f"Snapshot metadata project_count is {metadata_count}, but projects contains {project_count}."
        )
    return _preview(path, payload, warnings, errors)


def validate_snapshot(snapshot_id: str | None = None, filename: str | None = None) -> dict[str, Any]:
    path = snapshot_path(snapshot_id, filename)
    payload, load_errors = _load_payload(path)
    if load_errors:
        return _preview(path, {}, [], load_errors)
    preview = validate_payload(payload, path)
    return {
        "ok": preview["ok"],
        "snapshot": {
            key: preview[key]
            for key in ("id", "filename", "created_at", "reason", "source_action", "project_count", "current_project")
        },
        "projects": preview["projects"],
        "warnings": preview["warnings"],
        "errors": preview["errors"],
        "summary": preview["summary"],
    }


def _parse_snapshot_created_at(value: Any) -> datetime | None:
    try:
        return datetime.fromisoformat(str(value or ""))
    except ValueError:
        return None


def _filename_parts(filename: str) -> tuple[datetime | None, str, int]:
    stem = Path(filename).stem
    suffix = 1
    suffix_match = re.fullmatch(r"(.+)-(\d+)", stem)
    if suffix_match:
        stem = suffix_match.group(1)
        suffix = int(suffix_match.group(2))
    timestamp = None
    timestamp_match = re.match(r"^(\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}-\d{6})", stem)
    if timestamp_match:
        try:
            timestamp = datetime.strptime(timestamp_match.group(1), "%Y-%m-%d_%H-%M-%S-%f").astimezone()
        except ValueError:
            timestamp = None
    return timestamp, stem, suffix


def _snapshot_sort_key(item: dict[str, Any]) -> tuple[float, float, str, int, str]:
    filename = str(item.get("filename") or "")
    created = _parse_snapshot_created_at(item.get("created_at"))
    filename_created, base, suffix = _filename_parts(filename)
    created_ts = created.timestamp() if created is not None else float("-inf")
    filename_ts = filename_created.timestamp() if filename_created is not None else float("-inf")
    return (created_ts, filename_ts, base, suffix, filename)


def list_snapshots() -> list[dict[str, Any]]:
    PROJECT_SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    items: list[dict[str, Any]] = []
    for path in PROJECT_SNAPSHOT_DIR.glob("*.json"):
        payload, load_errors = _load_payload(path)
        preview = _preview(path, {}, [], load_errors) if load_errors else validate_payload(payload, path)
        items.append(
            {
                "id": preview.get("id") or path.stem,
                "filename": path.name,
                "created_at": preview.get("created_at", ""),
                "reason": preview.get("reason", ""),
                "source_action": preview.get("source_action", ""),
                "size": path.stat().st_size,
                "project_count": preview.get("project_count"),
                "current_project": preview.get("current_project", ""),
                "valid": not preview.get("errors"),
                "errors": preview.get("errors", []),
            }
        )

    return sorted(items, key=_snapshot_sort_key, reverse=True)


def _project_map(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    from void.core import project_context

    return {
        project_context._normalize(str(project.get("id", ""))): project
        for project in payload.get("projects", [])
        if isinstance(project, dict)
    }


def _json_safe(value: Any) -> Any:
    if value is _MISSING_SENTINEL:
        return deepcopy(MISSING)
    return deepcopy(value)


_MISSING_SENTINEL = object()


def _diff_values(before: Any, after: Any, prefix: str = "") -> list[dict[str, Any]]:
    if isinstance(before, dict) and isinstance(after, dict):
        changes: list[dict[str, Any]] = []
        for key in sorted(set(before) | set(after), key=str):
            child_before = before.get(key, _MISSING_SENTINEL)
            child_after = after.get(key, _MISSING_SENTINEL)
            path = f"{prefix}.{key}" if prefix else str(key)
            changes.extend(_diff_values(child_before, child_after, path))
        return changes
    if before != after:
        return [{"path": prefix, "before": _json_safe(before), "after": _json_safe(after)}]
    return []


def diff_registries(snapshot_registry: dict[str, Any], current_registry: dict[str, Any]) -> dict[str, Any]:
    from void.core import project_context

    before_projects = _project_map(snapshot_registry)
    after_projects = _project_map(current_registry)
    before_ids = set(before_projects)
    after_ids = set(after_projects)

    added = [after_projects[key] for key in sorted(after_ids - before_ids)]
    removed = [before_projects[key] for key in sorted(before_ids - after_ids)]
    unchanged: list[dict[str, Any]] = []
    updated: list[dict[str, Any]] = []
    for key in sorted(before_ids & after_ids):
        changes = _diff_values(before_projects[key], after_projects[key])
        if changes:
            entry = {
                "id": str(after_projects[key].get("id") or before_projects[key].get("id") or key),
                "name": {
                    "before": before_projects[key].get("name"),
                    "after": after_projects[key].get("name"),
                },
                "changes": changes,
            }
            updated.append(entry)
        else:
            unchanged.append({"id": str(after_projects[key].get("id") or key), "name": after_projects[key].get("name")})

    root_before = {key: value for key, value in snapshot_registry.items() if key != "projects"}
    root_after = {key: value for key, value in current_registry.items() if key != "projects"}
    root_changes = _diff_values(root_before, root_after)
    before_current = str(snapshot_registry.get("current_project", "")).strip()
    after_current = str(current_registry.get("current_project", "")).strip()
    return {
        "current_project": {
            "before": before_current,
            "after": after_current,
            "changed": project_context._normalize(before_current) != project_context._normalize(after_current),
        },
        "counts": {
            "added": len(added),
            "removed": len(removed),
            "updated": len(updated),
            "unchanged": len(unchanged),
        },
        "added": added,
        "removed": removed,
        "updated": updated,
        "unchanged": unchanged,
        "root_changes": root_changes,
    }


def diff_snapshot(snapshot_id: str | None = None, filename: str | None = None) -> dict[str, Any]:
    from void.core import project_context

    path = snapshot_path(snapshot_id, filename)
    payload, load_errors = _load_payload(path)
    if load_errors:
        raise ValueError("\n".join(load_errors))
    preview = validate_payload(payload, path)
    if preview["errors"]:
        raise ValueError("\n".join(preview["errors"]))
    diff = diff_registries(deepcopy(payload["registry"]), project_context._read_project_context_raw())
    diff["snapshot_id"] = preview["id"]
    diff["filename"] = path.name
    return diff


def plan_snapshot_restore(snapshot_id: str | None = None, filename: str | None = None) -> dict[str, Any]:
    from void.core import project_context

    path = snapshot_path(snapshot_id, filename)
    payload, load_errors = _load_payload(path)
    if load_errors:
        return {"snapshot_path": path, "payload": None, "preview": _preview(path, {}, [], load_errors), "restored_payload": {}}
    preview = validate_payload(payload, path)
    restored_payload = deepcopy(payload["registry"]) if not preview["errors"] else {}
    current_payload = project_context._read_project_context_raw()
    diff = diff_registries(restored_payload, current_payload) if not preview["errors"] else {}
    return {
        "snapshot_path": path,
        "payload": payload,
        "preview": preview,
        "diff": diff,
        "restored_payload": restored_payload,
    }


def delete_snapshot(snapshot_id: str | None = None, filename: str | None = None) -> dict[str, Any]:
    path = snapshot_path(snapshot_id, filename)
    if not path.exists():
        raise ValueError(f"Snapshot file not found: {path.name}")
    size = path.stat().st_size
    path.unlink()
    activity_history.log_activity(
        "project_snapshot_deleted",
        "success",
        f"Deleted project registry snapshot {path.name}",
        {"snapshot_id": path.stem, "filename": path.name, "path": str(path), "size": size},
    )
    return {"id": path.stem, "filename": path.name, "path": str(path), "size": size}


def delete_snapshot_validation(snapshot_id: str | None = None, filename: str | None = None) -> None:
    path = snapshot_path(snapshot_id, filename)
    if not path.exists():
        raise ValueError(f"Snapshot file not found: {path.name}")


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _file_identity(path: Path) -> dict[str, Any]:
    confined = _confined(path)
    if not confined.exists():
        raise ValueError(f"Snapshot file not found: {confined.name}")
    if not confined.is_file():
        raise ValueError(f"Snapshot path is not a regular file: {confined.name}")
    if confined.suffix != ".json":
        raise ValueError("Snapshot file must be a JSON file.")
    stat = confined.stat()
    return {"filename": confined.name, "size": stat.st_size, "sha256": _file_hash(confined)}


def _snapshot_inventory() -> list[dict[str, Any]]:
    PROJECT_SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    return [_file_identity(path) for path in sorted(PROJECT_SNAPSHOT_DIR.glob("*.json"), key=lambda item: item.name)]


def _with_identity(item: dict[str, Any]) -> dict[str, Any]:
    planned = dict(item)
    identity = _file_identity(snapshot_path(filename=str(item.get("filename") or "")))
    planned.update(identity)
    return planned


def plan_prune_snapshots(
    *,
    keep_latest: int | None = 50,
    max_age_days: int | None = 90,
    include_invalid: bool = False,
    now: datetime | None = None,
) -> dict[str, Any]:
    keep = None if keep_latest is None else max(0, int(keep_latest))
    age_days = None if max_age_days is None else max(0, int(max_age_days))
    listed = list_snapshots()
    inventory = _snapshot_inventory()
    plan_now = now or _now()
    created_at = plan_now.isoformat(timespec="microseconds")
    cutoff = None if age_days is None else plan_now - timedelta(days=age_days)
    deleted: list[dict[str, Any]] = []
    retained: list[dict[str, Any]] = []
    warnings: list[str] = []
    if keep is None and cutoff is None:
        warnings.append("No snapshot prune policy was provided; no snapshots will be deleted.")
    for index, item in enumerate(listed):
        valid = bool(item.get("valid"))
        if not valid and not include_invalid:
            warnings.append(f"Retained malformed snapshot {item['filename']}.")
            retained.append(item)
            continue
        protected_by_count = keep is not None and index < keep
        created = _parse_snapshot_created_at(item.get("created_at"))
        if created is None:
            filename_created, _, _ = _filename_parts(str(item.get("filename") or ""))
            created = filename_created
        expired_by_age = cutoff is not None and created is not None and created < cutoff
        overflow_by_count = keep is not None and not protected_by_count
        if keep is None:
            should_delete = expired_by_age
        elif cutoff is None:
            should_delete = overflow_by_count
        else:
            should_delete = overflow_by_count and expired_by_age
        if should_delete:
            deleted.append(_with_identity(item))
        else:
            if not valid and include_invalid and cutoff is not None and created is None:
                warnings.append(f"Retained malformed snapshot {item['filename']} because its age is unknown.")
            retained.append(item)
    return {
        "version": 1,
        "created_at": created_at,
        "policy": {
            "keep_latest": keep,
            "max_age_days": age_days,
            "include_invalid": include_invalid,
        },
        "inventory": inventory,
        "deleted": deleted,
        "retained": retained,
        "warnings": warnings,
        "freed_bytes": sum(int(item.get("size") or 0) for item in deleted),
    }


def plan_prune(
    *,
    keep_latest: int | None = 50,
    max_age_days: int | None = 90,
    include_invalid: bool = False,
    now: datetime | None = None,
) -> dict[str, Any]:
    return plan_prune_snapshots(
        keep_latest=keep_latest,
        max_age_days=max_age_days,
        include_invalid=include_invalid,
        now=now,
    )


def _inventory_signature(inventory: Any) -> list[tuple[str, int, str]]:
    if not isinstance(inventory, list):
        raise ValueError("Snapshot prune plan inventory is invalid.")
    signature = []
    for item in inventory:
        if not isinstance(item, dict):
            raise ValueError("Snapshot prune plan inventory is invalid.")
        filename = str(item.get("filename") or "")
        size = item.get("size")
        sha256 = str(item.get("sha256") or "")
        if not filename or not filename.endswith(".json") or not isinstance(size, int) or not sha256:
            raise ValueError("Snapshot prune plan inventory is invalid.")
        snapshot_path(filename=filename)
        signature.append((filename, size, sha256))
    return sorted(signature)


def _verify_prune_plan(plan: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(plan, dict) or plan.get("version") != 1:
        raise ValueError("Snapshot prune plan is invalid or unsupported.")
    expected_inventory = _inventory_signature(plan.get("inventory"))
    current_inventory = _inventory_signature(_snapshot_inventory())
    if current_inventory != expected_inventory:
        raise ValueError("Snapshot prune plan is stale; snapshot inventory changed before pruning.")
    deleted = plan.get("deleted")
    if not isinstance(deleted, list):
        raise ValueError("Snapshot prune plan deleted list is invalid.")
    planned_files: list[dict[str, Any]] = []
    for item in deleted:
        if not isinstance(item, dict):
            raise ValueError("Snapshot prune plan deleted list is invalid.")
        filename = str(item.get("filename") or "")
        size = item.get("size")
        sha256 = str(item.get("sha256") or "")
        if not filename or not filename.endswith(".json") or not isinstance(size, int) or not sha256:
            raise ValueError("Snapshot prune plan deleted item is invalid.")
        path = snapshot_path(filename=filename)
        if path.name != filename:
            raise ValueError("Snapshot prune plan filename changed.")
        if not path.exists():
            raise ValueError(f"Planned snapshot disappeared: {filename}")
        if not path.is_file():
            raise ValueError(f"Planned snapshot is not a regular file: {filename}")
        identity = _file_identity(path)
        if identity["size"] != size or identity["sha256"] != sha256:
            raise ValueError(f"Planned snapshot changed before pruning: {filename}")
        planned_files.append(item)
    return planned_files


def execute_prune_snapshot_plan(plan: dict[str, Any]) -> dict[str, Any]:
    planned_files = _verify_prune_plan(plan)
    for item in planned_files:
        snapshot_path(filename=item["filename"]).unlink()
    policy = plan.get("policy") if isinstance(plan.get("policy"), dict) else {}
    result = deepcopy(plan)
    activity_history.log_activity(
        "project_snapshots_pruned",
        "success",
        f"Pruned {len(planned_files)} project registry snapshot(s)",
        {
            "deleted": [item["filename"] for item in planned_files],
            "deleted_count": len(planned_files),
            "freed_bytes": result.get("freed_bytes", 0),
            "keep_latest": policy.get("keep_latest"),
            "max_age_days": policy.get("max_age_days"),
            "include_invalid": policy.get("include_invalid", False),
        },
    )
    return result


def prune_snapshots(
    *,
    plan: dict[str, Any] | None = None,
    keep_latest: int | None = 50,
    max_age_days: int | None = 90,
    dry_run: bool = False,
    include_invalid: bool = False,
) -> dict[str, Any]:
    if dry_run:
        return plan_prune_snapshots(
            keep_latest=keep_latest,
            max_age_days=max_age_days,
            include_invalid=include_invalid,
        )
    if plan is None:
        raise ValueError("Approved snapshot prune execution requires an immutable plan.")
    return execute_prune_snapshot_plan(plan)


def prune_snapshots_immediate(
    *,
    keep_latest: int | None = 50,
    max_age_days: int | None = 90,
    include_invalid: bool = False,
) -> dict[str, Any]:
    plan = plan_prune_snapshots(
        keep_latest=keep_latest,
        max_age_days=max_age_days,
        include_invalid=include_invalid,
    )
    return execute_prune_snapshot_plan(plan)
