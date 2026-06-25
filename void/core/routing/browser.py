"""Deterministic browser route matching."""

import re

from void.core.routing import clean, extract_url
from void.core.types import AgentAction, RouteResult


def _selector(value: str) -> str:
    selector = clean(value)
    selector = re.sub(
        r"^(?:button|кнопк[ау]|input|поле|form|форм[ау]|selector|селектор)\s+",
        "",
        selector,
        flags=re.IGNORECASE,
    )
    return clean(selector)


def _without_url(text: str, url: str) -> str:
    return text.replace(url, "", 1).strip()


def _session_id(value: str) -> str:
    return clean(value).split()[0] if clean(value) else ""


def _match_open_session(text: str, lowered: str, url: str) -> RouteResult | None:
    mode = ""
    if re.search(r"\bopen\s+visible\s+browser\s+session\b", lowered) or (
        "открой видимую browser session" in lowered
    ):
        mode = "visible"
    elif re.search(r"\bopen\s+headless\s+browser\s+session\b", lowered) or (
        "открой фоновую browser session" in lowered
    ):
        mode = "headless"

    if not mode:
        return None
    return RouteResult(
        matched=True,
        confidence=0.92,
        action=AgentAction(
            "browser_open_session",
            {"url": url, "mode": mode},
            "User asks to open a managed browser session.",
        ),
    )


def _match_session_without_url(text: str, lowered: str) -> RouteResult | None:
    if lowered in {"browser sessions", "list browser sessions"} or (
        "покажи browser sessions" in lowered
    ):
        return RouteResult(
            matched=True,
            confidence=0.92,
            action=AgentAction(
                "browser_list_sessions",
                {},
                "User asks to list managed browser sessions.",
            ),
        )

    match = re.search(
        r"(?:browser\s+session\s+status|статус\s+browser\s+session)\s+([A-Za-z0-9_-]+)",
        text,
        re.IGNORECASE,
    )
    if match:
        return RouteResult(
            matched=True,
            confidence=0.92,
            action=AgentAction(
                "browser_session_status",
                {"session_id": _session_id(match.group(1))},
                "User asks for managed browser session status.",
            ),
        )

    match = re.search(
        r"(?:close|закрой)\s+browser\s+session\s+([A-Za-z0-9_-]+)",
        text,
        re.IGNORECASE,
    )
    if match:
        return RouteResult(
            matched=True,
            confidence=0.92,
            action=AgentAction(
                "browser_close_session",
                {"session_id": _session_id(match.group(1))},
                "User asks to close a managed browser session.",
            ),
        )

    match = re.search(
        r"click\s+(.+?)\s+in\s+browser\s+session\s+([A-Za-z0-9_-]+)",
        text,
        re.IGNORECASE,
    )
    if match:
        return RouteResult(
            matched=True,
            confidence=0.92,
            action=AgentAction(
                "browser_session_click",
                {"selector": _selector(match.group(1)), "session_id": _session_id(match.group(2))},
                "User asks to click in a managed browser session.",
            ),
        )

    match = re.search(
        r"fill\s+(.+?)\s+with\s+(.+?)\s+in\s+browser\s+session\s+([A-Za-z0-9_-]+)",
        text,
        re.IGNORECASE,
    )
    if match:
        return RouteResult(
            matched=True,
            confidence=0.92,
            action=AgentAction(
                "browser_session_fill",
                {
                    "selector": _selector(match.group(1)),
                    "value": clean(match.group(2)),
                    "session_id": _session_id(match.group(3)),
                },
                "User asks to fill in a managed browser session.",
            ),
        )

    match = re.search(
        r"submit\s+(.+?)\s+in\s+browser\s+session\s+([A-Za-z0-9_-]+)",
        text,
        re.IGNORECASE,
    )
    if match:
        return RouteResult(
            matched=True,
            confidence=0.92,
            action=AgentAction(
                "browser_session_submit",
                {"selector": _selector(match.group(1)), "session_id": _session_id(match.group(2))},
                "User asks to submit in a managed browser session.",
            ),
        )

    match = re.search(
        r"wait\s+for\s+(.+?)\s+in\s+browser\s+session\s+([A-Za-z0-9_-]+)",
        text,
        re.IGNORECASE,
    )
    if match:
        return RouteResult(
            matched=True,
            confidence=0.92,
            action=AgentAction(
                "browser_session_wait_for_selector",
                {"selector": _selector(match.group(1)), "session_id": _session_id(match.group(2))},
                "User asks to wait in a managed browser session.",
            ),
        )

    return None


