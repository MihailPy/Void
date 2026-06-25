"""FastAPI server for the Void backend."""

import os
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from void.__version__ import __version__
from void.api.auth import get_api_token, require_api_token
from void.api.dependencies import get_agent, get_skill_registry, get_tool_registry
from void.api.schemas import (
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
    ErrorResponse,
    GitCommitRequest,
    HealthResponse,
    MemoryResponse,
    ScheduledTasksResponse,
    SchedulerRunOnceResponse,
    SchedulerStatusResponse,
    SkillsResponse,
)
from void.core.agent import Agent
from void.core.capabilities import list_capabilities
from void.core.permissions import approve, clear_approval, list_approvals, reject
from void.core.registry import ToolRegistry
from void.core.safety import MEMORY_DIR, ensure_memory_files
from void.core.scheduler import list_tasks
from void.core.scheduler_worker import SchedulerWorker
from void.core.types import AgentAction
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
        content=ErrorResponse(ok=False, error=str(exc)).model_dump(),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(ok=False, error=str(exc)).model_dump(),
    )


def _error(error: Exception | str) -> ErrorResponse:
    message = str(error)
    return ErrorResponse(ok=False, error=message)


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
) -> ApprovalResponse | ErrorResponse:
    try:
        result = registry.execute(AgentAction(action, arguments, "API request."))
        return ApprovalResponse(ok=result.ok, message=result.content)
    except Exception as error:
        return _error(error)


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
        response = agent.handle(request.message)
        return ChatResponse(ok=True, response=response)
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
        return ApprovalResponse(ok=result.ok, message=result.content)
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
        return ApprovalResponse(ok=result.ok, message=result.content)
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
        return ApprovalResponse(ok=result.ok, message=result.content)
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
        return ApprovalResponse(ok=result.ok, message=result.content)
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
        return ApprovalResponse(ok=result.ok, message=result.content)
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
        return ApprovalResponse(ok=result.ok, message=result.content)
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
