"""Approval-gated browser tools backed by Playwright."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import urljoin

from void.core import browser_safety
from void.core.safety import safe_project_path
from void.core.types import ToolDefinition, ToolResult

BLOCKED_SCHEMES = browser_safety.BLOCKED_SCHEMES
ALLOWED_SCHEMES = browser_safety.ALLOWED_SCHEMES
DEFAULT_TIMEOUT_MS = browser_safety.DEFAULT_TIMEOUT_MS
validate_url = browser_safety.validate_url
browser_allowed = browser_safety.browser_allowed
SCREENSHOTS_DIR = safe_project_path("workspace/screenshots")
TASK_TEXT_CHARS = 2000
TASK_LINK_LIMIT = 10

UNSUPPORTED_TASK_KEYWORDS = (
    "click",
    "клик",
    "нажми",
    "login",
    "log in",
    "sign in",
    "signin",
    "логин",
    "войти",
    "авториз",
    "form",
    "форма",
    "заполни",
    "fill",
    "password",
    "пароль",
    "buy",
    "purchase",
    "куп",
    "order",
    "заказ",
    "submit",
    "send",
    "отправ",
    "message",
    "сообщение",
    "javascript",
    "js",
    "script",
    "скрипт",
)

def _playwright() -> Any:
    from playwright.sync_api import sync_playwright

    return sync_playwright()


def _open_page(url: str):
    normalized_url = validate_url(url)
    manager = _playwright().start()
    browser = manager.chromium.launch(headless=True)
    context = browser.new_context()
    page = context.new_page()
    page.set_default_timeout(DEFAULT_TIMEOUT_MS)
    page.goto(normalized_url, wait_until="domcontentloaded")
    return manager, browser, context, page, normalized_url


def _close_browser(manager: Any, browser: Any, context: Any) -> None:
    try:
        context.close()
    finally:
        try:
            browser.close()
        finally:
            manager.stop()


def _body_text(page: Any, max_chars: int) -> str:
    text = page.evaluate("() => document.body ? document.body.innerText : ''")
    if not isinstance(text, str):
        text = ""
    return text[: max(0, max_chars)]


def _collect_links(page: Any, base_url: str, limit: int) -> list[dict[str, str]]:
    raw_links = page.eval_on_selector_all(
        "a[href]",
        """elements => elements.map((element) => ({
            text: (element.innerText || element.textContent || '').trim(),
            href: element.getAttribute('href') || ''
        }))""",
    )
    links: list[dict[str, str]] = []
    for item in raw_links if isinstance(raw_links, list) else []:
        if not isinstance(item, dict):
            continue
        href = str(item.get("href", "")).strip()
        if not href:
            continue
        normalized_href = urljoin(base_url, href)
        if not browser_allowed(normalized_href):
            continue
        links.append(
            {
                "text": str(item.get("text", "")).strip(),
                "href": validate_url(normalized_href),
            }
        )
        if len(links) >= max(0, limit):
            break
    return links


def _safe_screenshot_path(path: str) -> Path:
    screenshot_path = safe_project_path(path)
    screenshots_root = SCREENSHOTS_DIR.resolve()
    try:
        screenshot_path.resolve().relative_to(screenshots_root)
    except ValueError as error:
        raise ValueError("Screenshots must be saved inside workspace/screenshots/.") from error
    return screenshot_path


def browser_extract_text(url: str, max_chars: int = 5000) -> ToolResult:
    manager, browser, context, page, normalized_url = _open_page(url)
    try:
        text = _body_text(page, max_chars)
        return ToolResult(
            ok=True,
            content=f"Extracted text from {normalized_url}:\n\n{text}",
            data={"url": normalized_url, "text": text, "length": len(text)},
        )
    finally:
        _close_browser(manager, browser, context)


def browser_screenshot(url: str, path: str = "workspace/screenshots/page.png") -> ToolResult:
    screenshot_path = _safe_screenshot_path(path)
    manager, browser, context, page, normalized_url = _open_page(url)
    try:
        screenshot_path.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(screenshot_path), full_page=True)
        display_path = screenshot_path.relative_to(safe_project_path("."))
        return ToolResult(
            ok=True,
            content=f"Screenshot saved: {display_path}",
            data={"url": normalized_url, "path": str(display_path)},
        )
    finally:
        _close_browser(manager, browser, context)


def browser_links(url: str, limit: int = 50) -> ToolResult:
    manager, browser, context, page, normalized_url = _open_page(url)
    try:
        links = _collect_links(page, normalized_url, limit)
        if links:
            lines = [
                f"{index}. {link['text'] or '(no text)'} - {link['href']}"
                for index, link in enumerate(links, start=1)
            ]
            content = f"Links from {normalized_url}:\n" + "\n".join(lines)
        else:
            content = f"No links found on {normalized_url}."
        return ToolResult(
            ok=True,
            content=content,
            data={"url": normalized_url, "links": links, "count": len(links)},
        )
    finally:
        _close_browser(manager, browser, context)


def browser_title(url: str) -> ToolResult:
    manager, browser, context, page, normalized_url = _open_page(url)
    try:
        title = page.title()
        return ToolResult(
            ok=True,
            content=f"Title for {normalized_url}: {title}",
            data={"url": normalized_url, "title": title},
        )
    finally:
        _close_browser(manager, browser, context)


def browser_task(url: str, instruction: str) -> ToolResult:
    lowered = instruction.casefold()
    if any(keyword in lowered for keyword in UNSUPPORTED_TASK_KEYWORDS):
        return ToolResult(
            ok=False,
            content=(
                "browser_task currently supports read-only page inspection only. "
                "Clicks, login, forms, purchases, messages, JavaScript execution, and "
                "data submission need a separate capability such as "
                "browser_interactive_automation."
            ),
        )

    manager, browser, context, page, normalized_url = _open_page(url)
    try:
        title = page.title()
        text = _body_text(page, TASK_TEXT_CHARS)
        links = _collect_links(page, normalized_url, TASK_LINK_LIMIT)
        link_lines = [
            f"{index}. {link['text'] or '(no text)'} - {link['href']}"
            for index, link in enumerate(links, start=1)
        ]
        content = (
            f"Read-only browser task for {normalized_url}\n"
            f"Instruction: {instruction}\n"
            f"Title: {title}\n\n"
            f"Text excerpt:\n{text}\n\n"
            f"Links:\n{chr(10).join(link_lines) if link_lines else 'No links found.'}"
        )
        return ToolResult(
            ok=True,
            content=content,
            data={
                "url": normalized_url,
                "instruction": instruction,
                "title": title,
                "text_excerpt": text,
                "links": links,
            },
        )
    finally:
        _close_browser(manager, browser, context)


def browser_click(url: str, selector: str) -> ToolResult:
    clean_selector = selector.strip()
    if not clean_selector:
        raise ValueError("Selector is required.")

    manager, browser, context, page, normalized_url = _open_page(url)
    try:
        page.wait_for_load_state("load")
        page.locator(clean_selector).first.click()
        return ToolResult(
            ok=True,
            content=f"Clicked selector {clean_selector!r} on {normalized_url}.",
            data={"url": normalized_url, "selector": clean_selector},
        )
    finally:
        _close_browser(manager, browser, context)


def browser_fill(url: str, selector: str, value: str) -> ToolResult:
    clean_selector = selector.strip()
    if not clean_selector:
        raise ValueError("Selector is required.")

    manager, browser, context, page, normalized_url = _open_page(url)
    try:
        page.wait_for_load_state("load")
        page.locator(clean_selector).first.fill(value)
        return ToolResult(
            ok=True,
            content=f"Filled selector {clean_selector!r} on {normalized_url}.",
            data={"url": normalized_url, "selector": clean_selector},
        )
    finally:
        _close_browser(manager, browser, context)


def browser_submit(url: str, selector: str) -> ToolResult:
    clean_selector = selector.strip()
    if not clean_selector:
        raise ValueError("Selector is required.")

    manager, browser, context, page, normalized_url = _open_page(url)
    try:
        page.wait_for_load_state("load")
        locator = page.locator(clean_selector).first
        tag_name = locator.evaluate("element => element.tagName.toLowerCase()")
        if tag_name == "form":
            locator.evaluate(
                "element => element.requestSubmit ? element.requestSubmit() : element.submit()"
            )
        else:
            locator.click()
        return ToolResult(
            ok=True,
            content=f"Submitted selector {clean_selector!r} on {normalized_url}.",
            data={"url": normalized_url, "selector": clean_selector},
        )
    finally:
        _close_browser(manager, browser, context)


def browser_wait_for_selector(
    url: str,
    selector: str,
    timeout_ms: int = 10000,
) -> ToolResult:
    clean_selector = selector.strip()
    if not clean_selector:
        raise ValueError("Selector is required.")
    if timeout_ms < 1:
        raise ValueError("timeout_ms must be greater than 0.")

    manager, browser, context, page, normalized_url = _open_page(url)
    try:
        page.wait_for_load_state("load")
        page.wait_for_selector(clean_selector, timeout=timeout_ms)
        return ToolResult(
            ok=True,
            content=(
                f"Selector {clean_selector!r} appeared on {normalized_url} "
                f"within {timeout_ms} ms."
            ),
            data={
                "url": normalized_url,
                "selector": clean_selector,
                "timeout_ms": timeout_ms,
            },
        )
    finally:
        _close_browser(manager, browser, context)


def browser_open_session(url: str, mode: str = "headless") -> ToolResult:
    from void.core import browser_sessions

    session = browser_sessions.open_session(url, mode)
    return ToolResult(
        ok=True,
        content=(
            f"Opened {session['mode']} browser session {session['session_id']} "
            f"for {session['url']}."
        ),
        data={"session": session},
    )


def browser_list_sessions() -> ToolResult:
    from void.core import browser_sessions

    sessions = browser_sessions.list_sessions()
    if sessions:
        lines = [
            (
                f"{session['session_id']} | {session['mode']} | "
                f"{session['url']} | {session.get('title') or '(no title)'}"
            )
            for session in sessions
        ]
        content = "Browser sessions:\n" + "\n".join(lines)
    else:
        content = "No browser sessions are open."
    return ToolResult(ok=True, content=content, data={"sessions": sessions})


def browser_session_status(session_id: str) -> ToolResult:
    from void.core import browser_sessions

    session = browser_sessions.get_session(session_id)
    if session is None:
        return ToolResult(ok=False, content=f"Browser session not found: {session_id}.")
    return ToolResult(
        ok=True,
        content=(
            f"Browser session {session_id}: {session['mode']} {session['url']} "
            f"title={session.get('title') or '(no title)'}"
        ),
        data={"session": session},
    )


def browser_close_session(session_id: str) -> ToolResult:
    from void.core import browser_sessions

    if not browser_sessions.close_session(session_id):
        return ToolResult(ok=False, content=f"Browser session not found: {session_id}.")
    return ToolResult(ok=True, content=f"Closed browser session {session_id}.")


def browser_close_all_sessions() -> ToolResult:
    from void.core import browser_sessions

    count = browser_sessions.close_all_sessions()
    return ToolResult(ok=True, content=f"Closed {count} browser session(s).")


def browser_session_click(session_id: str, selector: str) -> ToolResult:
    from void.core import browser_sessions

    return browser_sessions.click(session_id, selector)


def browser_session_fill(session_id: str, selector: str, value: str) -> ToolResult:
    from void.core import browser_sessions

    return browser_sessions.fill(session_id, selector, value)


def browser_session_submit(session_id: str, selector: str) -> ToolResult:
    from void.core import browser_sessions

    return browser_sessions.submit(session_id, selector)


def browser_session_wait_for_selector(
    session_id: str,
    selector: str,
    timeout_ms: int = 10000,
) -> ToolResult:
    from void.core import browser_sessions

    return browser_sessions.wait_for_selector(session_id, selector, timeout_ms)


def definitions() -> list[ToolDefinition]:
    return [
        ToolDefinition(
            "browser_extract_text",
            "Open an http/https URL and extract visible body text.",
            browser_extract_text,
            terminal=True,
            requires_confirmation=True,
            category="browser",
            risk_level="network",
        ),
        ToolDefinition(
            "browser_screenshot",
            "Open an http/https URL and save a screenshot under workspace/screenshots/.",
            browser_screenshot,
            terminal=True,
            requires_confirmation=True,
            category="browser",
            risk_level="network",
        ),
        ToolDefinition(
            "browser_links",
            "Open an http/https URL and collect basic page links.",
            browser_links,
            terminal=True,
            requires_confirmation=True,
            category="browser",
            risk_level="network",
        ),
        ToolDefinition(
            "browser_title",
            "Open an http/https URL and return the page title.",
            browser_title,
            terminal=True,
            requires_confirmation=True,
            category="browser",
            risk_level="network",
        ),
        ToolDefinition(
            "browser_task",
            "Perform a read-only browser page inspection task.",
            browser_task,
            terminal=True,
            requires_confirmation=True,
            category="browser",
            risk_level="network",
        ),
        ToolDefinition(
            "browser_click",
            "Open an http/https URL and click a CSS selector.",
            browser_click,
            terminal=True,
            requires_confirmation=True,
            category="browser",
            risk_level="write",
        ),
        ToolDefinition(
            "browser_fill",
            "Open an http/https URL and fill an input or textarea selector.",
            browser_fill,
            terminal=True,
            requires_confirmation=True,
            category="browser",
            risk_level="write",
        ),
        ToolDefinition(
            "browser_submit",
            "Open an http/https URL and submit a form or click a submit selector.",
            browser_submit,
            terminal=True,
            requires_confirmation=True,
            category="browser",
            risk_level="write",
        ),
        ToolDefinition(
            "browser_wait_for_selector",
            "Open an http/https URL and wait for a CSS selector.",
            browser_wait_for_selector,
            terminal=True,
            requires_confirmation=True,
            category="browser",
            risk_level="network",
        ),
        ToolDefinition(
            "browser_open_session",
            "Open a managed Void browser session in headless or visible mode.",
            browser_open_session,
            terminal=True,
            requires_confirmation=True,
            category="browser",
            risk_level="network",
        ),
        ToolDefinition(
            "browser_list_sessions",
            "List managed Void browser sessions.",
            browser_list_sessions,
            terminal=True,
            requires_confirmation=False,
            category="browser",
            risk_level="read",
        ),
        ToolDefinition(
            "browser_session_status",
            "Return metadata for a managed Void browser session.",
            browser_session_status,
            terminal=True,
            requires_confirmation=False,
            category="browser",
            risk_level="read",
        ),
        ToolDefinition(
            "browser_close_session",
            "Close a managed Void browser session.",
            browser_close_session,
            terminal=True,
            requires_confirmation=True,
            category="browser",
            risk_level="write",
        ),
        ToolDefinition(
            "browser_close_all_sessions",
            "Close all managed Void browser sessions.",
            browser_close_all_sessions,
            terminal=True,
            requires_confirmation=True,
            category="browser",
            risk_level="destructive",
        ),
        ToolDefinition(
            "browser_session_click",
            "Click a CSS selector in an existing managed browser session.",
            browser_session_click,
            terminal=True,
            requires_confirmation=True,
            category="browser",
            risk_level="write",
        ),
        ToolDefinition(
            "browser_session_fill",
            "Fill a selector in an existing managed browser session.",
            browser_session_fill,
            terminal=True,
            requires_confirmation=True,
            category="browser",
            risk_level="write",
        ),
        ToolDefinition(
            "browser_session_submit",
            "Submit a form or click a submit selector in an existing managed browser session.",
            browser_session_submit,
            terminal=True,
            requires_confirmation=True,
            category="browser",
            risk_level="write",
        ),
        ToolDefinition(
            "browser_session_wait_for_selector",
            "Wait for a CSS selector in an existing managed browser session.",
            browser_session_wait_for_selector,
            terminal=True,
            requires_confirmation=True,
            category="browser",
            risk_level="network",
        ),
    ]
