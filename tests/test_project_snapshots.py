from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timedelta
from typing import Any

from void.core import activity_history, project_context, project_snapshots
from void.core.permissions import approve, clear_approval, list_approvals
from void.core.types import AgentAction
from void.tools.builtin import build_registry


def _registry_payload() -> dict[str, Any]:
    return {
        "current_project": "void",
        "unknown_root": {"survives": True},
        "projects": [
            {
                "id": "void",
                "name": "Void",
                "aliases": ["void"],
                "root_path": ".",
                "workspace": {"terminal": {"command": "cd {root}", "custom": "keep"}},
                "unknown_project": ["keep"],
            },
            {
                "id": "docs",
                "name": "Docs",
                "aliases": ["manual"],
                "root_path": "docs",
                "nullable": None,
            },
        ],
    }


def _save_registry(payload: dict[str, Any] | None = None) -> None:
    project_context.save_project_context(payload or _registry_payload())


def _approve_latest(registry):
    approval = list_approvals()[0]
    action = approve(approval["id"])
    assert action is not None
    result = registry.execute(action, bypass_confirmation=True)
    clear_approval(approval["id"])
    return result


def _snapshot_payload(registry_payload: dict[str, Any], *, snapshot_id: str = "snap") -> dict[str, Any]:
    return {
        "snapshot": {
            "version": 1,
            "id": snapshot_id,
            "created_at": "2026-07-24T12:00:00.000001+03:00",
            "reason": "manual",
            "source_action": "manual",
            "metadata": {
                "project_count": len(registry_payload.get("projects", [])),
                "current_project": registry_payload.get("current_project", ""),
            },
        },
        "registry": deepcopy(registry_payload),
    }


def test_manual_snapshot_requires_approval_and_preserves_exact_registry(monkeypatch):
    _save_registry()
    registry = build_registry()
    monkeypatch.setattr(
        project_snapshots,
        "_now",
        lambda: datetime(2026, 7, 24, 12, 30, 45, 123456).astimezone(),
    )
    raw = json.loads(project_context.PROJECT_CONTEXT_PATH.read_text(encoding="utf-8"))

    response = registry.execute(
        AgentAction("create_project_snapshot", {"reason": "before experimenting"}, "Create.")
    )
    assert response.ok is True
    assert list(project_snapshots.PROJECT_SNAPSHOT_DIR.glob("*.json")) == []

    approved = _approve_latest(registry)
    assert approved.ok is True
    snapshot_path = project_snapshots.PROJECT_SNAPSHOT_DIR / approved.data["filename"]
    payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
    assert payload["registry"] == raw
    assert payload["snapshot"]["reason"] == "before experimenting"
    assert approved.data["filename"].endswith("_before-experimenting.json")
    assert activity_history.get_last_activity()["activity_type"] == "project_snapshot_created"


def test_manual_snapshot_rejection_writes_nothing():
    _save_registry()
    registry = build_registry()
    response = registry.execute(AgentAction("create_project_snapshot", {}, "Create."))
    assert response.ok is True
    clear_approval(list_approvals()[0]["id"])
    assert list(project_snapshots.PROJECT_SNAPSHOT_DIR.glob("*.json")) == []


def test_snapshot_filename_collisions_and_exclusive_retry(monkeypatch):
    _save_registry()
    fixed = datetime(2026, 7, 24, 12, 0, 0, 1).astimezone()
    monkeypatch.setattr(project_snapshots, "_now", lambda: fixed)
    first = project_snapshots.create_snapshot(project_context._read_project_context_raw(), reason="update project")
    second = project_snapshots.create_snapshot(project_context._read_project_context_raw(), reason="update project")
    assert [first["filename"], second["filename"]] == [
        "2026-07-24_12-00-00-000001_update-project.json",
        "2026-07-24_12-00-00-000001_update-project-2.json",
    ]

    original_link = project_snapshots.os.link
    calls: list[str] = []

    def racing_link(source, destination):
        calls.append(project_snapshots.Path(destination).name)
        if len(calls) == 1:
            raise FileExistsError
        return original_link(source, destination)

    monkeypatch.setattr(project_snapshots.os, "link", racing_link)
    third = project_snapshots.create_snapshot(project_context._read_project_context_raw(), reason="update project")
    assert third["filename"] == "2026-07-24_12-00-00-000001_update-project-3.json"
    assert calls == [
        "2026-07-24_12-00-00-000001_update-project.json",
        "2026-07-24_12-00-00-000001_update-project-2.json",
        "2026-07-24_12-00-00-000001_update-project-3.json",
    ]


def test_snapshot_validation_listing_and_path_traversal():
    _save_registry()
    valid = project_snapshots.create_snapshot(project_context._read_project_context_raw(), reason="manual")
    malformed = project_snapshots.PROJECT_SNAPSHOT_DIR / "malformed.json"
    malformed.write_text("{", encoding="utf-8")

    listed = project_snapshots.list_snapshots()
    assert [item["filename"] for item in listed] == [valid["filename"], "malformed.json"]
    assert listed[1]["valid"] is False
    assert project_snapshots.validate_snapshot(filename=valid["filename"])["ok"] is True
    invalid = project_snapshots.validate_snapshot(filename="malformed.json")
    assert invalid["ok"] is False
    assert invalid["errors"]

    for kwargs in ({"filename": "../projects.json"}, {"snapshot_id": "../projects"}):
        try:
            project_snapshots.validate_snapshot(**kwargs)
        except ValueError as error:
            assert "must not contain directories" in str(error) or "stay inside" in str(error)
        else:
            raise AssertionError("Traversal should be rejected")


