from void.core import capabilities


def test_empty_capability_storage_lists_empty_sections():
    records = capabilities.list_capabilities()

    assert records == {"installed": [], "requested": [], "rejected": []}


def test_add_requested_capability():
    result = capabilities.add_requested_capability(
        name="web_search",
        description="Search the web.",
        problem="Need fresh data.",
        reason="No existing tool.",
    )

    assert result["ok"] is True
    records = capabilities.list_capabilities()
    assert [item["name"] for item in records["requested"]] == ["web_search"]


def test_duplicate_capability_name_is_not_added_twice():
    capabilities.add_requested_capability("web_search", "Search.", "Need data.", "No tool.")
    result = capabilities.add_requested_capability("WEB_SEARCH", "Search.", "Need data.", "No tool.")

    records = capabilities.list_capabilities()
    assert result["duplicate"] is True
    assert len(records["requested"]) == 1


def test_mark_capability_installed_moves_requested_record():
    capabilities.add_requested_capability("web_search", "Search.", "Need data.", "No tool.")

    result = capabilities.mark_capability_installed("web_search")

    assert result["ok"] is True
    records = capabilities.list_capabilities()
    assert records["requested"] == []
    assert [item["name"] for item in records["installed"]] == ["web_search"]
    assert records["installed"][0]["status"] == "installed"


def test_reject_capability_moves_requested_record():
    capabilities.add_requested_capability("web_search", "Search.", "Need data.", "No tool.")

    result = capabilities.reject_capability("web_search", "Not needed.")

    assert result["ok"] is True
    records = capabilities.list_capabilities()
    assert records["requested"] == []
    assert [item["name"] for item in records["rejected"]] == ["web_search"]
    assert records["rejected"][0]["status"] == "rejected"
    assert records["rejected"][0]["reason"] == "Not needed."
