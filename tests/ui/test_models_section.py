"""Settings → Models in a browser (openspec change model-settings-page): Your models and
Sources against a real `lado server`, the fake model server of tests/fake_model_server.py in
the test's process, and stand-ins of Claude Code, Codex CLI and OpenCode on the server's PATH
that print a version (Claude Code's aliases are its provider's own list; no CLI's list is
run here). On a computer and at a phone's width."""

import os
import re
import socket
import stat

import fake_model_server as fake
import pytest
from playwright.sync_api import Browser, Page, expect
from test_main_screen import log_in

from lado import model_settings, state

pytestmark = pytest.mark.ui

EMPTY = (
    "No models yet. Without them each agent runs on its CLI's default model. Tick models in "
    "Sources below."
)


@pytest.fixture
def clis(tmp_path, monkeypatch):
    """Claude Code, Codex CLI and OpenCode installed for the server: each prints a version.
    Taken before `server`, whose environment it is."""
    folder = tmp_path / "clis"
    folder.mkdir()
    for name in ("claude", "codex", "opencode"):
        script = folder / name
        script.write_text("#!/bin/sh\necho 1.0.0\n")
        script.chmod(script.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("PATH", f"{folder}{os.pathsep}{os.environ['PATH']}")


@pytest.fixture
def lms():
    """The fake LM Studio in this process: its list may change during a test."""
    server = fake.Server("lmstudio")
    yield server
    server.close()


def closed_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def section(page: Page):
    return page.get_by_role("region", name="Models")


def source(page: Page, name: str):
    """A source's row, by its toggle's name."""
    toggle = page.get_by_role("button", name=name, exact=True)  # within the row
    return section(page).locator("li.src").filter(has=toggle)


def your_models(page: Page):
    return section(page).locator("table.mm-models")


def open_settings(page: Page, server) -> None:
    log_in(page, server)
    page.goto(f"{server['url']}/settings#models")
    expect(section(page).get_by_role("heading", name="Your models")).to_be_visible()


def add_server(page: Page, name: str, address: str) -> None:
    models = section(page)
    models.get_by_role("button", name="+ Add server").click()
    models.get_by_label("Name").fill(name)
    models.get_by_label("Address").fill(address)
    models.get_by_role("button", name="Add", exact=True).click()


def test_first_open_and_ticking_claude_sonnet(page: Page, clis, server, lms, shot):
    page.set_viewport_size({"width": 1280, "height": 900})
    open_settings(page, server)
    models = section(page)
    expect(models.get_by_text(EMPTY)).to_be_visible()
    expect(models.get_by_role("heading", name="Sources")).to_be_visible()
    claude = source(page, "Claude Code")
    expect(claude.get_by_role("checkbox")).to_have_count(0)  # closed: nothing read
    expect(claude.get_by_text("CLI", exact=True)).to_be_visible()
    shot(page, "first-open")

    claude.get_by_role("button", name="Claude Code", exact=True).click()
    sonnet = claude.get_by_role("checkbox", name="sonnet on Claude Code", exact=True)
    sonnet.click()  # the tick follows the saved model, not the click: no check()
    row = your_models(page).get_by_role("row").filter(has_text="Claude Sonnet")
    expect(row).to_contain_text("sonnet")
    expect(sonnet).to_be_checked()
    assert [m.name for m in state.models()] == ["Claude Sonnet"]
    shot(page, "claude-sonnet")
    sonnet.click()
    expect(models.get_by_text(EMPTY)).to_be_visible()
    assert state.models() == []


def test_a_server_added_ticked_renamed_refreshed_and_removed(
    page: Page, clis, server, lms, shot, monkeypatch
):
    page.set_viewport_size({"width": 1280, "height": 900})
    open_settings(page, server)
    assert lms.requests == []  # opening the page asks no server
    add_server(page, "LM Studio дома", lms.url.removeprefix("http://"))
    lm = source(page, "LM Studio дома")
    expect(lm.get_by_text('✓ Saved model server "LM Studio дома".')).to_be_visible()
    emb = lm.locator("tr.src-emb")
    expect(emb).to_contain_text("(embeddings)")
    for box in emb.get_by_role("checkbox").all():
        expect(box).to_be_disabled()
    head = lm.locator("thead th")
    expect(head.first).to_have_text("Model")
    expect(lm.get_by_role("columnheader", name="OpenCode")).to_be_visible()
    shot(page, "server-added")

    lm.get_by_role("checkbox", name="qwen3-8b on OpenCode", exact=True).click()
    row = (
        your_models(page).get_by_role("row").filter(has_text="qwen3-8b · LM Studio дома · OpenCode")
    )
    expect(row).to_be_visible()
    row.get_by_role("button", name="Rename qwen3-8b · LM Studio дома · OpenCode").click()
    field = your_models(page).get_by_role("textbox")
    field.fill("Локальная Qwen")
    your_models(page).get_by_role("button", name="Save").click()
    expect(your_models(page).get_by_text("Локальная Qwen")).to_be_visible()
    assert [m.name for m in state.models()] == ["Локальная Qwen"]
    shot(page, "renamed")

    # The server's list changes: Refresh shows the new model unticked, the gone one first.
    listed = dict(fake.PROFILES["lmstudio"])
    listed[("GET", fake.MODELS)] = fake.openai_list("gemma-3-12b", fake.EMBEDDINGS)
    monkeypatch.setitem(fake.PROFILES, "lmstudio", listed)
    lm.get_by_role("button", name="↻ Refresh").click()
    expect(
        lm.get_by_role("checkbox", name="gemma-3-12b on OpenCode", exact=True)
    ).not_to_be_checked()
    first = lm.locator("tbody tr").first
    expect(first).to_contain_text("qwen3-8b")
    expect(first).to_contain_text("not in the server's list")
    expect(first.get_by_role("checkbox", name="qwen3-8b on OpenCode", exact=True)).to_be_checked()
    expect(your_models(page).get_by_text("not in LM Studio дома's list of models")).to_be_visible()
    shot(page, "refreshed")

    id = state.model_server("LM Studio дома").id
    lm.get_by_role("button", name="Remove", exact=True).click()
    expect(
        lm.get_by_text("Remove LM Studio дома and its 1 models: Локальная Qwen?")
    ).to_be_visible()
    shot(page, "remove-asks")
    lm.get_by_role("button", name="Remove server and models").click()
    expect(section(page).get_by_text(EMPTY)).to_be_visible()
    expect(section(page).get_by_role("button", name="LM Studio дома", exact=True)).to_have_count(0)
    assert state.model_servers() == [] and state.models() == []
    assert not model_settings.key_folder(id).exists()


def test_refusals_under_their_fields_a_silent_server_and_change(
    page: Page, clis, server, lms, shot
):
    page.set_viewport_size({"width": 1280, "height": 900})
    open_settings(page, server)
    port = closed_port()
    add_server(page, "lab", f"127.0.0.1:{port}")
    address = section(page).get_by_label("Address")
    note = section(page).get_by_text(re.compile(rf"http://127\.0\.0\.1:{port} does not answer"))
    expect(note).to_be_visible()
    field_box, note_box = address.bounding_box(), note.bounding_box()
    assert field_box and note_box and note_box["y"] >= field_box["y"] + field_box["height"]
    expect(section(page).get_by_label("Name")).to_have_value("lab")
    shot(page, "refused")
    section(page).get_by_role("button", name="Cancel").click()

    add_server(page, "LM Studio дома", lms.url)
    lm = source(page, "LM Studio дома")
    lm.get_by_role("checkbox", name="qwen3-8b on OpenCode", exact=True).click()
    expect(your_models(page)).to_contain_text("qwen3-8b · LM Studio дома · OpenCode")
    lm.get_by_role("button", name="LM Studio дома", exact=True).click()  # closed
    port = lms.port
    lms.close()
    lm.get_by_role("button", name="LM Studio дома", exact=True).click()
    expect(
        lm.get_by_text(
            re.compile(r"does not answer .*Its models stay: qwen3-8b · LM Studio дома · OpenCode\.")
        )
    ).to_be_visible()
    shot(page, "silent")
    assert [m.name for m in state.models()] == ["qwen3-8b · LM Studio дома · OpenCode"]

    moved = fake.Server("lmstudio")
    try:
        lm.get_by_role("button", name="Change").click()
        lm.get_by_label("Address").fill(moved.url)
        lm.get_by_role("button", name="Save").click()
        expect(
            lm.get_by_text('✓ Replaced model server "LM Studio дома".', exact=False)
        ).to_be_visible()
        assert state.model_server("LM Studio дома").address == moved.url
        assert (
            state.model("qwen3-8b · LM Studio дома · OpenCode").server
            == state.model_server("LM Studio дома").id
        )
        assert port != moved.port
    finally:
        moved.close()


def test_the_section_at_a_phones_width(browser: Browser, clis, server, lms, shot, monkeypatch):
    long = "qwen/qwen3-coder-30b-a3b-instruct"
    listed = dict(fake.PROFILES["lmstudio"])
    listed[("GET", fake.MODELS)] = fake.openai_list("qwen3-8b", long, fake.EMBEDDINGS)
    monkeypatch.setitem(fake.PROFILES, "lmstudio", listed)
    context = browser.new_context(
        viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True
    )
    try:
        page = context.new_page()
        open_settings(page, server)
        add_server(page, "LM Studio дома", lms.url)
        lm = source(page, "LM Studio дома")
        expect(lm.get_by_role("columnheader", name="Codex CLI")).to_be_visible()
        # A long model's name breaks at its / and -, never a letter or two to a line.
        cell = lm.locator("td.mono", has_text="coder")
        assert cell.bounding_box()["width"] >= 120
        lm.get_by_role("checkbox", name="qwen3-8b on OpenCode", exact=True).click()
        expect(your_models(page)).to_contain_text("qwen3-8b · LM Studio дома · OpenCode")
        assert page.evaluate("document.documentElement.scrollWidth") <= 390  # no sideways scroll
        section(page).scroll_into_view_if_needed()
        shot(page, "phone", full_page=False)
    finally:
        context.close()
