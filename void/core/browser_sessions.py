"""In-memory Playwright browser session manager."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import uuid4

from void.core.browser_safety import DEFAULT_TIMEOUT_MS, validate_url
from void.core.types import ToolResult

ALLOWED_MODES = {"headless", "visible"}
MAX_SESSIONS = 3


@dataclass
class _BrowserSession:
    session_id: str
    mode: str
    url: str
    created_at: str
    last_used_at: str
    manager: Any
    browser: Any
    context: Any
    page: Any
    title: str | None = None


class BrowserSessionManager:
    """Small explicit manager for browser sessions opened by Void."""

    def __init__(self) -> None:
        self._sessions: dict[str, _BrowserSession] = {}

    def open_session(self, url: str, mode: str = "headless") -> dict[str, Any]:
        clean_mode = mode.strip().casefold()
        if clean_mode not in ALLOWED_MODES:
            raise ValueError("Mode must be one of: headless, visible.")
        if len(self._sessions) >= MAX_SESSIONS:
            raise ValueError(f"Maximum open browser sessions reached: {MAX_SESSIONS}.")

        normalized_url = validate_url(url)
        manager = None
        browser = None
        context = None
        try:
            from playwright.sync_api import sync_playwright

            manager = sync_playwright().start()
            browser = manager.chromium.launch(headless=clean_mode == "headless")
            context = browser.new_context()
            page = context.new_page()
            page.set_default_timeout(DEFAULT_TIMEOUT_MS)
            page.goto(normalized_url, wait_until="domcontentloaded")
            now = _now()
            session = _BrowserSession(
                session_id=uuid4().hex[:8],
                mode=clean_mode,
                url=normalized_url,
                created_at=now,
                last_used_at=now,
                manager=manager,
                browser=browser,
                context=context,
                page=page,
                title=_safe_title(page),
            )
            self._sessions[session.session_id] = session
            return self._metadata(session)
        except Exception:
            if context is not None:
                _safe_close(context)
            if browser is not None:
                _safe_close(browser)
            if manager is not None:
                _safe_stop(manager)
            raise

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        session = self._sessions.get(session_id)
        if session is None:
            return None
        metadata = self._touch_or_stale(session)
        if metadata is None:
            self._drop_stale(session_id)
            return None
        return metadata

    def list_sessions(self) -> list[dict[str, Any]]:
        stale: list[str] = []
        sessions: list[dict[str, Any]] = []
        for session_id, session in self._sessions.items():
            metadata = self._touch_or_stale(session)
            if metadata is None:
                stale.append(session_id)
            else:
                sessions.append(metadata)
        for session_id in stale:
            self._drop_stale(session_id)
        return sessions

    def close_session(self, session_id: str) -> bool:
        session = self._sessions.pop(session_id, None)
        if session is None:
            return False
        self._close(session)
        return True

    def close_all_sessions(self) -> int:
        count = 0
        for session_id in list(self._sessions):
            if self.close_session(session_id):
                count += 1
        return count

    def click(self, session_id: str, selector: str) -> ToolResult:
        session = self._session_or_result(session_id)
        if isinstance(session, ToolResult):
            return session
        clean_selector = _clean_selector(selector)
        if clean_selector is None:
            return ToolResult(ok=False, content="Selector is required.")
        try:
            session.page.wait_for_load_state("load")
            session.page.locator(clean_selector).first.click()
            metadata = self._touch(session)
            return ToolResult(
                ok=True,
                content=f"Clicked selector {clean_selector!r} in browser session {session_id}.",
                data={"session": metadata, "selector": clean_selector},
            )
        except Exception as error:
            return self._handle_action_error(session_id, error)

    def fill(self, session_id: str, selector: str, value: str) -> ToolResult:
        session = self._session_or_result(session_id)
        if isinstance(session, ToolResult):
            return session
        clean_selector = _clean_selector(selector)
        if clean_selector is None:
            return ToolResult(ok=False, content="Selector is required.")
        try:
            session.page.wait_for_load_state("load")
            session.page.locator(clean_selector).first.fill(value)
            metadata = self._touch(session)
            return ToolResult(
                ok=True,
                content=f"Filled selector {clean_selector!r} in browser session {session_id}.",
                data={"session": metadata, "selector": clean_selector},
            )
        except Exception as error:
            return self._handle_action_error(session_id, error)

    def submit(self, session_id: str, selector: str) -> ToolResult:
        session = self._session_or_result(session_id)
        if isinstance(session, ToolResult):
            return session
        clean_selector = _clean_selector(selector)
        if clean_selector is None:
            return ToolResult(ok=False, content="Selector is required.")
        try:
            session.page.wait_for_load_state("load")
            locator = session.page.locator(clean_selector).first
            tag_name = locator.evaluate("element => element.tagName.toLowerCase()")
            if tag_name == "form":
                locator.evaluate(
                    "element => element.requestSubmit ? element.requestSubmit() : element.submit()"
                )
            else:
                locator.click()
            metadata = self._touch(session)
            return ToolResult(
                ok=True,
                content=f"Submitted selector {clean_selector!r} in browser session {session_id}.",
                data={"session": metadata, "selector": clean_selector},
            )
        except Exception as error:
            return self._handle_action_error(session_id, error)

    def wait_for_selector(
        self,
        session_id: str,
        selector: str,
        timeout_ms: int = 10000,
    ) -> ToolResult:
        session = self._session_or_result(session_id)
        if isinstance(session, ToolResult):
            return session
        clean_selector = _clean_selector(selector)
        if clean_selector is None:
            return ToolResult(ok=False, content="Selector is required.")
        if timeout_ms < 1:
            return ToolResult(ok=False, content="timeout_ms must be greater than 0.")
        try:
            session.page.wait_for_load_state("load")
            session.page.wait_for_selector(clean_selector, timeout=timeout_ms)
            metadata = self._touch(session)
            return ToolResult(
                ok=True,
                content=(
                    f"Selector {clean_selector!r} appeared in browser session "
                    f"{session_id} within {timeout_ms} ms."
                ),
                data={
                    "session": metadata,
                    "selector": clean_selector,
                    "timeout_ms": timeout_ms,
                },
            )
        except Exception as error:
            return self._handle_action_error(session_id, error)

    def _session_or_result(self, session_id: str) -> _BrowserSession | ToolResult:
        session = self._sessions.get(session_id)
        if session is None:
            return ToolResult(ok=False, content=f"Browser session not found: {session_id}.")
        if self._touch_or_stale(session) is None:
            self._drop_stale(session_id)
            return ToolResult(
                ok=False,
                content=f"Browser session is no longer available: {session_id}.",
            )
        return session

    def _touch(self, session: _BrowserSession) -> dict[str, Any]:
        session.last_used_at = _now()
        session.title = _safe_title(session.page)
        try:
            current_url = session.page.url
        except Exception:
            current_url = ""
        if current_url:
            session.url = current_url
        return self._metadata(session)

    def _touch_or_stale(self, session: _BrowserSession) -> dict[str, Any] | None:
        try:
            return self._touch(session)
        except Exception:
            return None

    def _metadata(self, session: _BrowserSession) -> dict[str, Any]:
        return {
            "session_id": session.session_id,
            "mode": session.mode,
            "url": session.url,
            "created_at": session.created_at,
            "last_used_at": session.last_used_at,
            "title": session.title,
        }

    def _handle_action_error(self, session_id: str, error: Exception) -> ToolResult:
        if _looks_closed_error(error):
            self._drop_stale(session_id)
            return ToolResult(
                ok=False,
                content=f"Browser session closed or browser process died: {session_id}.",
            )
        return ToolResult(ok=False, content=f"Browser session action failed: {error}")

    def _drop_stale(self, session_id: str) -> None:
        session = self._sessions.pop(session_id, None)
        if session is not None:
            self._close(session)

    def _close(self, session: _BrowserSession) -> None:
        try:
            _safe_close(session.context)
        finally:
            try:
                _safe_close(session.browser)
            finally:
                _safe_stop(session.manager)


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _safe_title(page: Any) -> str | None:
    try:
        return page.title()
    except Exception:
        return None


def _clean_selector(selector: str) -> str | None:
    clean_selector = selector.strip()
    return clean_selector or None


def _safe_close(value: Any) -> None:
    try:
        value.close()
    except Exception:
        pass


def _safe_stop(value: Any) -> None:
    try:
        value.stop()
    except Exception:
        pass


def _looks_closed_error(error: Exception) -> bool:
    text = str(error).casefold()
    return any(
        marker in text
        for marker in (
            "has been closed",
            "target closed",
            "browser has been closed",
            "browser closed",
            "process died",
        )
    )


manager = BrowserSessionManager()


def open_session(url: str, mode: str = "headless") -> dict[str, Any]:
    return manager.open_session(url, mode)


def get_session(session_id: str) -> dict[str, Any] | None:
    return manager.get_session(session_id)


def list_sessions() -> list[dict[str, Any]]:
    return manager.list_sessions()


def close_session(session_id: str) -> bool:
    return manager.close_session(session_id)


def close_all_sessions() -> int:
    return manager.close_all_sessions()


def click(session_id: str, selector: str) -> ToolResult:
    return manager.click(session_id, selector)


def fill(session_id: str, selector: str, value: str) -> ToolResult:
    return manager.fill(session_id, selector, value)


def submit(session_id: str, selector: str) -> ToolResult:
    return manager.submit(session_id, selector)


def wait_for_selector(
    session_id: str,
    selector: str,
    timeout_ms: int = 10000,
) -> ToolResult:
    return manager.wait_for_selector(session_id, selector, timeout_ms)
