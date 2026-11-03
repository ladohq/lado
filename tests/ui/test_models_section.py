"""Settings → Models in a browser (openspec change model-settings-page): its tabs Your models
and Add models against a real `lado server`, the fake model server of tests/fake_model_server.py
in the test's process, and stand-ins of Claude Code, Codex CLI, OpenCode and Kilo CLI on the
server's PATH that print a version (Claude Code's aliases are its provider's own list; Kilo
CLI's `kilo models` prints 323 models). Nothing moves under the pointer: each action keeps
the top of what it acted on. On a computer and at a phone's width."""

import os
import re
import socket
import stat

import fake_model_server as fake
import pytest
from playwright.sync_api import Browser, Locator, Page, expect
from test_main_screen import log_in

from lado import model_settings, state

pytestmark = pytest.mark.ui

EMPTY = "No models yet. Without them each agent runs on its CLI's default model."
KILO_MODELS = 323


@pytest.fixture
def clis(tmp_path, monkeypatch):
    """Claude Code, Codex CLI, OpenCode and Kilo CLI installed for the server: each prints a
    version; `kilo models` prints KILO_MODELS models. Taken before `server`, whose
    environment it is."""
    folder = tmp_path / "clis"
    folder.mkdir()
    kilo = (
        f'if [ "$1" = models ]; then i=0; while [ $i -lt {KILO_MODELS} ]; do '
        'echo "vendor/model-$i"; i=$((i+1)); done; exit 0; fi\n'
    )
    for name in ("claude", "codex", "opencode", "kilo"):
        script = folder / name
        script.write_text("#!/bin/sh\n" + (kilo if name == "kilo" else "") + "echo 1.0.0\n")
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


def tab(page: Page, name: str):
    return section(page).get_by_role("tab", name=re.compile(rf"^{re.escape(name)}"))


def source(page: Page, name: str):
    """A source's row in Add models, by its toggle's name."""
    toggle = page.get_by_role("button", name=name, exact=True)  # within the row
    return section(page).locator("li.mx-src").filter(has=toggle)


def card(page: Page, title: str):
    return section(page).get_by_role("group", name=title, exact=True)


def top(locator: Locator) -> float:
    box = locator.bounding_box()
    assert box is not None
    return box["y"]


def open_settings(page: Page, server) -> None:
    log_in(page, server)
    page.goto(f"{server['url']}/settings#models")
    expect(tab(page, "Your models")).to_be_visible()
    # Agent CLIs and environment, above, grows once its check ends: measured after that.
    expect(page.locator(".pv-refresh.spinning")).to_have_count(0, timeout=30_000)
    expect(page.locator(".pv-list")).to_be_visible()


def start_form(page: Page, name: str, address: str) -> None:
    models = section(page)
    models.get_by_role("button", name="+ Add server").click()
    models.get_by_label("Name").fill(name)
    models.get_by_label("Address").fill(address)


def test_first_open_and_ticking_claude_sonnet(page: Page, clis, server, lms, shot):
    page.set_viewport_size({"width": 1280, "height": 900})
    open_settings(page, server)
    models = section(page)
    expect(models.get_by_text(EMPTY)).to_be_visible()
    shot(page, "first-open")
    models.get_by_role("button", name="Add models").click()  # the empty line's link
    claude = source(page, "Claude Code")
    expect(claude.get_by_role("checkbox")).to_have_count(0)  # closed: nothing read
    expect(claude.locator(".badge")).to_have_text("CLI")
    claude.get_by_text("Claude Code", exact=True).click()  # the row's name opens it
    sonnet = claude.get_by_role("checkbox", name="sonnet on Claude Code", exact=True)
    sonnet.scroll_into_view_if_needed()  # where the click would scroll it: measured there
    before = top(sonnet)
    sonnet.click()  # the tick follows the saved model, not the click: no check()
    expect(claude.get_by_text("as Claude Sonnet")).to_be_visible()
    expect(sonnet).to_be_checked()
    assert top(sonnet) == before  # nothing moved under the pointer
    expect(tab(page, "Your models")).to_have_text("Your models 1")
    assert [m.name for m in state.models()] == ["Claude Sonnet"]
    shot(page, "claude-sonnet")
    sonnet.click()
    expect(sonnet).not_to_be_checked()
    assert top(sonnet) == before
    assert state.models() == []
    # Undo, in Your models, brings the model back under its name; the tick follows.
    tab(page, "Your models").click()
    undo = card(page, "Claude Code").get_by_role("button", name="Undo")
    undo.click()
    expect(
        card(page, "Claude Code").get_by_role("button", name="Rename Claude Sonnet")
    ).to_be_visible()
    assert [m.name for m in state.models()] == ["Claude Sonnet"]
    tab(page, "Add models").click()
    expect(
        source(page, "Claude Code").get_by_role("checkbox", name="sonnet on Claude Code")
    ).to_be_checked()


