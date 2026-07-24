"""FastAPI server for the Void backend."""

import os
from contextlib import asynccontextmanager
from dataclasses import asdict
from typing import Any

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from void.__version__ import __version__
from void.api.auth import get_api_token, require_api_token
from void.api.dependencies import get_agent, get_skill_registry, get_tool_registry
from void.api.schemas import (
    ActivityResponse,
    ApprovalResponse,
    BrowserFillRequest,
    BrowserLinksRequest,
    BrowserScreenshotRequest,
    BrowserSessionFillRequest,
    BrowserSessionOpenRequest,
    BrowserSessionResponse,
    BrowserSessionsResponse,
    BrowserSessionSelectorRequest,
    BrowserSessionWaitRequest,
    BrowserSelectorRequest,
    BrowserTaskRequest,
    BrowserTextRequest,
    BrowserUrlRequest,
    BrowserWaitRequest,
    CapabilitiesResponse,
    ChatRequest,
    ChatResponse,
    CreateScheduledTaskRequest,
    DeleteProjectRequest,
    ErrorResponse,
    GitCommitRequest,
    HealthResponse,
    LastActivityResponse,
    ClarificationRespondRequest,
    ClarificationResponse,
    MemoryResponse,
    OpenProjectRepoRequest,
    OpenProjectWorkspaceRequest,
    ProjectBackupRequest,
    ProjectBackupsResponse,
    ProjectBackupValidationResponse,
    CreateProjectSnapshotRequest,
    ProjectSnapshotDiffResponse,
    ProjectSnapshotPruneRequest,
    ProjectSnapshotRequest,
    ProjectSnapshotsResponse,
    ProjectSnapshotValidationResponse,
    ProjectExportResponse,
    ProjectImportRequest,
    ProjectImportValidationResponse,
    ProjectRegistryRequest,
    ProjectResponse,
    UpdateWorkspacePreferencesRequest,
    WorkspacePreferencesResponse,
    CurrentProjectResponse,
    ProjectCommandsResponse,
    ProjectDescriptionResponse,
    ProjectsResponse,
    RunProjectCommandRequest,
    ScheduledTasksResponse,
    SchedulerRunOnceResponse,
    SchedulerStatusResponse,
    SetCurrentProjectRequest,
    SkillsResponse,
)
from void.core.agent import Agent
from void.core import browser_sessions
from void.core import workspace_preferences
from void.core.capabilities import list_capabilities
from void.core.clarification import load_pending_clarification
from void.core.permissions import approve, clear_approval, list_approvals, reject
from void.core.registry import ToolRegistry
from void.core.safety import MEMORY_DIR, ensure_memory_files
from void.core.scheduler import list_tasks
from void.core.scheduler_worker import SchedulerWorker
from void.core.types import AgentAction, ToolResult
from void.skills.registry import SkillRegistry

API_VERSION = __version__
SCHEDULER_WORKER_ENABLED_ENV = "VOID_SCHEDULER_WORKER_ENABLED"
SCHEDULER_WORKER_INTERVAL_ENV = "VOID_SCHEDULER_WORKER_INTERVAL"


def _env_enabled(name: str, default: bool = True) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return max(1, int(value))
    except ValueError:
        print(
            f"WARNING: Invalid {name}={value!r}; using {default}.",
            flush=True,
        )
        return default


