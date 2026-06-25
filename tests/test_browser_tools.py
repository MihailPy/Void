import pytest

from void.tools.browser_tools import browser_allowed, validate_url
from void.tools.builtin import build_registry
from void.core.permissions import list_approvals
from void.core.types import AgentAction


def test_validate_url_adds_https_when_scheme_missing():
    assert validate_url("example.com/path") == "https://example.com/path"


def test_validate_url_rejects_blocked_schemes():
    for url in (
        "file:///tmp/example.html",
        "javascript:alert(1)",
        "data:text/plain,hello",
    ):
        with pytest.raises(ValueError):
            validate_url(url)
        assert browser_allowed(url) is False


def test_validate_url_rejects_empty_host():
    with pytest.raises(ValueError):
        validate_url("https:///missing-host")


def test_browser_tools_registered_with_confirmation():
    registry = build_registry()

    expected = {
        "browser_extract_text": "network",
        "browser_screenshot": "network",
        "browser_links": "network",
        "browser_title": "network",
        "browser_task": "network",
        "browser_click": "write",
        "browser_fill": "write",
        "browser_submit": "write",
        "browser_wait_for_selector": "network",
        "browser_open_session": "network",
        "browser_list_sessions": "read",
        "browser_session_status": "read",
        "browser_close_session": "write",
        "browser_close_all_sessions": "destructive",
        "browser_session_click": "write",
        "browser_session_fill": "write",
        "browser_session_submit": "write",
        "browser_session_wait_for_selector": "network",
    }
    for name, risk_level in expected.items():
        tool = registry.get(name)
        assert tool is not None
        assert tool.terminal is True
        assert tool.requires_confirmation is (risk_level != "read")
        assert tool.category == "browser"
        assert tool.risk_level == risk_level


def test_interactive_browser_tool_creates_approval():
    registry = build_registry()

    result = registry.execute(
        AgentAction(
            "browser_click",
            {"url": "https://example.com", "selector": "#login"},
            "test",
        )
    )

    assert result.ok is True
    assert "approval" in result.content.lower()
    approvals = list_approvals()
    assert len(approvals) == 1
    assert approvals[0]["action"] == "browser_click"
    assert approvals[0]["category"] == "browser"
    assert approvals[0]["risk_level"] == "write"


def test_browser_open_session_creates_approval():
    registry = build_registry()

    result = registry.execute(
        AgentAction(
            "browser_open_session",
            {"url": "https://example.com", "mode": "visible"},
            "test",
        )
    )

    assert result.ok is True
    assert "approval" in result.content.lower()
    approvals = list_approvals()
    assert approvals[0]["action"] == "browser_open_session"
    assert approvals[0]["category"] == "browser"
    assert approvals[0]["risk_level"] == "network"


def test_read_only_session_tools_do_not_require_confirmation():
    registry = build_registry()

    assert registry.get("browser_list_sessions").requires_confirmation is False
    assert registry.get("browser_session_status").requires_confirmation is False


def test_browser_session_manager_rejects_invalid_mode():
    from void.core.browser_sessions import BrowserSessionManager

    manager = BrowserSessionManager()

    with pytest.raises(ValueError, match="Mode must be one of"):
        manager.open_session("https://example.com", "personal-chrome")


def test_browser_session_manager_enforces_max_sessions():
    from void.core.browser_sessions import BrowserSessionManager, MAX_SESSIONS

    manager = BrowserSessionManager()
    manager._sessions = {str(index): object() for index in range(MAX_SESSIONS)}

    with pytest.raises(ValueError, match="Maximum open browser sessions"):
        manager.open_session("https://example.com", "headless")