def test_a_server_added_ticked_renamed_refreshed_and_removed(
    page: Page, clis, server, lms, shot, monkeypatch
):
    page.set_viewport_size({"width": 1280, "height": 900})
    open_settings(page, server)
    assert lms.requests == []  # opening the page asks no server
    tab(page, "Add models").click()
    start_form(page, "LM Studio дома", lms.url.removeprefix("http://"))
    models = section(page)
    expect(
        models.get_by_text(re.compile(r"✓ LM Studio · 1 model · .*can run them"))
    ).to_be_visible()
    shot(page, "form-checked")
    add = models.get_by_role("button", name="Add", exact=True)
    add.scroll_into_view_if_needed()
    at = top(models.locator("li.mx-src").filter(has=page.locator(".mx-form")))
    add.click()
    lm = source(page, "LM Studio дома")
    expect(lm.get_by_text('✓ Saved model server "LM Studio дома".')).to_be_visible()
    assert top(lm) == at  # the new server takes the form's place
    expect(lm.get_by_text("1 embeddings model hidden: agents cannot run on it.")).to_be_visible()
    expect(lm.get_by_text(fake.EMBEDDINGS)).to_have_count(0)
    shot(page, "server-added")

    row = lm.get_by_role("button", name="qwen3-8b", exact=True)
    row.click()
    clis_of = lm.get_by_role("group", name="Agent CLIs for qwen3-8b")
    opencode = clis_of.get_by_role("checkbox", name="qwen3-8b on OpenCode", exact=True)
    opencode.scroll_into_view_if_needed()
    before = top(opencode)
    opencode.click()
    expect(row).to_contain_text("in OpenCode")
    assert top(opencode) == before
    shot(page, "server-model-clis")
    clis_of.get_by_role("button", name="Done").click()

    tab(page, "Your models").click()
    name = "qwen3-8b · LM Studio дома · OpenCode"
    opencode_card = card(page, "OpenCode")
    opencode_card.get_by_role("button", name=f"Rename {name}").click()
    field = opencode_card.get_by_role("textbox", name=f"Name of {name}")
    field.fill("Другое")
    field.press("Escape")  # restores, saves nothing
    expect(opencode_card.get_by_role("button", name=f"Rename {name}")).to_be_visible()
    assert [m.name for m in state.models()] == [name]
    opencode_card.get_by_role("button", name=f"Rename {name}").click()
    field.fill("Локальная Qwen")
    field.press("Enter")
    expect(opencode_card.get_by_role("button", name="Rename Локальная Qwen")).to_be_visible()
    assert [m.name for m in state.models()] == ["Локальная Qwen"]
    shot(page, "renamed")

    # The server's list changes: ↻ shows the new model, the gone one first, marked.
    listed = dict(fake.PROFILES["lmstudio"])
    listed[("GET", fake.MODELS)] = fake.openai_list("gemma-3-12b", fake.EMBEDDINGS)
    monkeypatch.setitem(fake.PROFILES, "lmstudio", listed)
    tab(page, "Add models").click()
    lm.get_by_role("button", name="Refresh the list").click()
    expect(lm.get_by_role("button", name="gemma-3-12b", exact=True)).to_be_visible()
    first = lm.locator(".mx-list .mx-row").first
    expect(first).to_contain_text("qwen3-8b ⚠ no longer listed")
    expect(first).to_contain_text("in OpenCode")
    tab(page, "Your models").click()
    expect(card(page, "OpenCode").get_by_text("⚠ not in list")).to_be_visible()
    shot(page, "refreshed")

    id = state.model_server("LM Studio дома").id
    tab(page, "Add models").click()
    lm.get_by_role("button", name="Remove LM Studio дома").click()
    expect(
        lm.get_by_text(
            "Remove LM Studio дома and its 1 model: Локальная Qwen? Its key is deleted too; "
            "this cannot be undone."
        )
    ).to_be_visible()
    shot(page, "remove-asks")
    confirm = lm.get_by_role("button", name="Remove server and models")
    confirm.scroll_into_view_if_needed()
    at = top(lm)
    confirm.click()
    removed = "Removed LM Studio дома and its 1 model."
    expect(models.get_by_text(removed)).to_be_visible()
    line = models.locator("li.mx-src").filter(has=page.get_by_text(removed))
    assert top(line) == at  # its line in its place
    assert state.model_servers() == [] and state.models() == []
    assert not model_settings.key_folder(id).exists()
    tab(page, "Your models").click()
    expect(section(page).get_by_text(EMPTY)).to_be_visible()


