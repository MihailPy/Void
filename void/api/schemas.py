"""Pydantic schemas for the Void HTTP API."""

from typing import Any

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    ok: bool
    response: str


class HealthResponse(BaseModel):
    ok: bool
    service: str
    version: str


class ApprovalResponse(BaseModel):
    ok: bool
    message: str


class MemoryResponse(BaseModel):
    ok: bool
    content: str


class CapabilitiesResponse(BaseModel):
    ok: bool
    installed: list[Any]
    requested: list[Any]
    rejected: list[Any]


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


class GitCommitRequest(BaseModel):
    message: str


class ErrorResponse(BaseModel):
    ok: bool
    error: str
