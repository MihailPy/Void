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
