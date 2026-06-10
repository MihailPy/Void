"""Pydantic schemas for the Void HTTP API."""

from typing import Any

from pydantic import BaseModel


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


class ErrorResponse(BaseModel):
    ok: bool
    error: str
