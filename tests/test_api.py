from collections.abc import Mapping
from typing import Any

import anyio
import httpx

from void.api.server import app


async def _request(
    method: str,
    path: str,
    json: Mapping[str, Any] | None = None,
) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.request(method, path, json=json)


def request(
    method: str,
    path: str,
    *,
    json: Mapping[str, Any] | None = None,
) -> httpx.Response:
    return anyio.run(_request, method, path, json)


def test_health():
    response = request("GET", "/health")

    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_skills():
    response = request("GET", "/skills")

    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_capabilities():
    response = request("GET", "/capabilities")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["installed"] == []
    assert payload["requested"] == []
    assert payload["rejected"] == []


def test_tasks():
    response = request("GET", "/tasks")

    assert response.status_code == 200
    assert response.json() == {"ok": True, "tasks": []}


def test_chat_uses_router_without_llm():
    response = request("POST", "/chat", json={"message": "Сделай статистику проекта"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["response"]
    assert "Project statistics" in payload["response"]


def test_git_status_endpoint():
    response = request("GET", "/git/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert isinstance(payload["message"], str)


def test_git_commit_endpoint_creates_approval():
    response = request("POST", "/git/commit", json={"message": "test"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert "approval" in payload["message"].lower()


def test_browser_click_endpoint_creates_approval():
    response = request(
        "POST",
        "/browser/click",
        json={"url": "https://example.com", "selector": "#login"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert "approval" in payload["message"].lower()


def test_browser_fill_endpoint_requires_selector():
    response = request(
        "POST",
        "/browser/fill",
        json={"url": "https://example.com", "value": "test@test.com"},
    )

    assert response.status_code == 422
    payload = response.json()
    assert payload["ok"] is False


def test_browser_wait_endpoint_validates_timeout():
    response = request(
        "POST",
        "/browser/wait",
        json={
            "url": "https://example.com",
            "selector": "#result",
            "timeout_ms": 0,
        },
    )

    assert response.status_code == 422
    payload = response.json()
    assert payload["ok"] is False


def test_browser_open_session_endpoint_creates_approval():
    response = request(
        "POST",
        "/browser/sessions",
        json={"url": "https://example.com", "mode": "visible"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert "approval" in payload["message"].lower()


def test_browser_sessions_endpoint_lists_sessions():
    response = request("GET", "/browser/sessions")

    assert response.status_code == 200
    assert response.json() == {"ok": True, "sessions": []}


def test_browser_open_session_endpoint_rejects_invalid_mode():
    response = request(
        "POST",
        "/browser/sessions",
        json={"url": "https://example.com", "mode": "personal"},
    )

    assert response.status_code == 422
    payload = response.json()
    assert payload["ok"] is False


def test_browser_session_wait_endpoint_validates_timeout():
    response = request(
        "POST",
        "/browser/sessions/abc123/wait",
        json={"selector": "#result", "timeout_ms": 0},
    )

    assert response.status_code == 422
    payload = response.json()
    assert payload["ok"] is False