def test_snapshot_validation_rejects_invalid_envelopes():
    cases = {
        "root.json": [],
        "missing-envelope.json": {"current_project": "void", "projects": []},
        "unsupported.json": {
            **_snapshot_payload(_registry_payload()),
            "snapshot": {**_snapshot_payload(_registry_payload())["snapshot"], "version": 2},
        },
        "missing-id.json": {
            **_snapshot_payload(_registry_payload()),
            "snapshot": {**_snapshot_payload(_registry_payload())["snapshot"], "id": ""},
        },
        "missing-created.json": {
            **_snapshot_payload(_registry_payload()),
            "snapshot": {**_snapshot_payload(_registry_payload())["snapshot"], "created_at": ""},
        },
        "bad-metadata.json": {
            **_snapshot_payload(_registry_payload()),
            "snapshot": {**_snapshot_payload(_registry_payload())["snapshot"], "metadata": []},
        },
        "duplicate-id.json": _snapshot_payload(
            {
                "current_project": "void",
                "projects": [
                    {"id": "void", "name": "Void", "root_path": "."},
                    {"id": "VOID", "name": "Void 2", "root_path": "."},
                ],
            }
        ),
        "duplicate-alias.json": _snapshot_payload(
            {
                "current_project": "void",
                "projects": [
                    {"id": "void", "name": "Void", "aliases": ["same"], "root_path": "."},
                    {"id": "docs", "name": "Docs", "aliases": ["SAME"], "root_path": "docs"},
                ],
            }
        ),
        "bad-current.json": _snapshot_payload(
            {
                "current_project": "missing",
                "projects": [{"id": "void", "name": "Void", "root_path": "."}],
            }
        ),
    }
    project_snapshots.PROJECT_SNAPSHOT_DIR.mkdir(parents=True)
    for filename, payload in cases.items():
        (project_snapshots.PROJECT_SNAPSHOT_DIR / filename).write_text(
            json.dumps(payload),
            encoding="utf-8",
        )
        result = project_snapshots.validate_snapshot(filename=filename)
        assert result["ok"] is False, filename
        assert result["errors"], filename


def test_snapshot_diff_includes_known_unknown_nested_ordered_list_and_missing():
    before = _registry_payload()
    after = deepcopy(before)
    after["current_project"] = "docs"
    after["unknown_root"] = {"survives": False}
    after["new_root"] = None
    after["projects"][0]["name"] = "Void App"
    after["projects"][0]["workspace"]["terminal"]["command"] = "cd {root} && make dev"
    after["projects"][0]["unknown_project"] = ["keep", "changed"]
    after["projects"][1].pop("nullable")
    after["projects"].append({"id": "api", "name": "API", "root_path": "api"})
    after["projects"] = [project for project in after["projects"] if project["id"] != "docs"]
    before_copy = deepcopy(before)
    after_copy = deepcopy(after)

    diff = project_snapshots.diff_registries(before, after)

    assert diff["current_project"]["changed"] is True
    assert diff["counts"] == {"added": 1, "removed": 1, "updated": 1, "unchanged": 0}
    assert [item["id"] for item in diff["added"]] == ["api"]
    assert [item["id"] for item in diff["removed"]] == ["docs"]
    paths = [change["path"] for change in diff["updated"][0]["changes"]]
    assert paths == sorted(paths)
    assert "workspace.terminal.command" in paths
    assert "unknown_project" in paths
    assert any(change["path"] == "new_root" and change["before"] == {"missing": True} for change in diff["root_changes"])
    assert before == before_copy
    assert after == after_copy


def test_automatic_snapshot_and_noop_behavior(monkeypatch):
    _save_registry()
    registry = build_registry()
    original_save = project_context.save_project_context
    save_calls: list[dict[str, Any]] = []

    def tracking_save(payload):
        save_calls.append(deepcopy(payload))
        return original_save(payload)

    monkeypatch.setattr(project_context, "save_project_context", tracking_save)
    response = registry.execute(
        AgentAction("update_project", {"project_id": "void", "project": {"name": "Void 2"}}, "Update.")
    )
    assert response.ok is True
    approved = _approve_latest(registry)
    assert approved.ok is True
    assert len(save_calls) == 1
    snapshot_files = list(project_snapshots.PROJECT_SNAPSHOT_DIR.glob("*.json"))
    assert len(snapshot_files) == 1
    snapshot_payload = json.loads(snapshot_files[0].read_text(encoding="utf-8"))
    assert snapshot_payload["registry"]["projects"][0]["name"] == "Void"
    assert approved.data["snapshot"]["id"] == snapshot_files[0].stem

    noop = project_context.commit_project_registry_mutation(
        action="noop",
        previous_payload=project_context._read_project_context_raw(),
        final_payload=project_context._read_project_context_raw(),
        activity_type="project_update",
        activity_summary="Noop",
        activity_metadata={},
    )
    assert noop["changed"] is False
    assert noop["snapshot"] is None
    assert len(list(project_snapshots.PROJECT_SNAPSHOT_DIR.glob("*.json"))) == 1