if get_api_token() is None:
    print(
        "WARNING: VOID_API_TOKEN is not set. API token auth is disabled for local dev mode.",
        flush=True,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    enabled = _env_enabled(SCHEDULER_WORKER_ENABLED_ENV, True)
    interval_seconds = _env_int(SCHEDULER_WORKER_INTERVAL_ENV, 60)
    worker = SchedulerWorker(interval_seconds=interval_seconds)
    app.state.scheduler_worker_enabled = enabled
    app.state.scheduler_worker = worker

    if enabled:
        worker.start()
        print(
            f"Scheduler worker started with interval {interval_seconds}s.",
            flush=True,
        )
    else:
        print(
            "WARNING: Scheduler worker disabled by VOID_SCHEDULER_WORKER_ENABLED.",
            flush=True,
        )

    try:
        yield
    finally:
        worker.stop()
        try:
            browser_sessions.close_all_sessions()
        except Exception as error:
            print(
                f"WARNING: Failed to close browser sessions during shutdown: {error}",
                flush=True,
            )


app = FastAPI(
    title="Void API",
    version=API_VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content=ErrorResponse(ok=False, error=str(exc), message=str(exc)).model_dump(),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(ok=False, error=str(exc), message=str(exc)).model_dump(),
    )


def _error(error: Exception | str) -> ErrorResponse:
    message = str(error)
    return ErrorResponse(ok=False, error=message, message=message)


def _result_type(action: str | None, result: ToolResult) -> str:
    data = result.data or {}
    if "approval_id" in data:
        return "approval"
    if action in {"run_project_command_visible", "open_project_workspace"} and (
        data.get("target") == "terminal" or data.get("mode") == "visible_terminal"
    ):
        return "terminal_launch_result"
    if action == "run_project_command" or "command_key" in data:
        return "command_result"
    if action in {"open_project_repo_in_browser", "browser_open_session"} or (
        "session_id" in data and "url" in data
    ):
        return "browser_result"
    return "message"


def _approval_response(
    result: ToolResult,
    action: str | None = None,
) -> ApprovalResponse:
    return ApprovalResponse(
        ok=result.ok,
        message=result.content,
        result_type=_result_type(action, result),
        data=result.data,
    )


def _read_memory_file(filename: str) -> MemoryResponse | ErrorResponse:
    try:
        ensure_memory_files()
        content = (MEMORY_DIR / filename).read_text(encoding="utf-8")
        return MemoryResponse(ok=True, content=content)
    except Exception as error:
        return _error(error)


def _execute_api_tool(
    registry: ToolRegistry,
    action: str,
    arguments: dict[str, Any],
    reason: str = "API request.",
) -> ApprovalResponse | ErrorResponse:
    try:
        result = registry.execute(AgentAction(action, arguments, reason))
        return _approval_response(result, action)
    except Exception as error:
        return _error(error)


def _execute_read_api_tool(
    registry: ToolRegistry,
    action: str,
    arguments: dict[str, Any] | None = None,
) -> Any:
    result = registry.execute(AgentAction(action, arguments or {}, "API request."))
    if not result.ok:
        raise ValueError(result.content)
    return result


@app.get("/health", response_model=HealthResponse | ErrorResponse)
def health() -> HealthResponse | ErrorResponse:
    try:
        return HealthResponse(ok=True, service="Void API", version=API_VERSION)
    except Exception as error:
        return _error(error)


@app.post("/chat", response_model=ChatResponse | ErrorResponse)
def chat(
    request: ChatRequest,
    _: None = Depends(require_api_token),
    agent: Agent = Depends(get_agent),
) -> ChatResponse | ErrorResponse:
    try:
        result = agent.handle_result(request.message)
        clarification = (
            asdict(result.clarification) if result.clarification is not None else None
        )
        return ChatResponse(
            ok=True,
            response=result.content,
            result_type=result.kind,
            clarification=clarification,
            message=result.content,
            data=result.tool_result.data if result.tool_result is not None else None,
        )
    except Exception as error:
        return _error(error)


@app.get("/clarification", response_model=ClarificationResponse | ErrorResponse)
def clarification(
    _: None = Depends(require_api_token),
) -> ClarificationResponse | ErrorResponse:
    try:
        return ClarificationResponse(ok=True, pending=load_pending_clarification())
    except Exception as error:
        return _error(error)


@app.post("/clarification/respond", response_model=ChatResponse | ErrorResponse)
def respond_to_clarification(
    request: ClarificationRespondRequest,
    _: None = Depends(require_api_token),
    agent: Agent = Depends(get_agent),
) -> ChatResponse | ErrorResponse:
    try:
        if load_pending_clarification() is None:
            return ChatResponse(
                ok=True,
                response="No pending clarification.",
                result_type="final_answer",
            )
        result = agent.handle_result(request.answer)
        clarification = (
            asdict(result.clarification) if result.clarification is not None else None
        )
        return ChatResponse(
            ok=True,
            response=result.content,
            result_type=result.kind,
            clarification=clarification,
            message=result.content,
            data=result.tool_result.data if result.tool_result is not None else None,
        )
    except Exception as error:
        return _error(error)


@app.get("/skills", response_model=SkillsResponse | ErrorResponse)
def skills(
    _: None = Depends(require_api_token),
    skill_registry: SkillRegistry = Depends(get_skill_registry),
) -> SkillsResponse | ErrorResponse:
    try:
        payload: list[dict[str, Any]] = [
            {
                "name": skill.name,
                "description": skill.description,
                "keywords": skill.keywords,
            }
            for skill in skill_registry.list_skills()
        ]
        return SkillsResponse(ok=True, skills=payload)
    except Exception as error:
        return _error(error)


@app.get("/capabilities", response_model=CapabilitiesResponse | ErrorResponse)
def capabilities(
    _: None = Depends(require_api_token),
) -> CapabilitiesResponse | ErrorResponse:
    try:
        records = list_capabilities()
        return CapabilitiesResponse(
            ok=True,
            installed=records["installed"],
            requested=records["requested"],
            rejected=records["rejected"],
        )
    except Exception as error:
        return _error(error)


@app.get("/activity", response_model=ActivityResponse | ErrorResponse)
def activity(
    _: None = Depends(require_api_token),
    registry: ToolRegistry = Depends(get_tool_registry),
) -> ActivityResponse | ErrorResponse:
    try:
        result = _execute_read_api_tool(registry, "list_recent_activity")
        return ActivityResponse(ok=True, activities=(result.data or {}).get("activities", []))
    except Exception as error:
        return _error(error)


@app.get("/activity/latest", response_model=LastActivityResponse | ErrorResponse)
def latest_activity(
    _: None = Depends(require_api_token),
    registry: ToolRegistry = Depends(get_tool_registry),
) -> LastActivityResponse | ErrorResponse:
    try:
        result = _execute_read_api_tool(registry, "get_last_activity")
        return LastActivityResponse(ok=True, activity=(result.data or {}).get("activity"))
    except Exception as error:
        return _error(error)


@app.post("/activity/clear", response_model=ApprovalResponse | ErrorResponse)
def clear_activity(
    _: None = Depends(require_api_token),
    registry: ToolRegistry = Depends(get_tool_registry),
) -> ApprovalResponse | ErrorResponse:
    return _execute_api_tool(registry, "clear_activity_history", {})


@app.post("/activity/replay/latest", response_model=ApprovalResponse | ErrorResponse)
def replay_latest_activity(
    _: None = Depends(require_api_token),
    registry: ToolRegistry = Depends(get_tool_registry),
) -> ApprovalResponse | ErrorResponse:
    return _execute_api_tool(registry, "repeat_last_activity", {})


@app.post("/activity/replay/{activity_id}", response_model=ApprovalResponse | ErrorResponse)
def replay_activity(
    activity_id: str,
    _: None = Depends(require_api_token),
    registry: ToolRegistry = Depends(get_tool_registry),
) -> ApprovalResponse | ErrorResponse:
    return _execute_api_tool(registry, "replay_activity", {"activity_id": activity_id})


@app.get("/projects", response_model=ProjectsResponse | ErrorResponse)
def projects(
    _: None = Depends(require_api_token),
    registry: ToolRegistry = Depends(get_tool_registry),
) -> ProjectsResponse | ErrorResponse:
    try:
        result = _execute_read_api_tool(registry, "list_projects")
        data = result.data or {}
        return ProjectsResponse(
            ok=True,
            projects=data.get("projects", []),
            current_project=data.get("current_project"),
        )
    except Exception as error:
        return _error(error)


@app.post("/projects", response_model=ApprovalResponse | ErrorResponse)
def create_project_entry(
    request: ProjectRegistryRequest,
    _: None = Depends(require_api_token),
    registry: ToolRegistry = Depends(get_tool_registry),
) -> ApprovalResponse | ErrorResponse:
    project = request.project
    arguments = {"project": project}
    if request.duplicate_source_id:
        arguments["duplicate_source_id"] = request.duplicate_source_id
    return _execute_api_tool(
        registry,
        "create_project",
        arguments,
        (
            "Create project:\n\n"
            f"Project: {project.get('name') or project.get('id') or ''}\n"
            f"Root path: {project.get('root_path') or ''}"
        ),
    )


@app.get("/projects/current", response_model=CurrentProjectResponse | ErrorResponse)
def current_project(
    _: None = Depends(require_api_token),
    registry: ToolRegistry = Depends(get_tool_registry),
) -> CurrentProjectResponse | ErrorResponse:
    try:
        result = _execute_read_api_tool(registry, "get_current_project")
        return CurrentProjectResponse(ok=True, project=(result.data or {}).get("project", {}))
    except Exception as error:
        return _error(error)


@app.post("/projects/current", response_model=ApprovalResponse | ErrorResponse)
def set_current_project(
    request: SetCurrentProjectRequest,
    _: None = Depends(require_api_token),
    registry: ToolRegistry = Depends(get_tool_registry),
) -> ApprovalResponse | ErrorResponse:
    return _execute_api_tool(registry, "set_current_project", {"project": request.project})


@app.get("/projects/current/export", response_model=ProjectExportResponse | ErrorResponse)
def export_current_project(
    _: None = Depends(require_api_token),
    registry: ToolRegistry = Depends(get_tool_registry),
) -> ProjectExportResponse | ErrorResponse:
    try:
        result = _execute_read_api_tool(registry, "export_project", {"current": True})
        return ProjectExportResponse(ok=True, export=(result.data or {}).get("export", {}))
    except Exception as error:
        return _error(error)


@app.get("/projects/export/all", response_model=ProjectExportResponse | ErrorResponse)
def export_all_projects(
    _: None = Depends(require_api_token),
    registry: ToolRegistry = Depends(get_tool_registry),
) -> ProjectExportResponse | ErrorResponse:
    try:
        result = _execute_read_api_tool(registry, "export_projects")
        return ProjectExportResponse(ok=True, export=(result.data or {}).get("export", {}))
    except Exception as error:
        return _error(error)


@app.post(
    "/projects/import/validate",
    response_model=ProjectImportValidationResponse | ErrorResponse,
)
def validate_project_import(
    request: ProjectImportRequest,
    _: None = Depends(require_api_token),
    registry: ToolRegistry = Depends(get_tool_registry),
) -> ProjectImportValidationResponse | ErrorResponse:
    try:
        arguments = {
            "source": request.source,
            "path": request.path,
            "resolution": request.resolution,
        }
        result = registry.execute(
            AgentAction("validate_project_import", arguments, "API request.")
        )
        return ProjectImportValidationResponse(
            ok=result.ok,
            preview=(result.data or {}).get("preview", {}),
        )
    except Exception as error:
        return _error(error)


@app.post("/projects/import", response_model=ApprovalResponse | ErrorResponse)
def import_project_entries(
    request: ProjectImportRequest,
    _: None = Depends(require_api_token),
    registry: ToolRegistry = Depends(get_tool_registry),
) -> ApprovalResponse | ErrorResponse:
    arguments = {
        "source": request.source,
        "path": request.path,
        "resolution": request.resolution,
    }
    preview_result = registry.execute(
        AgentAction("validate_project_import", arguments, "API request.")
    )
    preview = (preview_result.data or {}).get("preview", {})
    if not preview_result.ok:
        return ApprovalResponse(
            ok=False,
            message=preview_result.content,
            result_type="message",
            data={"preview": preview},
        )

    counts = preview.get("counts", {})
    alias_lines = []
    for update in preview.get("alias_updates", []):
        for alias in update.get("remove_aliases", []):
            alias_lines.append(
                f"- Remove alias \"{alias}\" from {update.get('project_id', '')}; "
                f"assign to {update.get('import_project_id', '')}"
            )
    reason = (
        "Import projects:\n\n"
        f"Projects: {counts.get('projects', 0)}\n"
        f"Creates: {counts.get('creates', 0)}\n"
        f"Updates: {counts.get('updates', 0)}\n"
        f"Skips: {counts.get('skips', 0)}\n"
        f"Resolution: {preview.get('resolution', request.resolution)}"
    )
    if alias_lines:
        reason = f"{reason}\n\nAlias ownership changes:\n" + "\n".join(alias_lines)
    return _execute_api_tool(registry, "import_projects", arguments, reason)


@app.get("/projects/backups", response_model=ProjectBackupsResponse | ErrorResponse)
def project_backups(
    _: None = Depends(require_api_token),
    registry: ToolRegistry = Depends(get_tool_registry),
) -> ProjectBackupsResponse | ErrorResponse:
    try:
        result = _execute_read_api_tool(registry, "list_project_backups")
        return ProjectBackupsResponse(ok=True, backups=(result.data or {}).get("backups", []))
    except Exception as error:
        return _error(error)


@app.post("/projects/backups", response_model=ApprovalResponse | ErrorResponse)
def create_project_backup(
    _: None = Depends(require_api_token),
    registry: ToolRegistry = Depends(get_tool_registry),
) -> ApprovalResponse | ErrorResponse:
    return _execute_api_tool(
        registry,
        "create_project_backup",
        {},
        "Create a project registry backup.",
    )


@app.post(
    "/projects/backups/validate",
    response_model=ProjectBackupValidationResponse | ErrorResponse,
)
def validate_project_backup(
    request: ProjectBackupRequest,
    _: None = Depends(require_api_token),
    registry: ToolRegistry = Depends(get_tool_registry),
) -> ProjectBackupValidationResponse | ErrorResponse:
    try:
        arguments = {"filename": request.filename, "path": request.path}
        result = registry.execute(
            AgentAction("validate_project_backup", arguments, "API request.")
        )
        return ProjectBackupValidationResponse(
            ok=result.ok,
            preview=(result.data or {}).get("preview", {}),
        )
    except Exception as error:
        return _error(error)


@app.post("/projects/backups/restore", response_model=ApprovalResponse | ErrorResponse)
def restore_project_backup(
    request: ProjectBackupRequest,
    _: None = Depends(require_api_token),
    registry: ToolRegistry = Depends(get_tool_registry),
) -> ApprovalResponse | ErrorResponse:
    arguments = {"filename": request.filename, "path": request.path}
    preview_result = registry.execute(
        AgentAction("validate_project_backup", arguments, "API request.")
    )
    preview = (preview_result.data or {}).get("preview", {})
    if not preview_result.ok:
        return ApprovalResponse(
            ok=False,
            message=preview_result.content,
            result_type="message",
            data={"preview": preview},
        )
    response = _execute_api_tool(
        registry,
        "restore_project_backup",
        arguments,
        (
            "Restore project registry backup:\n\n"
            f"Backup: {preview.get('filename') or request.filename or request.path or ''}\n"
            f"Created: {preview.get('created_at') or 'unknown'}\n"
            f"Projects: {preview.get('project_count', 0)}\n"
            f"Current project: {preview.get('current_project') or 'unknown'}"
        ),
    )
    if isinstance(response, ApprovalResponse):
        data = dict(response.data or {})
        data["preview"] = preview
        response.data = data
    return response


@app.delete("/projects/backups", response_model=ApprovalResponse | ErrorResponse)
def delete_project_backup(
    request: ProjectBackupRequest,
    _: None = Depends(require_api_token),
    registry: ToolRegistry = Depends(get_tool_registry),
) -> ApprovalResponse | ErrorResponse:
    target = request.filename or request.path or ""
    return _execute_api_tool(
        registry,
        "delete_project_backup",
        {"filename": request.filename, "path": request.path},
        f"Delete project registry backup:\n\nBackup: {target}",
    )


@app.get("/projects/snapshots", response_model=ProjectSnapshotsResponse | ErrorResponse)
def project_snapshots(
    _: None = Depends(require_api_token),
    registry: ToolRegistry = Depends(get_tool_registry),
) -> ProjectSnapshotsResponse | ErrorResponse:
    try:
        result = _execute_read_api_tool(registry, "list_project_snapshots")
        return ProjectSnapshotsResponse(ok=True, snapshots=(result.data or {}).get("snapshots", []))
    except Exception as error:
        return _error(error)


@app.post("/projects/snapshots", response_model=ApprovalResponse | ErrorResponse)
def create_project_snapshot(
    request: CreateProjectSnapshotRequest,
    _: None = Depends(require_api_token),
    registry: ToolRegistry = Depends(get_tool_registry),
) -> ApprovalResponse | ErrorResponse:
    reason = request.reason or "manual"
    return _execute_api_tool(
        registry,
        "create_project_snapshot",
        {"reason": reason},
        f"Create project registry snapshot:\n\nReason: {reason}",
    )


@app.post(
    "/projects/snapshots/validate",
    response_model=ProjectSnapshotValidationResponse | ErrorResponse,
)
def validate_project_snapshot(
    request: ProjectSnapshotRequest,
    _: None = Depends(require_api_token),
    registry: ToolRegistry = Depends(get_tool_registry),
) -> ProjectSnapshotValidationResponse | ErrorResponse:
    try:
        arguments = {"id": request.id, "filename": request.filename}
        result = registry.execute(
            AgentAction("validate_project_snapshot", arguments, "API request.")
        )
        return ProjectSnapshotValidationResponse(
            ok=result.ok,
            preview=(result.data or {}).get("preview", {}),
        )
    except Exception as error:
        return _error(error)


@app.post(
    "/projects/snapshots/diff",
    response_model=ProjectSnapshotDiffResponse | ErrorResponse,
)
def diff_project_snapshot(
    request: ProjectSnapshotRequest,
    _: None = Depends(require_api_token),
    registry: ToolRegistry = Depends(get_tool_registry),
) -> ProjectSnapshotDiffResponse | ErrorResponse:
    try:
        result = _execute_read_api_tool(
            registry,
            "diff_project_snapshot",
            {"id": request.id, "filename": request.filename},
        )
        return ProjectSnapshotDiffResponse(ok=True, diff=(result.data or {}).get("diff", {}))
    except Exception as error:
        return _error(error)


@app.post("/projects/snapshots/restore", response_model=ApprovalResponse | ErrorResponse)
def restore_project_snapshot(
    request: ProjectSnapshotRequest,
    _: None = Depends(require_api_token),
    registry: ToolRegistry = Depends(get_tool_registry),
) -> ApprovalResponse | ErrorResponse:
    arguments = {"id": request.id, "filename": request.filename}
    preview_result = registry.execute(
        AgentAction("validate_project_snapshot", arguments, "API request.")
    )
    preview = (preview_result.data or {}).get("preview", {})
    if not preview_result.ok:
        return ApprovalResponse(
            ok=False,
            message=preview_result.content,
            result_type="message",
            data={"preview": preview},
        )
    response = _execute_api_tool(
        registry,
        "restore_project_snapshot",
        arguments,
        (
            "Restore project registry snapshot:\n\n"
            f"Snapshot: {preview.get('snapshot', {}).get('filename') or request.filename or request.id or ''}\n"
            f"Created: {preview.get('snapshot', {}).get('created_at') or 'unknown'}\n"
            f"Reason: {preview.get('snapshot', {}).get('reason') or 'unknown'}\n"
            f"Projects: {preview.get('snapshot', {}).get('project_count', 0)}\n"
            "The current registry will first be snapshotted."
        ),
    )
    if isinstance(response, ApprovalResponse):
        data = dict(response.data or {})
        data["preview"] = preview
        response.data = data
    return response


@app.delete("/projects/snapshots/{snapshot_id}", response_model=ApprovalResponse | ErrorResponse)
def delete_project_snapshot(
    snapshot_id: str,
    _: None = Depends(require_api_token),
    registry: ToolRegistry = Depends(get_tool_registry),
) -> ApprovalResponse | ErrorResponse:
    return _execute_api_tool(
        registry,
        "delete_project_snapshot",
        {"id": snapshot_id},
        f"Delete project registry snapshot:\n\nSnapshot: {snapshot_id}",
    )


@app.post("/projects/snapshots/prune", response_model=ApprovalResponse | ErrorResponse)
def prune_project_snapshots(
    request: ProjectSnapshotPruneRequest,
    _: None = Depends(require_api_token),
    registry: ToolRegistry = Depends(get_tool_registry),
) -> ApprovalResponse | ErrorResponse:
    arguments = request.model_dump()
    preview_result = registry.execute(
        AgentAction(
            "prune_project_snapshots",
            {**arguments, "dry_run": True},
            "API request.",
        ),
        bypass_confirmation=True,
    )
    if not preview_result.ok:
        return ApprovalResponse(
            ok=False,
            message=preview_result.content,
            result_type="message",
            data=preview_result.data,
        )
    if request.dry_run:
        return ApprovalResponse(
            ok=True,
            message=preview_result.content,
            result_type="message",
            data=preview_result.data,
        )
    plan = preview_result.data or {}
    deleted = plan.get("deleted", []) if isinstance(plan, dict) else []
    retained = plan.get("retained", []) if isinstance(plan, dict) else []
    warnings = plan.get("warnings", []) if isinstance(plan, dict) else []
    policy = plan.get("policy", {}) if isinstance(plan.get("policy"), dict) else {}
    filenames = [str(item.get("filename", "")) for item in deleted if isinstance(item, dict)]
    summary_lines = [
        "Prune project registry snapshots",
        "",
        f"Delete {len(filenames)} snapshot(s)",
        f"Free {int(plan.get('freed_bytes') or 0)} bytes",
        f"Retain {len(retained)} snapshot(s)",
        "",
        f"Keep latest: {policy.get('keep_latest') if policy.get('keep_latest') is not None else 'none'}",
        f"Max age: {policy.get('max_age_days') if policy.get('max_age_days') is not None else 'none'}",
    ]
    if filenames:
        summary_lines.extend(["", "Files:"])
        summary_lines.extend(f"- {name}" for name in filenames)
    if warnings:
        summary_lines.extend(["", "Warnings:"])
        summary_lines.extend(f"- {warning}" for warning in warnings)
    response = _execute_api_tool(
        registry,
        "prune_project_snapshots",
        {**arguments, "plan": plan},
        "\n".join(summary_lines),
    )
    if isinstance(response, ApprovalResponse):
        data = dict(response.data or {})
        data["preview"] = plan
        response.data = data
    return response


@app.get("/projects/{project_id}/export", response_model=ProjectExportResponse | ErrorResponse)
def export_project_entry(
    project_id: str,
    _: None = Depends(require_api_token),
    registry: ToolRegistry = Depends(get_tool_registry),
) -> ProjectExportResponse | ErrorResponse:
    try:
        result = _execute_read_api_tool(registry, "export_project", {"project": project_id})
        return ProjectExportResponse(ok=True, export=(result.data or {}).get("export", {}))
    except Exception as error:
        return _error(error)


@app.get("/projects/{project_id}", response_model=ProjectResponse | ErrorResponse)
def project_entry(
    project_id: str,
    _: None = Depends(require_api_token),
    registry: ToolRegistry = Depends(get_tool_registry),
) -> ProjectResponse | ErrorResponse:
    try:
        result = _execute_read_api_tool(registry, "get_project", {"project": project_id})
        return ProjectResponse(ok=True, project=(result.data or {}).get("project", {}))
    except Exception as error:
        return _error(error)


@app.put("/projects/{project_id}", response_model=ApprovalResponse | ErrorResponse)
def update_project_entry(
    project_id: str,
    request: ProjectRegistryRequest,
    _: None = Depends(require_api_token),
    registry: ToolRegistry = Depends(get_tool_registry),
) -> ApprovalResponse | ErrorResponse:
    project = request.project
    return _execute_api_tool(
        registry,
        "update_project",
        {"project_id": project_id, "project": project},
        (
            "Update project:\n\n"
            f"Project: {project.get('name') or project.get('id') or project_id}\n"
            f"Root path: {project.get('root_path') or ''}"
        ),
    )


@app.delete("/projects/{project_id}", response_model=ApprovalResponse | ErrorResponse)
def delete_project_entry(
    project_id: str,
    request: DeleteProjectRequest | None = None,
    _: None = Depends(require_api_token),
    registry: ToolRegistry = Depends(get_tool_registry),
) -> ApprovalResponse | ErrorResponse:
    return _execute_api_tool(
        registry,
        "delete_project",
        {
            "project_id": project_id,
            "confirm_current": bool(request.confirm_current) if request else False,
        },
        f"Delete project:\n\nProject: {project_id}",
    )


@app.post("/projects/{project_id}/duplicate", response_model=ProjectResponse | ErrorResponse)
def duplicate_project_entry(
    project_id: str,
    _: None = Depends(require_api_token),
    registry: ToolRegistry = Depends(get_tool_registry),
) -> ProjectResponse | ErrorResponse:
    try:
        result = _execute_read_api_tool(registry, "duplicate_project", {"project_id": project_id})
        return ProjectResponse(ok=True, project=(result.data or {}).get("project", {}))
    except Exception as error:
        return _error(error)


@app.post("/projects/repo/open", response_model=ApprovalResponse | ErrorResponse)
def open_project_repo(
    request: OpenProjectRepoRequest,
    _: None = Depends(require_api_token),
    registry: ToolRegistry = Depends(get_tool_registry),
) -> ApprovalResponse | ErrorResponse:
    return _execute_api_tool(
        registry,
        "open_project_repo_in_browser",
        {"project": request.project, "mode": request.mode},
    )


@app.post("/projects/current/workspace", response_model=ApprovalResponse | ErrorResponse)
def open_current_project_workspace(
    request: OpenProjectWorkspaceRequest,
    _: None = Depends(require_api_token),
    registry: ToolRegistry = Depends(get_tool_registry),
) -> ApprovalResponse | ErrorResponse:
    return _execute_api_tool(
        registry,
        "open_project_workspace",
        {"target": request.target},
    )


@app.get(
    "/projects/current/workspace/preferences",
    response_model=WorkspacePreferencesResponse | ErrorResponse,
)
def current_workspace_preferences(
    _: None = Depends(require_api_token),
    registry: ToolRegistry = Depends(get_tool_registry),
) -> WorkspacePreferencesResponse | ErrorResponse:
    try:
        result = _execute_read_api_tool(registry, "get_workspace_preferences")
        data = result.data or {}
        return WorkspacePreferencesResponse(
            ok=True,
            project=data.get("project", {}),
            preferences=data.get("preferences", {}),
            editable_fields=data.get("editable_fields", {}),
        )
    except Exception as error:
        return _error(error)


@app.post(
    "/projects/current/workspace/preferences",
    response_model=ApprovalResponse | ErrorResponse,
)
def update_current_workspace_preferences(
    request: UpdateWorkspacePreferencesRequest,
    _: None = Depends(require_api_token),
    registry: ToolRegistry = Depends(get_tool_registry),
) -> ApprovalResponse | ErrorResponse:
    changes = request.changes
    if changes is None:
        if request.section is None or request.field is None or request.value is None:
            return _error("changes is required.")
        changes_payload: list[dict[str, Any]] = [
            {
                "section": request.section,
                "field": request.field,
                "value": request.value,
            }
        ]
    else:
        changes_payload = [change.model_dump() for change in changes]

    if not changes_payload:
        return _error("changes must contain at least one workspace preference change.")
    if len(changes_payload) > workspace_preferences.MAX_CHANGES:
        return _error(f"changes must contain at most {workspace_preferences.MAX_CHANGES} items.")

    arguments = {"changes": changes_payload}
    if request.project:
        arguments["project"] = request.project
    return _execute_api_tool(registry, "update_workspace_preferences", arguments)


@app.get(
    "/projects/current/describe",
    response_model=ProjectDescriptionResponse | ErrorResponse,
)
def describe_current_project(
    _: None = Depends(require_api_token),
    registry: ToolRegistry = Depends(get_tool_registry),
) -> ProjectDescriptionResponse | ErrorResponse:
    try:
        result = _execute_read_api_tool(registry, "describe_current_project")
        return ProjectDescriptionResponse(
            ok=True,
            description=result.content,
            project=(result.data or {}).get("project", {}),
        )
    except Exception as error:
        return _error(error)


@app.get(
    "/projects/current/commands",
    response_model=ProjectCommandsResponse | ErrorResponse,
)
def current_project_commands(
    _: None = Depends(require_api_token),
    registry: ToolRegistry = Depends(get_tool_registry),
) -> ProjectCommandsResponse | ErrorResponse:
    try:
        result = _execute_read_api_tool(registry, "list_project_commands")
        data = result.data or {}
        return ProjectCommandsResponse(
            ok=True,
            project=data.get("project", {}),
            cwd=data.get("cwd", ""),
            commands=data.get("commands", {}),
        )
    except Exception as error:
        return _error(error)


@app.post(
    "/projects/current/commands/{command_key}/run",
    response_model=ApprovalResponse | ErrorResponse,
)
def run_current_project_command(
    command_key: str,
    request: RunProjectCommandRequest | None = None,
    _: None = Depends(require_api_token),
    registry: ToolRegistry = Depends(get_tool_registry),
) -> ApprovalResponse | ErrorResponse:
    timeout_seconds = request.timeout_seconds if request is not None else 120
    return _execute_api_tool(
        registry,
        "run_project_command",
        {"command_key": command_key, "timeout_seconds": timeout_seconds},
    )


@app.post(
    "/projects/current/commands/{command_key}/run-visible",
    response_model=ApprovalResponse | ErrorResponse,
)
def run_current_project_command_visible(
    command_key: str,
    _: None = Depends(require_api_token),
    registry: ToolRegistry = Depends(get_tool_registry),
) -> ApprovalResponse | ErrorResponse:
    return _execute_api_tool(
        registry,
        "run_project_command_visible",
        {"command_key": command_key},
    )


@app.get("/approvals")
def approvals(
    _: None = Depends(require_api_token),
) -> dict[str, Any] | ErrorResponse:
    try:
        return {"ok": True, "pending": list_approvals()}
    except Exception as error:
        return _error(error)


@app.get("/tasks", response_model=ScheduledTasksResponse | ErrorResponse)
def tasks(
    _: None = Depends(require_api_token),
) -> ScheduledTasksResponse | ErrorResponse:
    try:
        return ScheduledTasksResponse(ok=True, tasks=list_tasks())
    except Exception as error:
        return _error(error)


@app.get("/scheduler/status", response_model=SchedulerStatusResponse | ErrorResponse)
def scheduler_status(
    request: Request,
    _: None = Depends(require_api_token),
) -> SchedulerStatusResponse | ErrorResponse:
    try:
        worker: SchedulerWorker | None = getattr(
            request.app.state, "scheduler_worker", None
        )
        enabled = bool(getattr(request.app.state, "scheduler_worker_enabled", False))
        return SchedulerStatusResponse(
            ok=True,
            enabled=enabled,
            running=bool(worker and worker.running),
            interval_seconds=worker.interval_seconds if worker else 60,
        )
    except Exception as error:
        return _error(error)


@app.post(
    "/scheduler/run-once", response_model=SchedulerRunOnceResponse | ErrorResponse
)
async def scheduler_run_once(
    request: Request,
    _: None = Depends(require_api_token),
) -> SchedulerRunOnceResponse | ErrorResponse:
    try:
        worker: SchedulerWorker | None = getattr(
            request.app.state, "scheduler_worker", None
        )
        if worker is None:
            worker = SchedulerWorker()
            request.app.state.scheduler_worker = worker
            request.app.state.scheduler_worker_enabled = False
        results = await worker.run_once()
        return SchedulerRunOnceResponse(ok=True, results=results)
    except Exception as error:
        return _error(error)


@app.post("/tasks", response_model=ApprovalResponse | ErrorResponse)
def create_task(
    request: CreateScheduledTaskRequest,
    _: None = Depends(require_api_token),
    registry: ToolRegistry = Depends(get_tool_registry),
) -> ApprovalResponse | ErrorResponse:
    try:
        result = registry.execute(
            AgentAction(
                "create_scheduled_task",
                {
                    "title": request.title,
                    "prompt": request.prompt,
                    "schedule_type": request.schedule_type,
                    "schedule_value": request.schedule_value,
                },
                "API request.",
            )
        )
        return _approval_response(result, "create_scheduled_task")
    except Exception as error:
        return _error(error)


@app.post("/browser/title", response_model=ApprovalResponse | ErrorResponse)
def browser_title_endpoint(
    request: BrowserUrlRequest,
    _: None = Depends(require_api_token),
    registry: ToolRegistry = Depends(get_tool_registry),
) -> ApprovalResponse | ErrorResponse:
    return _execute_api_tool(registry, "browser_title", {"url": request.url})


@app.post("/browser/text", response_model=ApprovalResponse | ErrorResponse)
def browser_text_endpoint(
    request: BrowserTextRequest,
    _: None = Depends(require_api_token),
    registry: ToolRegistry = Depends(get_tool_registry),
) -> ApprovalResponse | ErrorResponse:
    return _execute_api_tool(
        registry,
        "browser_extract_text",
        {"url": request.url, "max_chars": request.max_chars},
    )


@app.post("/browser/links", response_model=ApprovalResponse | ErrorResponse)
def browser_links_endpoint(
    request: BrowserLinksRequest,
    _: None = Depends(require_api_token),
    registry: ToolRegistry = Depends(get_tool_registry),
) -> ApprovalResponse | ErrorResponse:
    return _execute_api_tool(
        registry,
        "browser_links",
        {"url": request.url, "limit": request.limit},
    )


@app.post("/browser/screenshot", response_model=ApprovalResponse | ErrorResponse)
def browser_screenshot_endpoint(
    request: BrowserScreenshotRequest,
    _: None = Depends(require_api_token),
    registry: ToolRegistry = Depends(get_tool_registry),
) -> ApprovalResponse | ErrorResponse:
    return _execute_api_tool(
        registry,
        "browser_screenshot",
        {"url": request.url, "path": request.path},
    )


@app.post("/browser/task", response_model=ApprovalResponse | ErrorResponse)
def browser_task_endpoint(
    request: BrowserTaskRequest,
    _: None = Depends(require_api_token),
    registry: ToolRegistry = Depends(get_tool_registry),
) -> ApprovalResponse | ErrorResponse:
    return _execute_api_tool(
        registry,
        "browser_task",
        {"url": request.url, "instruction": request.instruction},
    )


@app.post("/browser/click", response_model=ApprovalResponse | ErrorResponse)
def browser_click_endpoint(
    request: BrowserSelectorRequest,
    _: None = Depends(require_api_token),
    registry: ToolRegistry = Depends(get_tool_registry),
) -> ApprovalResponse | ErrorResponse:
    return _execute_api_tool(
        registry,
        "browser_click",
        {"url": request.url, "selector": request.selector},
    )


@app.post("/browser/fill", response_model=ApprovalResponse | ErrorResponse)
def browser_fill_endpoint(
    request: BrowserFillRequest,
    _: None = Depends(require_api_token),
    registry: ToolRegistry = Depends(get_tool_registry),
) -> ApprovalResponse | ErrorResponse:
    return _execute_api_tool(
        registry,
        "browser_fill",
        {"url": request.url, "selector": request.selector, "value": request.value},
    )


@app.post("/browser/submit", response_model=ApprovalResponse | ErrorResponse)
def browser_submit_endpoint(
    request: BrowserSelectorRequest,
    _: None = Depends(require_api_token),
    registry: ToolRegistry = Depends(get_tool_registry),
) -> ApprovalResponse | ErrorResponse:
    return _execute_api_tool(
        registry,
        "browser_submit",
        {"url": request.url, "selector": request.selector},
    )


@app.post("/browser/wait", response_model=ApprovalResponse | ErrorResponse)
def browser_wait_endpoint(
    request: BrowserWaitRequest,
    _: None = Depends(require_api_token),
    registry: ToolRegistry = Depends(get_tool_registry),
) -> ApprovalResponse | ErrorResponse:
    return _execute_api_tool(
        registry,
        "browser_wait_for_selector",
        {
            "url": request.url,
            "selector": request.selector,
            "timeout_ms": request.timeout_ms,
        },
    )


@app.post("/browser/sessions", response_model=ApprovalResponse | ErrorResponse)
def browser_open_session_endpoint(
    request: BrowserSessionOpenRequest,
    _: None = Depends(require_api_token),
    registry: ToolRegistry = Depends(get_tool_registry),
) -> ApprovalResponse | ErrorResponse:
    return _execute_api_tool(
        registry,
        "browser_open_session",
        {"url": request.url, "mode": request.mode},
    )


@app.get("/browser/sessions", response_model=BrowserSessionsResponse | ErrorResponse)
def browser_sessions_endpoint(
    _: None = Depends(require_api_token),
    registry: ToolRegistry = Depends(get_tool_registry),
) -> BrowserSessionsResponse | ErrorResponse:
    try:
        result = registry.execute(AgentAction("browser_list_sessions", {}, "API request."))
        return BrowserSessionsResponse(
            ok=result.ok,
            sessions=(result.data or {}).get("sessions", []),
        )
    except Exception as error:
        return _error(error)


@app.get(
    "/browser/sessions/{session_id}",
    response_model=BrowserSessionResponse | ErrorResponse,
)
def browser_session_status_endpoint(
    session_id: str,
    _: None = Depends(require_api_token),
    registry: ToolRegistry = Depends(get_tool_registry),
) -> BrowserSessionResponse | ErrorResponse:
    try:
        result = registry.execute(
            AgentAction(
                "browser_session_status",
                {"session_id": session_id},
                "API request.",
            )
        )
        if not result.ok:
            return _error(result.content)
        return BrowserSessionResponse(
            ok=True,
            session=(result.data or {}).get("session", {}),
        )
    except Exception as error:
        return _error(error)


@app.delete("/browser/sessions/{session_id}", response_model=ApprovalResponse | ErrorResponse)
def browser_close_session_endpoint(
    session_id: str,
    _: None = Depends(require_api_token),
    registry: ToolRegistry = Depends(get_tool_registry),
) -> ApprovalResponse | ErrorResponse:
    return _execute_api_tool(
        registry,
        "browser_close_session",
        {"session_id": session_id},
    )


@app.delete("/browser/sessions", response_model=ApprovalResponse | ErrorResponse)
def browser_close_all_sessions_endpoint(
    _: None = Depends(require_api_token),
    registry: ToolRegistry = Depends(get_tool_registry),
) -> ApprovalResponse | ErrorResponse:
    return _execute_api_tool(registry, "browser_close_all_sessions", {})


@app.post(
    "/browser/sessions/{session_id}/click",
    response_model=ApprovalResponse | ErrorResponse,
)
def browser_session_click_endpoint(
    session_id: str,
    request: BrowserSessionSelectorRequest,
    _: None = Depends(require_api_token),
    registry: ToolRegistry = Depends(get_tool_registry),
) -> ApprovalResponse | ErrorResponse:
    return _execute_api_tool(
        registry,
        "browser_session_click",
        {"session_id": session_id, "selector": request.selector},
    )


@app.post(
    "/browser/sessions/{session_id}/fill",
    response_model=ApprovalResponse | ErrorResponse,
)
def browser_session_fill_endpoint(
    session_id: str,
    request: BrowserSessionFillRequest,
    _: None = Depends(require_api_token),
    registry: ToolRegistry = Depends(get_tool_registry),
) -> ApprovalResponse | ErrorResponse:
    return _execute_api_tool(
        registry,
        "browser_session_fill",
        {
            "session_id": session_id,
            "selector": request.selector,
            "value": request.value,
        },
    )


@app.post(
    "/browser/sessions/{session_id}/submit",
    response_model=ApprovalResponse | ErrorResponse,
)
def browser_session_submit_endpoint(
    session_id: str,
    request: BrowserSessionSelectorRequest,
    _: None = Depends(require_api_token),
    registry: ToolRegistry = Depends(get_tool_registry),
) -> ApprovalResponse | ErrorResponse:
    return _execute_api_tool(
        registry,
        "browser_session_submit",
        {"session_id": session_id, "selector": request.selector},
    )


@app.post(
    "/browser/sessions/{session_id}/wait",
    response_model=ApprovalResponse | ErrorResponse,
)
def browser_session_wait_endpoint(
    session_id: str,
    request: BrowserSessionWaitRequest,
    _: None = Depends(require_api_token),
    registry: ToolRegistry = Depends(get_tool_registry),
) -> ApprovalResponse | ErrorResponse:
    return _execute_api_tool(
        registry,
        "browser_session_wait_for_selector",
        {
            "session_id": session_id,
            "selector": request.selector,
            "timeout_ms": request.timeout_ms,
        },
    )


@app.get("/git/status", response_model=ApprovalResponse | ErrorResponse)
def git_status_endpoint(
    _: None = Depends(require_api_token),
    registry: ToolRegistry = Depends(get_tool_registry),
) -> ApprovalResponse | ErrorResponse:
    return _execute_api_tool(registry, "git_status", {})


@app.get("/git/diff", response_model=ApprovalResponse | ErrorResponse)
def git_diff_endpoint(
    _: None = Depends(require_api_token),
    registry: ToolRegistry = Depends(get_tool_registry),
) -> ApprovalResponse | ErrorResponse:
    return _execute_api_tool(registry, "git_diff", {"staged": False})


@app.get("/git/diff/staged", response_model=ApprovalResponse | ErrorResponse)
def git_staged_diff_endpoint(
    _: None = Depends(require_api_token),
    registry: ToolRegistry = Depends(get_tool_registry),
) -> ApprovalResponse | ErrorResponse:
    return _execute_api_tool(registry, "git_diff", {"staged": True})


@app.get("/git/log", response_model=ApprovalResponse | ErrorResponse)
def git_log_endpoint(
    _: None = Depends(require_api_token),
    registry: ToolRegistry = Depends(get_tool_registry),
) -> ApprovalResponse | ErrorResponse:
    return _execute_api_tool(registry, "git_log", {})


@app.get("/git/branch", response_model=ApprovalResponse | ErrorResponse)
def git_branch_endpoint(
    _: None = Depends(require_api_token),
    registry: ToolRegistry = Depends(get_tool_registry),
) -> ApprovalResponse | ErrorResponse:
    return _execute_api_tool(registry, "git_current_branch", {})


@app.get("/git/suggest-commit-message", response_model=ApprovalResponse | ErrorResponse)
def git_suggest_commit_message_endpoint(
    _: None = Depends(require_api_token),
    registry: ToolRegistry = Depends(get_tool_registry),
) -> ApprovalResponse | ErrorResponse:
    return _execute_api_tool(registry, "git_suggest_commit_message", {})


@app.post("/git/commit", response_model=ApprovalResponse | ErrorResponse)
def git_commit_endpoint(
    request: GitCommitRequest,
    _: None = Depends(require_api_token),
    registry: ToolRegistry = Depends(get_tool_registry),
) -> ApprovalResponse | ErrorResponse:
    return _execute_api_tool(registry, "git_commit", {"message": request.message})


@app.post("/tasks/{task_id}/run", response_model=ApprovalResponse | ErrorResponse)
def run_task(
    task_id: str,
    _: None = Depends(require_api_token),
    registry: ToolRegistry = Depends(get_tool_registry),
) -> ApprovalResponse | ErrorResponse:
    try:
        result = registry.execute(
            AgentAction("run_scheduled_task", {"task_id": task_id}, "API request.")
        )
        return _approval_response(result, "run_scheduled_task")
    except Exception as error:
        return _error(error)


@app.post("/tasks/{task_id}/enable", response_model=ApprovalResponse | ErrorResponse)
def enable_task(
    task_id: str,
    _: None = Depends(require_api_token),
    registry: ToolRegistry = Depends(get_tool_registry),
) -> ApprovalResponse | ErrorResponse:
    try:
        result = registry.execute(
            AgentAction("enable_scheduled_task", {"task_id": task_id}, "API request.")
        )
        return _approval_response(result, "enable_scheduled_task")
    except Exception as error:
        return _error(error)


@app.post("/tasks/{task_id}/disable", response_model=ApprovalResponse | ErrorResponse)
def disable_task(
    task_id: str,
    _: None = Depends(require_api_token),
    registry: ToolRegistry = Depends(get_tool_registry),
) -> ApprovalResponse | ErrorResponse:
    try:
        result = registry.execute(
            AgentAction("disable_scheduled_task", {"task_id": task_id}, "API request.")
        )
        return _approval_response(result, "disable_scheduled_task")
    except Exception as error:
        return _error(error)


@app.delete("/tasks/{task_id}", response_model=ApprovalResponse | ErrorResponse)
def delete_task(
    task_id: str,
    _: None = Depends(require_api_token),
    registry: ToolRegistry = Depends(get_tool_registry),
) -> ApprovalResponse | ErrorResponse:
    try:
        result = registry.execute(
            AgentAction("delete_scheduled_task", {"task_id": task_id}, "API request.")
        )
        return _approval_response(result, "delete_scheduled_task")
    except Exception as error:
        return _error(error)


@app.post(
    "/approvals/{approval_id}/approve", response_model=ApprovalResponse | ErrorResponse
)
def approve_approval(
    approval_id: str,
    _: None = Depends(require_api_token),
    registry: ToolRegistry = Depends(get_tool_registry),
) -> ApprovalResponse | ErrorResponse:
    try:
        action = approve(approval_id)
        if action is None:
            return _error(f"Approval not found: {approval_id}")

        result = registry.execute(action, bypass_confirmation=True)
        clear_approval(approval_id)
        return _approval_response(result, action.action)
    except Exception as error:
        return _error(error)


@app.post(
    "/approvals/{approval_id}/reject", response_model=ApprovalResponse | ErrorResponse
)
def reject_approval(
    approval_id: str,
    _: None = Depends(require_api_token),
) -> ApprovalResponse | ErrorResponse:
    try:
        if reject(approval_id):
            return ApprovalResponse(ok=True, message="Approval rejected.")
        return _error(f"Approval not found: {approval_id}")
    except Exception as error:
        return _error(error)


@app.get("/memory/session", response_model=MemoryResponse | ErrorResponse)
def memory_session(
    _: None = Depends(require_api_token),
) -> MemoryResponse | ErrorResponse:
    return _read_memory_file("session.md")


@app.get("/memory/facts", response_model=MemoryResponse | ErrorResponse)
def memory_facts(
    _: None = Depends(require_api_token),
) -> MemoryResponse | ErrorResponse:
    return _read_memory_file("facts.md")


@app.get("/memory/project", response_model=MemoryResponse | ErrorResponse)
def memory_project(
    _: None = Depends(require_api_token),
) -> MemoryResponse | ErrorResponse:
    return _read_memory_file("project.md")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
