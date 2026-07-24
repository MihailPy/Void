"""Pydantic schemas for the Void HTTP API."""

from typing import Any, Literal

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    ok: bool
    response: str
    result_type: str = "final_answer"
    clarification: dict[str, Any] | None = None
    message: str | None = None
    data: dict[str, Any] | None = None


class HealthResponse(BaseModel):
    ok: bool
    service: str
    version: str


class ApprovalResponse(BaseModel):
    ok: bool
    message: str
    result_type: str = "message"
    data: dict[str, Any] | None = None


class ClarificationResponse(BaseModel):
    ok: bool
    pending: dict[str, Any] | None = None


class ClarificationRespondRequest(BaseModel):
    answer: str


class MemoryResponse(BaseModel):
    ok: bool
    content: str


class CapabilitiesResponse(BaseModel):
    ok: bool
    installed: list[Any]
    requested: list[Any]
    rejected: list[Any]


class ActivityResponse(BaseModel):
    ok: bool
    activities: list[dict[str, Any]]


class LastActivityResponse(BaseModel):
    ok: bool
    activity: dict[str, Any] | None = None


class ProjectsResponse(BaseModel):
    ok: bool
    projects: list[dict[str, Any]]
    current_project: str | None = None


class ProjectResponse(BaseModel):
    ok: bool
    project: dict[str, Any]


class CurrentProjectResponse(BaseModel):
    ok: bool
    project: dict[str, Any]


class ProjectDescriptionResponse(BaseModel):
    ok: bool
    description: str
    project: dict[str, Any]


class ProjectCommandsResponse(BaseModel):
    ok: bool
    project: dict[str, Any]
    cwd: str
    commands: dict[str, str]


class SetCurrentProjectRequest(BaseModel):
    project: str


class ProjectRegistryRequest(BaseModel):
    project: dict[str, Any]
    duplicate_source_id: str | None = None


class ProjectExportResponse(BaseModel):
    ok: bool
    export: dict[str, Any]


class ProjectImportRequest(BaseModel):
    source: Any | None = None
    path: str | None = None
    resolution: Literal["replace", "rename", "skip"] = "skip"


class ProjectImportValidationResponse(BaseModel):
    ok: bool
    preview: dict[str, Any]


class ProjectBackupsResponse(BaseModel):
    ok: bool
    backups: list[dict[str, Any]]


class ProjectBackupRequest(BaseModel):
    filename: str | None = None
    path: str | None = None


class ProjectBackupValidationResponse(BaseModel):
    ok: bool
    preview: dict[str, Any]


class ProjectSnapshotRequest(BaseModel):
    id: str | None = None
    filename: str | None = None


class CreateProjectSnapshotRequest(BaseModel):
    reason: str | None = None


class ProjectSnapshotsResponse(BaseModel):
    ok: bool
    snapshots: list[dict[str, Any]]


class ProjectSnapshotValidationResponse(BaseModel):
    ok: bool
    preview: dict[str, Any]


class ProjectSnapshotDiffResponse(BaseModel):
    ok: bool
    diff: dict[str, Any]


class ProjectSnapshotPruneRequest(BaseModel):
    keep_latest: int = 50
    max_age_days: int | None = 90
    dry_run: bool = False
    include_invalid: bool = False


class DeleteProjectRequest(BaseModel):
    confirm_current: bool = False


class OpenProjectRepoRequest(BaseModel):
    project: str
    mode: Literal["visible", "headless"] = "visible"


class OpenProjectWorkspaceRequest(BaseModel):
    target: Literal["terminal", "finder", "github", "browser", "editor"] = "terminal"


class WorkspacePreferencesResponse(BaseModel):
    ok: bool
    project: dict[str, Any]
    preferences: dict[str, Any]
    editable_fields: dict[str, list[str]]


class WorkspacePreferenceChange(BaseModel):
    section: str
    field: str
    value: Any


class UpdateWorkspacePreferencesRequest(BaseModel):
    project: str | None = None
    changes: list[WorkspacePreferenceChange] | None = None
    section: str | None = None
    field: str | None = None
    value: Any | None = None


class RunProjectCommandRequest(BaseModel):
    timeout_seconds: int = Field(default=120, ge=1, le=3600)


class SkillsResponse(BaseModel):
    ok: bool
    skills: list[Any]


class ScheduledTaskResponse(BaseModel):
    ok: bool
    task: dict[str, Any]


class ScheduledTasksResponse(BaseModel):
    ok: bool
    tasks: list[dict[str, Any]]


class SchedulerStatusResponse(BaseModel):
    ok: bool
    enabled: bool
    running: bool
    interval_seconds: int


class SchedulerRunOnceResponse(BaseModel):
    ok: bool
    results: list[dict[str, Any]]


class CreateScheduledTaskRequest(BaseModel):
    title: str
    prompt: str
    schedule_type: str
    schedule_value: dict[str, Any]


class BrowserUrlRequest(BaseModel):
    url: str


class BrowserTextRequest(BaseModel):
    url: str
    max_chars: int = 5000


class BrowserLinksRequest(BaseModel):
    url: str
    limit: int = 50


class BrowserScreenshotRequest(BaseModel):
    url: str
    path: str = "workspace/screenshots/page.png"


class BrowserTaskRequest(BaseModel):
    url: str
    instruction: str


class BrowserSelectorRequest(BaseModel):
    url: str
    selector: str


class BrowserFillRequest(BaseModel):
    url: str
    selector: str
    value: str


class BrowserWaitRequest(BaseModel):
    url: str
    selector: str
    timeout_ms: int = Field(default=10000, ge=1, le=60000)


class BrowserSessionOpenRequest(BaseModel):
    url: str
    mode: Literal["headless", "visible"] = "headless"


class BrowserSessionSelectorRequest(BaseModel):
    selector: str


class BrowserSessionFillRequest(BaseModel):
    selector: str
    value: str


class BrowserSessionWaitRequest(BaseModel):
    selector: str
    timeout_ms: int = Field(default=10000, ge=1, le=60000)


class BrowserSessionResponse(BaseModel):
    ok: bool
    session: dict[str, Any]


class BrowserSessionsResponse(BaseModel):
    ok: bool
    sessions: list[dict[str, Any]]


class GitCommitRequest(BaseModel):
    message: str


class ErrorResponse(BaseModel):
    ok: bool
    error: str
    message: str | None = None
    result_type: str = "error"
    data: dict[str, Any] | None = None
