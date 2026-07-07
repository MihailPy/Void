"""Deterministic routing for common Void requests."""

from void.core.routing import (
    activity,
    browser,
    capabilities,
    files,
    git,
    memory,
    project_context,
    scheduler,
)
from void.core.types import RouteResult


class Router:
    """Simple domain router that avoids LLM calls for known tasks."""

    def route(self, user_input: str) -> RouteResult:
        text = user_input.strip()
        lowered = text.lower()

        for matcher in (
            activity.match,
            git.match,
            project_context.match,
            browser.match,
            scheduler.match,
            memory.match,
            files.match,
            capabilities.match,
        ):
            route = matcher(text, lowered)
            if route is not None:
                return route

        return RouteResult(matched=False, confidence=0.0)
