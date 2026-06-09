"""Tools for requesting and tracking built-in capabilities."""

from void.core.types import ToolDefinition, ToolResult
from void.core.capabilities import (
    add_requested_capability,
    list_capabilities as load_capabilities,
    mark_capability_installed as mark_installed,
    reject_capability,
)


def _format_record(record: dict) -> str:
    name = record.get("name", "unknown")
    record_id = record.get("id", "")
    description = record.get("description", "")
    reason = record.get("reason")
    suffix = f" ({record_id})" if record_id else ""
    line = f"- {name}{suffix}"
    if description:
        line += f": {description}"
    if reason:
        line += f" [reason: {reason}]"
    return line


def _format_section(title: str, records: list[dict]) -> str:
    if not records:
        return f"{title}:\n- None"
    return f"{title}:\n" + "\n".join(_format_record(record) for record in records)


def list_capabilities() -> ToolResult:
    capabilities = load_capabilities()
    content = "\n\n".join(
        (
            _format_section("Installed", capabilities["installed"]),
            _format_section("Requested", capabilities["requested"]),
            _format_section("Rejected", capabilities["rejected"]),
        )
    )
    return ToolResult(ok=True, content=content, data=capabilities)


def add_capability_request(
    name: str,
    description: str,
    problem: str,
    reason: str,
) -> ToolResult:
    result = add_requested_capability(
        name=name,
        description=description,
        problem=problem,
        reason=reason,
    )
    if not result.get("ok"):
        return ToolResult(ok=False, content=str(result.get("error", "Capability request failed.")))

    record = result["record"]
    prefix = "Capability request already exists." if result.get("duplicate") else (
        "Capability request saved."
    )
    content = (
        f"{prefix}\n\n"
        f"Name: {record.get('name')}\n"
        f"ID: {record.get('id')}\n"
        f"Status: {record.get('status')}\n"
        f"Description: {record.get('description')}\n"
        f"Problem: {record.get('problem')}\n"
        f"Reason: {record.get('reason')}"
    )
    return ToolResult(ok=True, content=content, data={"record": record}, terminal=True)


def mark_capability_installed(name_or_id: str) -> ToolResult:
    result = mark_installed(name_or_id)
    if not result.get("ok"):
        return ToolResult(ok=False, content=str(result.get("error", "Capability not found.")))

    record = result["record"]
    prefix = "Capability is already installed." if result.get("duplicate") else (
        "Capability marked as installed."
    )
    return ToolResult(
        ok=True,
        content=f"{prefix}\n\nName: {record.get('name')}\nID: {record.get('id')}",
        data={"record": record},
        terminal=True,
    )


def reject_capability_request(name_or_id: str, reason: str) -> ToolResult:
    result = reject_capability(name_or_id, reason)
    if not result.get("ok"):
        return ToolResult(ok=False, content=str(result.get("error", "Capability not found.")))

    record = result["record"]
    return ToolResult(
        ok=True,
        content=(
            "Capability request rejected.\n\n"
            f"Name: {record.get('name')}\n"
            f"ID: {record.get('id')}\n"
            f"Reason: {record.get('reason')}"
        ),
        data={"record": record},
        terminal=True,
    )


def request_capability(
    name: str,
    problem: str,
    why_self_tool_not_enough: str,
    suggested_function_signature: str,
    suggested_behavior: str,
    usage_example: str,
) -> ToolResult:
    description = suggested_behavior.strip() or suggested_function_signature.strip()
    reason = why_self_tool_not_enough.strip()
    result = add_requested_capability(
        name=name,
        description=description,
        problem=problem,
        reason=reason,
    )
    saved_note = "Capability request saved to memory."
    if not result.get("ok"):
        saved_note = f"Capability request was not saved: {result.get('error')}"
    elif result.get("duplicate"):
        saved_note = "Capability request already exists in memory."

    content = (
        "Void requests a new built-in capability.\n\n"
        f"{saved_note}\n\n"
        f"Name:\n{name}\n\n"
        f"Problem:\n{problem}\n\n"
        f"Why existing tools are not enough:\n{why_self_tool_not_enough}\n\n"
        f"Suggested function signature:\n{suggested_function_signature}\n\n"
        f"Suggested behavior:\n{suggested_behavior}\n\n"
        f"Usage example:\n{usage_example}"
    )
    return ToolResult(ok=True, content=content, terminal=True)


def definitions() -> list[ToolDefinition]:
    return [
        ToolDefinition(
            "list_capabilities",
            "List installed, requested, and rejected capabilities.",
            list_capabilities,
            terminal=True,
            requires_confirmation=False,
        ),
        ToolDefinition(
            "add_capability_request",
            "Save a request for a new built-in capability.",
            add_capability_request,
            terminal=True,
            requires_confirmation=True,
        ),
        ToolDefinition(
            "mark_capability_installed",
            "Move a requested capability to installed capabilities.",
            mark_capability_installed,
            terminal=True,
            requires_confirmation=True,
        ),
        ToolDefinition(
            "reject_capability_request",
            "Move a requested capability to rejected capabilities.",
            reject_capability_request,
            terminal=True,
            requires_confirmation=True,
        ),
        ToolDefinition(
            "request_capability",
            "Request a new safe built-in capability when current tools are insufficient.",
            request_capability,
            terminal=True,
            requires_confirmation=True,
        )
    ]
