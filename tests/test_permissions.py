import json

from void.core import permissions


def test_old_approval_records_without_metadata_still_load(temp_memory_dir):
    approvals_path = temp_memory_dir / "pending_approvals.json"
    approvals_path.write_text(
        json.dumps(
            [
                {
                    "id": "old-record",
                    "action": "read_facts",
                    "arguments": {},
                    "reason": "legacy approval",
                    "created_at": "2026-01-01T00:00:00",
                }
            ]
        ),
        encoding="utf-8",
    )

    approvals = permissions.list_approvals()
    action = permissions.approve("old-record")

    assert approvals[0]["action"] == "read_facts"
    assert "category" not in approvals[0]
    assert "risk_level" not in approvals[0]
    assert action is not None
    assert action.action == "read_facts"
    assert action.arguments == {}
    assert action.reason == "legacy approval"
