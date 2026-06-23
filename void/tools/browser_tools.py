"""Approval-gated browser tools backed by Playwright."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse, urlunparse

from void.core.safety import safe_project_path
from void.core.types import ToolDefinition, ToolResult

BLOCKED_SCHEMES = {"file", "javascript", "data"}
ALLOWED_SCHEMES = {"http", "https"}
SCREENSHOTS_DIR = safe_project_path("workspace/screenshots")
DEFAULT_TIMEOUT_MS = 15000
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


def validate_url(url: str) -> str:
    """Normalize and validate a browser URL."""
    clean_url = url.strip()
    if not clean_url:
        raise ValueError("URL is required.")

    parsed = urlparse(clean_url)
    if parsed.scheme.casefold() in BLOCKED_SCHEMES:
        raise ValueError(f"URL scheme is blocked: {parsed.scheme}")

    if not parsed.scheme:
        clean_url = f"https://{clean_url}"
        parsed = urlparse(clean_url)

    scheme = parsed.scheme.casefold()
    if scheme not in ALLOWED_SCHEMES:
        raise ValueError("Only http and https URLs are allowed.")
    if not parsed.netloc:
        raise ValueError("URL host is required.")

    return urlunparse(
        (
            scheme,
            parsed.netloc,
            parsed.path or "",
            parsed.params,
            parsed.query,
            parsed.fragment,
        )
    )


def browser_allowed(url: str) -> bool:
    try:
        validate_url(url)
    except ValueError:
        return False
    return True


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
    ]
