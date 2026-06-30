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


def test_router_list_projects():
    route = Router().route("покажи проекты")

    assert route.matched is True
    assert route.action is not None
    assert route.action.action == "list_projects"


def test_router_current_project():
    route = Router().route("what project am I working on")

    assert route.matched is True
    assert route.action is not None
    assert route.action.action == "get_current_project"


def test_router_describe_current_project():
    route = Router().route("опиши текущий проект")

    assert route.matched is True
    assert route.action is not None
    assert route.action.action == "describe_current_project"


def test_router_set_current_project():
    route = Router().route("switch project to Void")

    assert route.matched is True
    assert route.action is not None
    assert route.action.action == "set_current_project"
    assert route.action.arguments == {"project": "Void"}


def test_router_switch_project_missing_project_requests_clarification():
    route = Router().route("switch project")

    assert route.matched is True
    assert route.action is None
    assert route.clarification is not None
    assert route.clarification.clarification_type == "project_selection"


def test_router_open_project_repo():
    route = Router().route("open Void project on github")

    assert route.matched is True
    assert route.action is not None
    assert route.action.action == "open_project_repo"
    assert route.action.arguments == {"project": "Void"}


def test_router_open_project_repo_missing_project_requests_clarification():
    route = Router().route("открой проект на github")

    assert route.matched is True
    assert route.action is None
    assert route.clarification is not None
    assert route.clarification.clarification_type == "project_selection"


def test_router_list_project_commands():
    route = Router().route("покажи команды проекта")

    assert route.matched is True
    assert route.action is not None
    assert route.action.action == "list_project_commands"


def test_router_run_project_command_by_key():
    route = Router().route("run project command verify")

    assert route.matched is True
    assert route.action is not None
    assert route.action.action == "run_project_command"
    assert route.action.arguments == {"command_key": "verify"}


def test_router_run_project_command_missing_key_requests_clarification():
    route = Router().route("запусти команду проекта")

    assert route.matched is True
    assert route.action is None
    assert route.clarification is not None
    assert route.clarification.clarification_type == "command_selection"


def test_router_run_tests_maps_to_project_command():
    route = Router().route("запусти тесты")

    assert route.matched is True
    assert route.action is not None
    assert route.action.action == "run_project_command"
    assert route.action.arguments == {"command_key": "test"}


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


def test_router_browser_open_visible_session():
    route = Router().route("open visible browser session https://example.com")

    assert route.matched is True
    assert route.action is not None
    assert route.action.action == "browser_open_session"
    assert route.action.arguments == {
        "url": "https://example.com",
        "mode": "visible",
    }


def test_router_browser_open_headless_session_ru():
    route = Router().route("открой фоновую browser session https://example.com")

    assert route.matched is True
    assert route.action is not None
    assert route.action.action == "browser_open_session"
    assert route.action.arguments == {
        "url": "https://example.com",
        "mode": "headless",
    }


def test_router_browser_list_sessions():
    route = Router().route("list browser sessions")

    assert route.matched is True
    assert route.action is not None
    assert route.action.action == "browser_list_sessions"
    assert route.action.arguments == {}


def test_router_browser_session_status():
    route = Router().route("browser session status abc123")

    assert route.matched is True
    assert route.action is not None
    assert route.action.action == "browser_session_status"
    assert route.action.arguments == {"session_id": "abc123"}


def test_router_browser_session_click():
    route = Router().route("click #login in browser session abc123")

    assert route.matched is True
    assert route.action is not None
    assert route.action.action == "browser_session_click"
    assert route.action.arguments == {
        "session_id": "abc123",
        "selector": "#login",
    }


def test_router_browser_session_fill():
    route = Router().route("fill #email with test@test.com in browser session abc123")

    assert route.matched is True
    assert route.action is not None
    assert route.action.action == "browser_session_fill"
    assert route.action.arguments == {
        "session_id": "abc123",
        "selector": "#email",
        "value": "test@test.com",
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