def _match_click(text: str, lowered: str, url: str) -> RouteResult | None:
    selector = ""
    if lowered.startswith("browser click"):
        payload = re.sub(
            r"^browser\s+click\s+",
            "",
            _without_url(text, url),
            flags=re.IGNORECASE,
        )
        selector = _selector(payload)
    else:
        match = re.search(
            rf"(?:click|нажми|кликни)\s+(.+?)\s+(?:on|на)\s+{re.escape(url)}",
            text,
            re.IGNORECASE,
        )
        if match:
            selector = _selector(match.group(1))

    if not selector:
        return None
    return RouteResult(
        matched=True,
        confidence=0.9,
        action=AgentAction(
            "browser_click",
            {"url": url, "selector": selector},
            "User asks to click a selector on a web page.",
        ),
    )


def _match_fill(text: str, lowered: str, url: str) -> RouteResult | None:
    selector = ""
    value = ""
    if lowered.startswith("browser fill"):
        payload = _without_url(text, url)
        payload = re.sub(r"^browser\s+fill\s+", "", payload, flags=re.IGNORECASE)
        parts = payload.split(maxsplit=1)
        if len(parts) == 2:
            selector = _selector(parts[0])
            value = clean(parts[1])
    else:
        match = re.search(
            rf"(?:fill|заполни)\s+(?:input\s+|поле\s+)?(.+?)\s+(?:with|значением)\s+(.+?)\s+(?:on|на)\s+{re.escape(url)}",
            text,
            re.IGNORECASE,
        )
        if match:
            selector = _selector(match.group(1))
            value = clean(match.group(2))

    if not selector or not value:
        return None
    return RouteResult(
        matched=True,
        confidence=0.9,
        action=AgentAction(
            "browser_fill",
            {"url": url, "selector": selector, "value": value},
            "User asks to fill a selector on a web page.",
        ),
    )


def _match_submit(text: str, lowered: str, url: str) -> RouteResult | None:
    selector = ""
    if lowered.startswith("browser submit"):
        payload = re.sub(
            r"^browser\s+submit\s+",
            "",
            _without_url(text, url),
            flags=re.IGNORECASE,
        )
        selector = _selector(payload)
    else:
        match = re.search(
            rf"(?:submit|отправь)\s+(.+?)\s+(?:on|на)\s+{re.escape(url)}",
            text,
            re.IGNORECASE,
        )
        if match:
            selector = _selector(match.group(1))

    if not selector:
        return None
    return RouteResult(
        matched=True,
        confidence=0.9,
        action=AgentAction(
            "browser_submit",
            {"url": url, "selector": selector},
            "User asks to submit a selector on a web page.",
        ),
    )


def _match_wait(text: str, lowered: str, url: str) -> RouteResult | None:
    selector = ""
    if lowered.startswith("browser wait"):
        payload = re.sub(
            r"^browser\s+wait\s+",
            "",
            _without_url(text, url),
            flags=re.IGNORECASE,
        )
        selector = _selector(payload)
    else:
        match = re.search(
            rf"(?:wait for selector|дождись селектор[а]?|жди селектор)\s+(.+?)\s+(?:on|на)\s+{re.escape(url)}",
            text,
            re.IGNORECASE,
        )
        if match:
            selector = _selector(match.group(1))

    if not selector:
        return None
    return RouteResult(
        matched=True,
        confidence=0.9,
        action=AgentAction(
            "browser_wait_for_selector",
            {"url": url, "selector": selector},
            "User asks to wait for a selector on a web page.",
        ),
    )


def match(text: str, lowered: str) -> RouteResult | None:
    session_route = _match_session_without_url(text, lowered)
    if session_route is not None:
        return session_route

    url = extract_url(text)
    if url is None:
        return None

    open_session_route = _match_open_session(text, lowered, url)
    if open_session_route is not None:
        return open_session_route

    for matcher in (_match_click, _match_fill, _match_submit, _match_wait):
        route = matcher(text, lowered, url)
        if route is not None:
            return route

    browser_routes = (
        (
            (
                "получи текст со страницы",
                "извлеки текст с сайта",
                "открой сайт",
            ),
            "browser_extract_text",
            {"url": url},
            "User asks to extract text from a web page.",
        ),
        (
            (
                "сделай скриншот",
                "скриншот сайта",
            ),
            "browser_screenshot",
            {"url": url},
            "User asks to take a screenshot of a web page.",
        ),
        (
            (
                "покажи ссылки на странице",
                "собери ссылки с",
            ),
            "browser_links",
            {"url": url},
            "User asks to collect links from a web page.",
        ),
        (
            (
                "какой title у",
                "заголовок страницы",
            ),
            "browser_title",
            {"url": url},
            "User asks for the title of a web page.",
        ),
        (
            (
                "проверь сайт",
                "изучи страницу",
            ),
            "browser_task",
            {"url": url, "instruction": text},
            "User asks for a read-only browser page inspection.",
        ),
    )
    for phrases, action, arguments, reason in browser_routes:
        if any(phrase in lowered for phrase in phrases):
            return RouteResult(
                matched=True,
                confidence=0.9,
                action=AgentAction(action, arguments, reason),
            )

    return None
