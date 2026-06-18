import pytest

from void.tools.browser_tools import browser_allowed, validate_url
from void.tools.builtin import build_registry


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

    for name in (
        "browser_extract_text",
        "browser_screenshot",
        "browser_links",
        "browser_title",
        "browser_task",
    ):
        tool = registry.get(name)
        assert tool is not None
        assert tool.terminal is True
        assert tool.requires_confirmation is True