def test_the_form_checks_before_add_and_a_silent_server(page: Page, clis, server, lms, shot):
    page.set_viewport_size({"width": 1280, "height": 900})
    open_settings(page, server)
    tab(page, "Add models").click()
    port = closed_port()
    start_form(page, "lab", f"127.0.0.1:{port}")
    models = section(page)
    address = models.get_by_label("Address")
    note = models.get_by_text(re.compile(rf"http://127\.0\.0\.1:{port} does not answer"))
    expect(note).to_be_visible()  # before any Add
    expect(models.get_by_role("button", name="Add", exact=True)).to_be_disabled()
    field_box, note_box = address.bounding_box(), note.bounding_box()
    assert field_box and note_box and note_box["y"] >= field_box["y"] + field_box["height"]
    assert state.model_servers() == []
    shot(page, "refused")
    address.fill(lms.url)
    expect(models.get_by_role("button", name="Add", exact=True)).to_be_enabled()
    models.get_by_role("button", name="Add", exact=True).click()
    lm = source(page, "lab")
    lm.get_by_role("button", name="qwen3-8b", exact=True).click()
    lm.get_by_role("checkbox", name="qwen3-8b on OpenCode", exact=True).click()
    expect(lm.get_by_role("button", name="qwen3-8b", exact=True)).to_contain_text("in OpenCode")
    lm.get_by_role("button", name="lab", exact=True).click()  # closed
    lms.close()
    lm.get_by_role("button", name="lab", exact=True).click()
    expect(
        lm.get_by_text(
            re.compile(r"does not answer .*Its models stay: qwen3-8b · lab · OpenCode\.")
        )
    ).to_be_visible()
    shot(page, "silent")
    assert [m.name for m in state.models()] == ["qwen3-8b · lab · OpenCode"]

    moved = fake.Server("lmstudio")
    try:
        lm.get_by_role("button", name="Change lab").click()
        lm.get_by_label("Address").fill(moved.url)
        lm.get_by_role("button", name="Save").click()
        expect(lm.get_by_text('✓ Saved model server "lab".')).to_be_visible()
        expect(lm.get_by_role("button", name="qwen3-8b", exact=True)).to_be_visible()  # opened
        assert state.model_server("lab").address == moved.url
        assert state.model("qwen3-8b · lab · OpenCode").server == state.model_server("lab").id
    finally:
        moved.close()


def test_a_long_list_is_bounded_and_searched(page: Page, clis, server, shot):
    page.set_viewport_size({"width": 1280, "height": 900})
    open_settings(page, server)
    tab(page, "Add models").click()
    height = page.evaluate("document.querySelector('#models').scrollHeight")
    kilo = source(page, "Kilo CLI")
    kilo.get_by_role("button", name="Kilo CLI", exact=True).click()
    expect(kilo.get_by_text(f"{KILO_MODELS} models", exact=True)).to_be_visible()
    listing = kilo.locator(".mx-list")
    box = listing.bounding_box()
    assert box and box["height"] <= 320  # about nine rows, scrolled within
    grown = page.evaluate("document.querySelector('#models').scrollHeight") - height
    assert grown < 400
    shot(page, "kilo")
    kilo.get_by_role("searchbox", name="Search the models").fill("model-32")
    expect(kilo.get_by_text(f"4 of {KILO_MODELS} models")).to_be_visible()  # 32, 320-322


def test_the_section_at_a_phones_width(browser: Browser, clis, server, lms, shot, monkeypatch):
    long = "qwen/qwen3-coder-30b-a3b-instruct"
    listed = dict(fake.PROFILES["lmstudio"])
    listed[("GET", fake.MODELS)] = fake.openai_list("qwen3-8b", long, fake.EMBEDDINGS)
    monkeypatch.setitem(fake.PROFILES, "lmstudio", listed)
    gateway = "https://litellm-gateway.platform.internal.example.com:4000/v1"
    state.add_model_server("g1", "LiteLLM", gateway, "LiteLLM", ["chat"])
    context = browser.new_context(
        viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True
    )
    try:
        page = context.new_page()
        open_settings(page, server)
        tab(page, "Add models").click()
        gw = source(page, "LiteLLM")
        toggle = gw.get_by_role("button", name="LiteLLM", exact=True)
        expect(toggle).to_have_attribute("title", gateway)
        expect(gw.get_by_role("button", name="Change LiteLLM")).to_be_visible()
        # The icons under the name, measured at one moment.
        assert gw.evaluate(
            "li => li.querySelector('.mx-acts').getBoundingClientRect().top >= "
            "li.querySelector('.mx-title').getBoundingClientRect().bottom"
        )
        start_form(page, "LM Studio дома", lms.url)
        section(page).get_by_role("button", name="Add", exact=True).click()
        lm = source(page, "LM Studio дома")
        lm.get_by_role("button", name=long, exact=True).click()
        lm.get_by_role("checkbox", name=f"{long} on OpenCode", exact=True).click()
        expect(lm.get_by_role("button", name=long, exact=True)).to_contain_text("in OpenCode")
        assert page.evaluate("document.documentElement.scrollWidth") <= 390  # no sideways scroll
        shot(page, "phone", full_page=False)
        tab(page, "Your models").click()
        expect(card(page, "OpenCode")).to_contain_text(long)
        assert page.evaluate("document.documentElement.scrollWidth") <= 390
        shot(page, "phone-your-models", full_page=False)
    finally:
        context.close()