def test_snapshot_restore_requires_approval_and_restores_losslessly(monkeypatch):
    _save_registry()
    registry = build_registry()
    original_raw = project_context._read_project_context_raw()
    snapshot = project_snapshots.create_snapshot(original_raw, reason="manual")
    project_context.save_project_context(
        {
            "current_project": "changed",
            "projects": [{"id": "changed", "name": "Changed", "root_path": "."}],
        }
    )
    save_calls: list[dict[str, Any]] = []
    original_save = project_context.save_project_context

    def tracking_save(payload):
        save_calls.append(deepcopy(payload))
        return original_save(payload)

    request = registry.execute(AgentAction("restore_project_snapshot", {"id": snapshot["id"]}, "Restore."))
    assert request.ok is True
    monkeypatch.setattr(project_context, "save_project_context", tracking_save)
    restored = _approve_latest(registry)
    raw_after = json.loads(project_context.PROJECT_CONTEXT_PATH.read_text(encoding="utf-8"))

    assert restored.ok is True
    assert len(save_calls) == 1
    assert raw_after == original_raw
    assert restored.data["restored_snapshot"]["id"] == snapshot["id"]
    assert restored.data["pre_restore_snapshot"]["id"] != snapshot["id"]
    restore_activity = activity_history.get_last_activity()
    assert restore_activity["activity_type"] == "project_snapshot_restored"
    assert restore_activity["metadata"]["restored_snapshot_id"] == snapshot["id"]
    assert restore_activity["metadata"]["pre_restore_snapshot_id"] == restored.data["pre_restore_snapshot"]["id"]


def test_snapshot_restore_invalid_execution_payload_writes_nothing(monkeypatch):
    _save_registry()
    registry = build_registry()
    snapshot = project_snapshots.create_snapshot(project_context._read_project_context_raw(), reason="manual")
    request = registry.execute(AgentAction("restore_project_snapshot", {"id": snapshot["id"]}, "Restore."))
    assert request.ok is True
    path = project_snapshots.PROJECT_SNAPSHOT_DIR / snapshot["filename"]
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["registry"]["current_project"] = "missing"
    path.write_text(json.dumps(payload), encoding="utf-8")
    save_calls: list[dict[str, Any]] = []
    monkeypatch.setattr(project_context, "save_project_context", lambda payload: save_calls.append(payload) or payload)

    result = _approve_latest(registry)
    assert result.ok is False
    assert save_calls == []


def test_snapshot_delete_requires_approval_and_prune_policies(monkeypatch):
    _save_registry()
    registry = build_registry()
    base = datetime(2026, 7, 24, 12, 0, 0).astimezone()
    snapshots = []
    for index in range(4):
        monkeypatch.setattr(project_snapshots, "_now", lambda index=index: base - timedelta(days=index * 10))
        snapshots.append(project_snapshots.create_snapshot(project_context._read_project_context_raw(), reason=f"s{index}"))
    invalid = project_snapshots.PROJECT_SNAPSHOT_DIR / "invalid.json"
    invalid.write_text("{", encoding="utf-8")

    delete_request = registry.execute(AgentAction("delete_project_snapshot", {"id": snapshots[0]["id"]}, "Delete."))
    assert delete_request.ok is True
    clear_approval(list_approvals()[0]["id"])
    assert (project_snapshots.PROJECT_SNAPSHOT_DIR / snapshots[0]["filename"]).exists()

    delete_request = registry.execute(AgentAction("delete_project_snapshot", {"id": snapshots[0]["id"]}, "Delete."))
    assert delete_request.ok is True
    deleted = _approve_latest(registry)
    assert deleted.ok is True
    assert not (project_snapshots.PROJECT_SNAPSHOT_DIR / snapshots[0]["filename"]).exists()

    monkeypatch.setattr(project_snapshots, "_now", lambda: base)
    preview = project_snapshots.prune_snapshots(keep_latest=1, max_age_days=15, dry_run=True)
    assert [item["filename"] for item in preview["deleted"]] == [
        snapshots[2]["filename"],
        snapshots[3]["filename"],
    ]
    assert any("malformed" in warning for warning in preview["warnings"])
    changed = project_snapshots.PROJECT_SNAPSHOT_DIR / preview["deleted"][0]["filename"]
    plan = project_snapshots.plan_prune(keep_latest=1, max_age_days=15)
    changed.write_text(changed.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    monkeypatch.setattr(project_snapshots, "plan_prune", lambda **kwargs: plan)
    try:
        project_snapshots.prune_snapshots(keep_latest=1, max_age_days=15)
    except ValueError as error:
        assert "changed before pruning" in str(error)
    else:
        raise AssertionError("Changed planned file should fail safely")
