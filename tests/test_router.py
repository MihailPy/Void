from void.core.router import Router


def test_router_remember_fact():
    route = Router().route("Запомни: Void сначала ищет tools")

    assert route.matched is True
    assert route.confidence >= 0.85
    assert route.action is not None
    assert route.action.action == "remember_fact"


def test_router_project_stats():
    route = Router().route("Сделай статистику проекта")

    assert route.matched is True
    assert route.action is not None
    assert route.action.action == "project_stats"


def test_router_list_scheduled_tasks():
    route = Router().route("Покажи scheduled tasks")

    assert route.matched is True
    assert route.action is not None
    assert route.action.action == "list_scheduled_tasks"


def test_router_read_facts():
    route = Router().route("Что ты помнишь?")

    assert route.matched is True
    assert route.action is not None
    assert route.action.action == "read_facts"


def test_router_read_file():
    route = Router().route("Прочитай файл README.md")

    assert route.matched is True
    assert route.action is not None
    assert route.action.action == "read_file"
    assert route.action.arguments == {"path": "README.md"}


def test_router_browser_extract_text():
    route = Router().route("Получи текст со страницы https://example.com")

    assert route.matched is True
    assert route.action is not None
    assert route.action.action == "browser_extract_text"
    assert route.action.arguments == {"url": "https://example.com"}


def test_router_browser_screenshot():
    route = Router().route("Сделай скриншот https://example.com")

    assert route.matched is True
    assert route.action is not None
    assert route.action.action == "browser_screenshot"
    assert route.action.arguments == {"url": "https://example.com"}


def test_router_browser_click():
    route = Router().route("click button #login on https://example.com")

    assert route.matched is True
    assert route.action is not None
    assert route.action.action == "browser_click"
    assert route.action.arguments == {
        "url": "https://example.com",
        "selector": "#login",
    }


def test_router_browser_fill():
    route = Router().route("fill input #email with test@test.com on https://example.com")

    assert route.matched is True
    assert route.action is not None
    assert route.action.action == "browser_fill"
    assert route.action.arguments == {
        "url": "https://example.com",
        "selector": "#email",
        "value": "test@test.com",
    }


def test_router_browser_submit():
    route = Router().route("submit form #login-form on https://example.com")

    assert route.matched is True
    assert route.action is not None
    assert route.action.action == "browser_submit"
    assert route.action.arguments == {
        "url": "https://example.com",
        "selector": "#login-form",
    }


def test_router_browser_wait():
    route = Router().route("wait for selector #result on https://example.com")

    assert route.matched is True
    assert route.action is not None
    assert route.action.action == "browser_wait_for_selector"
    assert route.action.arguments == {
        "url": "https://example.com",
        "selector": "#result",
    }


def test_router_browser_click_ru():
    route = Router().route("Нажми кнопку #login на https://example.com")

    assert route.matched is True
    assert route.action is not None
    assert route.action.action == "browser_click"
    assert route.action.arguments == {
        "url": "https://example.com",
        "selector": "#login",
    }


def test_router_git_status():
    route = Router().route("git status")

    assert route.matched is True
    assert route.action is not None
    assert route.action.action == "git_status"


def test_router_git_diff():
    route = Router().route("покажи diff")

    assert route.matched is True
    assert route.action is not None
    assert route.action.action == "git_diff"


def test_router_git_suggest_commit_message():
    route = Router().route("какой commit написать")

    assert route.matched is True
    assert route.action is not None
    assert route.action.action == "git_suggest_commit_message"


def test_router_git_commit_with_message():
    route = Router().route("сделай commit с сообщением test")

    assert route.matched is True
    assert route.action is not None
    assert route.action.action == "git_commit"
    assert route.action.arguments == {"message": "test"}
