"""FastAPI server for the Void backend."""

from typing import Any

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from void.api.dependencies import get_agent, get_skill_registry, get_tool_registry
from void.api.schemas import (
    ApprovalResponse,
    CapabilitiesResponse,
    ChatRequest,
    ChatResponse,
    ErrorResponse,
    HealthResponse,
    MemoryResponse,
    SkillsResponse,
)
from void.core.agent import Agent
from void.core.capabilities import list_capabilities
from void.core.permissions import approve, clear_approval, list_approvals, reject
from void.core.registry import ToolRegistry
from void.core.safety import MEMORY_DIR, ensure_memory_files
from void.skills.registry import SkillRegistry

API_VERSION = "0.8.0"

app = FastAPI(
    title="Void API",
    version=API_VERSION,
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


@app.get("/health", response_model=HealthResponse | ErrorResponse)
def health() -> HealthResponse | ErrorResponse:
    try:
        return HealthResponse(ok=True, service="Void API", version=API_VERSION)
    except Exception as error:
        return _error(error)


@app.post("/chat", response_model=ChatResponse | ErrorResponse)
def chat(
    request: ChatRequest,
    agent: Agent = Depends(get_agent),
) -> ChatResponse | ErrorResponse:
    try:
        response = agent.handle(request.message)
        return ChatResponse(ok=True, response=response)
    except Exception as error:
        return _error(error)


@app.get("/skills", response_model=SkillsResponse | ErrorResponse)
def skills(
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
def capabilities() -> CapabilitiesResponse | ErrorResponse:
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
def approvals() -> dict[str, Any] | ErrorResponse:
    try:
        return {"ok": True, "pending": list_approvals()}
    except Exception as error:
        return _error(error)


@app.post("/approvals/{approval_id}/approve", response_model=ApprovalResponse | ErrorResponse)
def approve_approval(
    approval_id: str,
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


@app.post("/approvals/{approval_id}/reject", response_model=ApprovalResponse | ErrorResponse)
def reject_approval(approval_id: str) -> ApprovalResponse | ErrorResponse:
    try:
        if reject(approval_id):
            return ApprovalResponse(ok=True, message="Approval rejected.")
        return _error(f"Approval not found: {approval_id}")
    except Exception as error:
        return _error(error)


@app.get("/memory/session", response_model=MemoryResponse | ErrorResponse)
def memory_session() -> MemoryResponse | ErrorResponse:
    return _read_memory_file("session.md")


@app.get("/memory/facts", response_model=MemoryResponse | ErrorResponse)
def memory_facts() -> MemoryResponse | ErrorResponse:
    return _read_memory_file("facts.md")


@app.get("/memory/project", response_model=MemoryResponse | ErrorResponse)
def memory_project() -> MemoryResponse | ErrorResponse:
    return _read_memory_file("project.md")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("void.api.server:app", host="127.0.0.1", port=8000, reload=True)
