"""Deterministic browser route matching."""

from void.core.routing import extract_url
from void.core.types import AgentAction, RouteResult


def match(text: str, lowered: str) -> RouteResult | None:
    url = extract_url(text)
    if url is None:
        return None

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
