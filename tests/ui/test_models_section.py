"""Settings → Models in a browser (openspec change model-settings-page): its two blocks, Your
agent CLIs and Model servers, against a real `lado server`, the fake model server of
tests/fake_model_server.py in the test's process, and stand-ins of Claude Code, Codex CLI,
OpenCode and Kilo CLI on the server's PATH that print a version (Claude Code's aliases are its
provider's own list; Kilo CLI's `kilo models` prints 323 models). Nothing moves under the
pointer: each action keeps the top of what it acted on, or of what holds the focus, to the
pixel, whatever it changes above. On a computer and at a phone's width."""

import os
import re
import socket
import stat

import fake_model_server as fake
import pytest
from playwright.sync_api import Browser, Locator, Page, Route, expect
from test_main_screen import log_in
from test_projects_section import masked

from lado import model_settings, state

pytestmark = pytest.mark.ui

LEAD_NO_MODELS = (
    "New sessions and workers of each agent CLI start on its default model. To add models of "
    "your own, add a model server below and tick the agent CLIs that run them."
)
KILO_MODELS = 323
CHAT = "chat completions"
UNDO_S = 10


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


def source(page: Page, name: str):
    """A source's row, by its toggle's name."""
    toggle = page.get_by_role("button", name=name, exact=True)  # within the row
    return section(page).locator("li.mx-src").filter(has=toggle)


def toggle(page: Page, name: str):
    return source(page, name).get_by_role("button", name=name, exact=True)


def card(page: Page, title: str):
    return section(page).get_by_role("group", name=title, exact=True)


def picker(page: Page, title: str):
    return section(page).get_by_role("combobox", name=f"Default model of {title}", exact=True)


def saved_server(lms, id="s1", name="LM Studio дома") -> str:
    state.add_model_server(id, name, lms.url, "LM Studio", [CHAT])
    return id


def top(locator: Locator) -> float:
    box = locator.bounding_box()
    assert box is not None
    return box["y"]


def stays(locator: Locator, before: float) -> None:
    """The locator's top is where it was, to the pixel: the page scrolls by whole pixels, so
    an anchor set back after a change of x.5 px is off by that half pixel at most."""
    assert abs(top(locator) - before) < 1, (top(locator), before)


def open_settings(page: Page, server) -> None:
    log_in(page, server)
    page.goto(f"{server['url']}/settings#models")
    expect(section(page).get_by_role("heading", name="Your agent CLIs")).to_be_visible()
    # Agent CLIs and environment, above, grows once its check ends: measured after that.
    expect(page.locator(".pv-refresh.spinning")).to_have_count(0, timeout=30_000)
    expect(page.locator(".pv-list")).to_be_visible()


def start_form(page: Page, name: str, address: str) -> None:
    models = section(page)
    models.get_by_role("button", name="Add server", exact=True).click()
    models.get_by_label("Name").fill(name)
    models.get_by_label("Address").fill(address)


def add_server(page: Page, name: str, address: str) -> Locator:
    start_form(page, name, address)
    add = section(page).get_by_role("button", name="Add server", exact=True)
    expect(add).to_be_enabled()
    add.click()
    lm = source(page, name)
    expect(lm.get_by_text(f'Saved model server "{name}".')).to_be_visible()
    return lm


def test_first_open_a_card_per_cli_and_nothing_asked(page: Page, clis, server, lms, shot):
    saved_server(lms)
    page.set_viewport_size({"width": 1280, "height": 900})
    open_settings(page, server)
    models = section(page)
    expect(models.get_by_role("tablist")).to_have_count(0)
    expect(models.get_by_role("heading", level=3)).to_have_text(
        ["Your agent CLIs", "Model servers 1"]
    )
    expect(models.get_by_text(LEAD_NO_MODELS)).to_be_visible()
    for title in ("Claude Code", "Codex CLI", "Kilo CLI", "OpenCode"):
        expect(card(page, title)).to_be_visible()
    expect(picker(page, "Claude Code")).to_have_text(re.compile("Claude Code's settings"))
    expect(models.locator(".mx-hit[aria-expanded=true]")).to_have_count(0)  # all closed
    assert lms.requests == []
    shot(page, "first-open")


def test_a_built_in_default_from_a_long_list_searched_and_cleared(page: Page, clis, server, shot):
    page.set_viewport_size({"width": 1280, "height": 900})
    open_settings(page, server)
    field = picker(page, "Kilo CLI")
    field.scroll_into_view_if_needed()
    before = top(field)
    field.click()
    search = section(page).get_by_placeholder(f"Search {KILO_MODELS} models")
    expect(search).to_be_focused()
    expect(section(page).get_by_role("option")).to_have_count(KILO_MODELS + 1)
    shot(page, "kilo-picker")
    search.fill("model-32")
    expect(section(page).get_by_role("option")).to_have_count(4)  # 32, 320-322
    expect(section(page).get_by_text(f"4 of {KILO_MODELS}")).to_be_visible()
    search.press("ArrowDown")
    search.press("Enter")
    expect(field).to_have_text(re.compile("vendor/model-320"))
    expect(field).to_be_focused()
    stays(field, before)  # nothing moved under the pointer
    assert state.cli_defaults() == [state.ModelRef("kilo", None, "vendor/model-320")]
    shot(page, "kilo-default")
    field.click()
    section(page).get_by_role("option", name="Kilo CLI's settings").click()
    expect(field).to_have_text(re.compile("Kilo CLI's settings"))
    assert state.cli_defaults() == []


def test_a_list_lost_default_shows_on_the_card_after_opening(page: Page, clis, server, shot):
    state.set_cli_default(state.ModelRef("kilo", None, "old/gone"))
    page.set_viewport_size({"width": 1280, "height": 900})
    open_settings(page, server)
    kilo = card(page, "Kilo CLI")
    expect(
        kilo.get_by_text(
            "⚠ Kilo CLI no longer lists old/gone: agents on it stop at their first turn."
        )
    ).to_be_visible()
    expect(picker(page, "Kilo CLI")).to_contain_text("⚠ no longer listed")
    assert state.cli_defaults() == [state.ModelRef("kilo", None, "old/gone")]
    shot(page, "lost-default")
    kilo.get_by_role("button", name="Use Kilo CLI's settings").click()
    expect(picker(page, "Kilo CLI")).to_be_focused()
    assert state.cli_defaults() == []


def test_other_name_on_claude_code_warns_and_stays(page: Page, clis, server, shot):
    page.set_viewport_size({"width": 1280, "height": 900})
    open_settings(page, server)
    claude = card(page, "Claude Code")
    picker(page, "Claude Code").click()
    expect(section(page).get_by_text("BUILT-IN · aliases")).to_be_visible()
    shot(page, "claude-picker")
    # The active row stays clear of the row pinned at the bottom, whichever way it moves.
    field = picker(page, "Claude Code")
    page.keyboard.press("End")
    pinned = section(page).locator(".mp-other").bounding_box()
    for _ in range(3):
        page.keyboard.press("ArrowUp")
        active = section(page).locator(".mp-active").bounding_box()
        assert pinned and active and active["y"] + active["height"] <= pinned["y"] + 1, (
            active,
            pinned,
        )
    expect(field).to_be_focused()
    section(page).get_by_role("option", name=re.compile("Other name…")).click()
    name = claude.get_by_role("textbox", name="Other name")
    expect(name).to_be_focused()
    name.fill("claude-opus-4-1-20250805")
    warned = claude.get_by_text(re.compile("LADO cannot check claude-opus-4-1-20250805"))
    expect(warned).to_be_visible()
    claude.get_by_role("button", name="Use", exact=True).click()
    expect(name).to_have_count(0)
    expect(picker(page, "Claude Code")).to_have_text(re.compile("claude-opus-4-1-20250805"))
    expect(warned).to_be_visible()  # it stays, with the value
    shot(page, "claude-other-name")
    assert state.cli_defaults() == [state.ModelRef("claude", None, "claude-opus-4-1-20250805")]


def test_an_external_default_removed_with_a_question_and_undo(page: Page, clis, server, lms, shot):
    saved_server(lms)
    state.add_model("Локальная Qwen", "opencode", "qwen3-8b", "s1")
    state.add_model("Рабочая Qwen", "opencode", "qwen3-8b", "s1")
    page.set_viewport_size({"width": 1280, "height": 900})
    open_settings(page, server)
    field = picker(page, "OpenCode")
    field.click()
    section(page).get_by_role("option", name=re.compile("Локальная Qwen")).click()
    expect(field).to_contain_text("Локальная Qwen")
    expect(field.locator(".srv")).to_have_text("LM Studio дома")
    saved = state.model("Локальная Qwen")
    assert state.cli_defaults() == [state.ModelRef("opencode", saved.id, None)]
    opencode = card(page, "OpenCode")
    opencode.get_by_role("button", name="Remove Локальная Qwen").click()
    ask = opencode.get_by_role("alertdialog")
    expect(ask).to_contain_text(
        "It is OpenCode's default model: OpenCode goes back to its settings."
    )
    expect(ask.get_by_role("button", name="Cancel")).to_be_focused()
    shot(page, "default-asks")
    ask.press("Escape")
    expect(ask).to_have_count(0)
    assert state.model("Локальная Qwen") is not None
    opencode.get_by_role("button", name="Remove Локальная Qwen").click()
    opencode.get_by_role("button", name="Remove model").click()
    undo = opencode.get_by_role("button", name="Undo")
    expect(undo).to_be_focused()
    expect(opencode.get_by_text("OpenCode is back on its settings.")).to_be_visible()
    expect(field).to_have_text(re.compile("OpenCode's settings"))
    assert state.cli_defaults() == []
    shot(page, "default-removed")
    undo.click()
    expect(opencode.get_by_role("button", name="Rename Локальная Qwen")).to_be_focused()
    expect(field).to_contain_text("Локальная Qwen")
    back = state.model("Локальная Qwen")
    assert state.cli_defaults() == [state.ModelRef("opencode", back.id, None)]


def test_a_request_lado_s_server_did_not_answer_promises_nothing(
    page: Page, clis, server, lms, shot
):
    saved_server(lms)
    state.add_model("Локальная Qwen", "opencode", "qwen3-8b", "s1")
    page.set_viewport_size({"width": 1280, "height": 900})
    open_settings(page, server)
    opencode = card(page, "OpenCode")
    x = opencode.get_by_role("button", name="Remove Локальная Qwen")
    expect(x).to_be_visible()
    page.route("**/api/**", lambda route: route.abort())
    x.click()
    expect(
        opencode.get_by_text(
            "LADO's server does not answer: your request may or may not have reached it."
        )
    ).to_be_visible()
    shot(page)
    page.unroute("**/api/**")


def test_a_silent_server_shows_when_the_picker_opens(page: Page, clis, server, lms, shot):
    saved_server(lms)
    saved = state.add_model("Локальная Qwen", "opencode", "qwen3-8b", "s1")
    state.set_cli_default(state.ModelRef("opencode", saved.id, None))
    lms.close()
    page.set_viewport_size({"width": 1280, "height": 900})
    open_settings(page, server)
    opencode = card(page, "OpenCode")
    expect(opencode.get_by_text("does not answer")).to_have_count(0)  # the page asks no server
    picker(page, "OpenCode").click()
    expect(opencode.get_by_text(re.compile("^⚠ LM Studio дома does not answer"))).to_be_visible()
    expect(section(page).get_by_role("option", name=re.compile("Локальная Qwen"))).to_contain_text(
        "not answering"
    )
    shot(page, "silent-default")
    page.keyboard.press("Escape")
    expect(opencode.get_by_role("button", name="Check again")).to_be_visible()
    assert state.cli_defaults() == [state.ModelRef("opencode", saved.id, None)]


def test_the_picker_of_the_last_card_lies_over_the_page_in_view(page: Page, clis, server, shot):
    page.set_viewport_size({"width": 1280, "height": 600})
    open_settings(page, server)
    field = picker(page, "Kilo CLI")
    field.evaluate(
        "f => { const c = document.querySelector('.content');"
        " c.scrollTop += f.getBoundingClientRect().bottom - c.getBoundingClientRect().bottom + 8; }"
    )
    height = page.evaluate("document.querySelector('.content').scrollHeight")
    field.click()
    pop = section(page).locator(".mp-pop")
    expect(pop).to_be_visible()
    box, at = pop.bounding_box(), field.bounding_box()
    assert box and at
    assert box["y"] >= 0 and box["y"] + box["height"] <= 600, box  # whole in the window
    assert box["y"] + box["height"] <= at["y"], (box, at)  # opened upward
    assert page.evaluate("document.querySelector('.content').scrollHeight") == height
    shot(page, "picker-upward", full_page=False)
    page.mouse.move(640, 595)
    page.mouse.wheel(0, 40)  # outside the list: the human's scroll closes it
    expect(pop).to_have_count(0)


def test_a_tick_in_the_middle_of_a_long_list_moves_nothing(
    page: Page, clis, server, lms, shot, monkeypatch
):
    many = [f"vendor/model-{i}" for i in range(KILO_MODELS)]
    listed = dict(fake.PROFILES["lmstudio"])
    listed[("GET", fake.MODELS)] = fake.openai_list(*many)
    monkeypatch.setitem(fake.PROFILES, "lmstudio", listed)
    saved_server(lms)
    page.set_viewport_size({"width": 1280, "height": 900})
    open_settings(page, server)
    lm = source(page, "LM Studio дома")
    toggle(page, "LM Studio дома").click()
    expect(lm.get_by_text(f"{KILO_MODELS} models", exact=True)).to_be_visible()
    listing = lm.locator(".mx-list")
    box = listing.bounding_box()
    assert box and box["height"] <= 9 * 36 + 2  # nine rows, scrolled within
    listing.evaluate("list => { list.scrollTop = list.scrollHeight / 2; }")
    lm.get_by_role("button", name="vendor/model-160", exact=True).click()
    middle = lm.get_by_role("checkbox", name="vendor/model-160 on Kilo CLI", exact=True)
    middle.scroll_into_view_if_needed()
    before = top(middle)
    middle.click()
    expect(card(page, "Kilo CLI").get_by_role("table")).to_be_visible()  # its table added above
    expect(middle).to_be_checked()
    stays(middle, before)
    shot(page, "server-long-list")
    lm.get_by_role("searchbox", name=f"Search {KILO_MODELS} models").fill("model-32")
    expect(lm.get_by_text(f"4 of {KILO_MODELS} models")).to_be_visible()  # 32, 320-322


def test_x_undo_and_undo_running_out_move_nothing(page: Page, clis, server, lms, shot):
    saved_server(lms)
    state.add_model("Claude Sonnet", "opencode", "qwen3-8b", "s1")
    state.add_model("gpt-5-codex", "opencode", "qwen3-8b", "s1")
    page.set_viewport_size({"width": 1280, "height": 900})
    open_settings(page, server)
    opencode = card(page, "OpenCode")
    x = opencode.get_by_role("button", name="Remove Claude Sonnet")
    x.scroll_into_view_if_needed()
    row = opencode.get_by_role("row").nth(1)
    at = top(row)
    x.click()
    undo = opencode.get_by_role("button", name="Undo")
    expect(undo).to_be_focused()
    stays(row, at)  # the row keeps its place and height
    expect(row).to_have_text("Removed Claude Sonnet.Undo")
    shot(page, "your-models-undo")
    undo.click()
    name = opencode.get_by_role("button", name="Rename Claude Sonnet")
    expect(name).to_be_focused()
    stays(row, at)
    assert sorted(m.name for m in state.models()) == ["Claude Sonnet", "gpt-5-codex"]

    # × again, then the human works below while its Undo runs out.
    opencode.get_by_role("button", name="Remove Claude Sonnet").click()
    expect(undo).to_be_visible()
    toggle(page, "LM Studio дома").click()
    lm = source(page, "LM Studio дома")
    lm.get_by_role("button", name="qwen3-8b", exact=True).click()
    kilo = lm.get_by_role("checkbox", name="qwen3-8b on Kilo CLI", exact=True)
    expect(lm.get_by_text("would be qwen3-8b · LM Studio дома · Kilo CLI")).to_be_visible()
    kilo.focus()
    page.wait_for_timeout(300)  # the names the core gave have settled
    below = top(kilo)
    page.wait_for_timeout(UNDO_S * 1000 + 500)
    expect(undo).to_have_count(0)
    expect(row).to_have_text("Removed Claude Sonnet.")  # the line stays
    stays(kilo, below)
    kilo.click()  # the next change: the line goes
    expect(opencode.get_by_text("Removed Claude Sonnet.")).to_have_count(0)
    stays(kilo, below)


def test_a_server_added_ticked_renamed_unticked_refreshed_and_removed(
    page: Page, clis, server, lms, shot, monkeypatch
):
    page.set_viewport_size({"width": 1280, "height": 900})
    open_settings(page, server)
    assert lms.requests == []  # opening the page asks no server
    start_form(page, "LM Studio дома", lms.url.removeprefix("http://"))
    models = section(page)
    found = models.locator(".mx-found")
    expect(found).to_contain_text(f"✓ LM Studio answers at {lms.url}")
    expect(found).to_contain_text("1 embeddings model hidden: agents cannot run on it.")
    expect(found).to_contain_text("Agent CLIsKilo CLI, OpenCode")
    expect(models.locator("label", has_text="Key")).to_contain_text("optional")
    shot(page, "form-checked")
    add = models.get_by_role("button", name="Add server", exact=True)
    # Room under the page: with the form at its very end, the page getting shorter moves it
    # whatever the section does, as the window has nothing left to scroll.
    page.add_style_tag(content=".setting.mx { margin-bottom: 600px; }")
    add.scroll_into_view_if_needed()
    at = top(models.locator(".mx-form"))
    add.click()
    lm = source(page, "LM Studio дома")
    expect(lm.get_by_text('Saved model server "LM Studio дома".')).to_be_visible()
    expect(lm.get_by_text("Open a model to tick the agent CLIs that run it.")).to_be_visible()
    stays(lm, at)  # the new server takes the form's place
    expect(toggle(page, "LM Studio дома")).to_be_focused()
    expect(lm.get_by_text(fake.EMBEDDINGS)).to_have_count(0)
    shot(page, "server-added")

    row = lm.get_by_role("button", name="qwen3-8b", exact=True)
    row.click()
    clis_of = lm.get_by_role("group", name="Agent CLIs for qwen3-8b")
    expect(clis_of.get_by_text("would be qwen3-8b · LM Studio дома · Kilo CLI")).to_be_visible()
    opencode = clis_of.get_by_role("checkbox", name="qwen3-8b on OpenCode", exact=True)
    opencode.scroll_into_view_if_needed()
    before = top(opencode)
    opencode.click()
    expect(row).to_contain_text("in OpenCode")
    expect(card(page, "OpenCode").get_by_role("table")).to_be_visible()  # its table above
    stays(opencode, before)
    shot(page, "server-model-clis")

    name = "qwen3-8b · LM Studio дома · OpenCode"
    opencode_card = card(page, "OpenCode")
    opencode_card.get_by_role("button", name=f"Rename {name}").click()
    field = opencode_card.get_by_role("textbox", name=f"Name of {name}")
    field.fill("Другое")
    field.press("Escape")  # restores, saves nothing, the focus back on the name
    expect(opencode_card.get_by_role("button", name=f"Rename {name}")).to_be_focused()
    assert [m.name for m in state.models()] == [name]
    opencode_card.get_by_role("button", name=f"Rename {name}").click()
    field.fill("Локальная Qwen")
    field.press("Enter")
    expect(opencode_card.get_by_role("button", name="Rename Локальная Qwen")).to_be_visible()
    assert [m.name for m in state.models()] == ["Локальная Qwen"]
    shot(page, "renamed")

    # A mis-click: unticked and ticked again, the model keeps its name.
    opencode.scroll_into_view_if_needed()
    before = top(opencode)
    opencode.click()
    expect(clis_of.get_by_text("would be Локальная Qwen")).to_be_visible()
    stays(opencode, before)
    assert state.models() == []
    opencode.click()
    expect(clis_of.get_by_text("as Локальная Qwen")).to_be_visible()
    assert [m.name for m in state.models()] == ["Локальная Qwen"]
    stays(opencode, before)

    # The server's list changes: ↻ shows the new model, the gone one first, marked.
    listed = dict(fake.PROFILES["lmstudio"])
    listed[("GET", fake.MODELS)] = fake.openai_list("gemma-3-12b", fake.EMBEDDINGS)
    monkeypatch.setitem(fake.PROFILES, "lmstudio", listed)
    lm.get_by_role("button", name="Read the models again").click()
    expect(lm.get_by_role("button", name="gemma-3-12b", exact=True)).to_be_visible()
    first = lm.locator(".mx-list .mx-row").first
    expect(first).to_contain_text("no longer listed")
    expect(first).to_contain_text("in OpenCode")
    expect(card(page, "OpenCode").get_by_text("⚠ not in list")).to_be_visible()
    shot(page, "refreshed")

    id = state.model_server("LM Studio дома").id
    lm.get_by_role("button", name="Remove LM Studio дома").click()
    ask = lm.get_by_role("alertdialog")
    expect(ask).to_have_text(
        re.compile(
            r"^Remove LM Studio дома and its 1 model: Локальная Qwen\? This cannot be undone\."
        )
    )
    expect(ask.get_by_role("button", name="Cancel")).to_be_focused()
    shot(page, "remove-asks")
    confirm = lm.get_by_role("button", name="Remove server and 1 model")
    confirm.scroll_into_view_if_needed()
    at = top(lm)
    confirm.click()
    removed = "Removed LM Studio дома and its 1 model."
    expect(models.get_by_text(removed)).to_be_visible()
    expect(card(page, "OpenCode").get_by_role("table")).to_have_count(0)  # its table above went
    line = models.locator("li.mx-src").filter(has=page.get_by_text(removed))
    stays(line, at)  # its line in its place
    assert state.model_servers() == [] and state.models() == []
    assert not model_settings.key_folder(id).exists()
    expect(models.get_by_text(LEAD_NO_MODELS)).to_be_visible()


def test_the_form_checks_before_add_a_silent_server_and_change(page: Page, clis, server, lms, shot):
    page.set_viewport_size({"width": 1280, "height": 900})
    open_settings(page, server)
    port = closed_port()
    start_form(page, "lab", f"127.0.0.1:{port}")
    models = section(page)
    address = models.get_by_label("Address")
    note = models.get_by_text(re.compile(rf"http://127\.0\.0\.1:{port} does not answer"))
    expect(note).to_be_visible()  # before any Add
    expect(models.get_by_role("button", name="Add server", exact=True)).to_be_disabled()
    field_box, note_box = address.bounding_box(), note.bounding_box()
    assert field_box and note_box and note_box["y"] >= field_box["y"] + field_box["height"]
    assert state.model_servers() == []
    shot(page, "refused")
    address.fill(lms.url)
    add = models.get_by_role("button", name="Add server", exact=True)
    expect(add).to_be_enabled()
    add.click()
    lm = source(page, "lab")
    lm.get_by_role("button", name="qwen3-8b", exact=True).click()
    lm.get_by_role("checkbox", name="qwen3-8b on OpenCode", exact=True).click()
    expect(lm.get_by_role("button", name="qwen3-8b", exact=True)).to_contain_text("in OpenCode")
    toggle(page, "lab").click()  # closed
    lms.close()
    toggle(page, "lab").click()
    expect(lm.get_by_role("alert")).to_contain_text("does not answer")
    expect(
        lm.get_by_text(re.compile(r"^Its model stays saved: qwen3-8b · lab · OpenCode\."))
    ).to_be_visible()
    shot(page, "silent")
    assert [m.name for m in state.models()] == ["qwen3-8b · lab · OpenCode"]

    moved = fake.Server("lmstudio")
    try:
        lm.get_by_role("button", name="Change lab").click()
        expect(lm.get_by_text("Its 1 model keeps its name and moves with it.")).to_be_visible()
        lm.get_by_label("Address").fill(moved.url)
        expect(lm.get_by_text("✓ LM Studio answers · 1 model")).to_be_visible()  # before Save
        shot(page, "change")
        lm.get_by_role("button", name="Save").click()
        expect(lm.get_by_text('Saved model server "lab".')).to_be_visible()
        expect(lm.get_by_role("button", name="qwen3-8b", exact=True)).to_be_visible()  # opened
        assert state.model_server("lab").address == moved.url
        assert state.model("qwen3-8b · lab · OpenCode").server == state.model_server("lab").id
    finally:
        moved.close()


def test_the_form_names_the_cli_a_server_s_type_does_not_suit(page: Page, clis, server, lms, shot):
    open_settings(page, server)
    start_form(page, "LM Studio дома", lms.url)
    found = section(page).locator(".mx-found")
    expect(found).to_contain_text("LM Studio answers at")
    expect(found.locator("dd").nth(1)).to_contain_text("Kilo CLI, OpenCode")
    expect(found.locator("dd").nth(1)).not_to_contain_text("Codex CLI")
    expect(found.locator(".field-note.warn")).to_have_text(
        "⚠ Codex CLI: its Responses API loses Codex CLI's MCP tools, so the agent could not talk "
        "to LADO"
    )
    shot(page, "note")


def test_key_and_new_key_are_dots_as_a_projects_secret(page: Page, clis, server, lms):
    """Key and New key: text fields drawn in the font of dots, as a project's secret."""
    model_settings.add_server("lab", lms.url, None, warn=lambda _: None, note=lambda _: None)
    page.set_viewport_size({"width": 1280, "height": 900})
    open_settings(page, server)
    start_form(page, "gw", "127.0.0.1:1")
    key = section(page).get_by_label("Key", exact=True)
    key.fill("sk_live Пароль")
    masked(page, key)
    source(page, "lab").get_by_role("button", name="Change lab").click()
    new_key = source(page, "lab").get_by_label("New key", exact=True)
    new_key.fill("sk_live Пароль")
    masked(page, new_key)


def test_change_of_a_server_with_a_kept_key_says_what_answers(page: Page, clis, server):
    """A server saved with its key moves to another port: Change's check sends the kept key,
    as Save does, and says what answers there before Save."""
    old, moved = fake.Server("lmstudio", key="k-1"), fake.Server("lmstudio", key="k-1")
    try:
        model_settings.add_server("lab", old.url, "k-1", warn=lambda _: None, note=lambda _: None)
        page.set_viewport_size({"width": 1280, "height": 900})
        open_settings(page, server)
        lab = source(page, "lab")
        lab.get_by_role("button", name="Change lab").click()
        lab.get_by_label("Address").fill(moved.url)
        expect(lab.get_by_text("✓ LM Studio answers · 1 model")).to_be_visible()  # before Save
        assert {r.headers.get("Authorization") for r in moved.requests} == {"Bearer k-1"}
        lab.get_by_role("button", name="Save").click()
        expect(lab.get_by_text('Saved model server "lab".')).to_be_visible()
        assert model_settings.server_key(state.model_server("lab")) == "k-1"
    finally:
        old.close()
        moved.close()


def test_change_keeps_a_refused_new_key_in_its_field_and_save_off_until_it_is_edited(
    page: Page, clis, server
):
    """A saved server with its key: Change with a wrong New key, Save is refused for the key;
    the key stays in New key with the refusal under it and Save off, so a second Save cannot
    save the server with its old key; erased, Save saves with the kept key. No answer of
    LADO's carries the typed key: it stays in the browser's field."""
    lab_server = fake.Server("lmstudio", key="k-1")
    bodies: list[str] = []
    page.on("response", lambda r: "/api/" in r.url and bodies.append(r.text()))
    try:
        model_settings.add_server(
            "lab", lab_server.url, "k-1", warn=lambda _: None, note=lambda _: None
        )
        page.set_viewport_size({"width": 1280, "height": 900})
        open_settings(page, server)
        lab = source(page, "lab")
        lab.get_by_role("button", name="Change lab").click()
        new_key = lab.get_by_label("New key")
        new_key.fill("sk-wrong-key-000")
        save = lab.get_by_role("button", name="Save")
        save.click()
        refusal = (
            lab.locator(".field")
            .filter(has=page.get_by_label("New key"))
            .get_by_text("refused the key (401)")
        )
        expect(refusal).to_be_visible()
        expect(new_key).to_have_value("sk-wrong-key-000")
        expect(save).to_be_disabled()
        new_key.press("Enter")
        expect(lab.get_by_text('Saved model server "lab".')).to_have_count(0)
        new_key.fill("sk-wrong-key-001")
        expect(refusal).to_have_count(0)
        expect(save).to_be_enabled()
        new_key.fill("")
        expect(save).to_be_enabled()
        save.click()
        expect(lab.get_by_text('Saved model server "lab".')).to_be_visible()
        assert model_settings.server_key(state.model_server("lab")) == "k-1"
        assert not [b for b in bodies if "sk-wrong" in b]
    finally:
        lab_server.close()


def test_the_page_never_scrolls_by_itself(page: Page, clis, server, lms):
    """Opened at /settings, no #models, nothing pressed: the sections above grow as their
    rows come and Models renders as its rows come, and the page stays at its top."""
    saved_server(lms)
    state.add_model("Claude Sonnet", "opencode", "qwen3-8b", "s1")
    page.set_viewport_size({"width": 1280, "height": 900})
    log_in(page, server)
    page.goto(f"{server['url']}/settings")
    expect(section(page).get_by_role("heading", name="Your agent CLIs")).to_be_visible()
    seen = []
    for _ in range(16):
        seen.append(page.evaluate("document.querySelector('.content').scrollTop"))
        page.wait_for_timeout(250)
    expect(page.locator(".pv-refresh.spinning")).to_have_count(0, timeout=30_000)
    seen.append(page.evaluate("document.querySelector('.content').scrollTop"))
    assert set(seen) == {0}, seen


def models_top(page: Page) -> float:
    """The top of Models less the top of the area that scrolls."""
    return page.evaluate(
        "() => document.querySelector('.setting.mx').getBoundingClientRect().top"
        " - document.querySelector('.content').getBoundingClientRect().top"
    )


def test_opened_at_models_the_section_stays_at_the_top_while_the_sections_above_grow(
    page: Page, clis, server, lms
):
    """Opened at /settings#models, nothing pressed: Agent CLIs and environment, above, grows
    once its check ends, and Models stays at the top; a section above growing after the
    human's own scroll no longer moves the page."""
    saved_server(lms)
    state.add_model("Claude Sonnet", "opencode", "qwen3-8b", "s1")
    page.set_viewport_size({"width": 1280, "height": 900})
    log_in(page, server)
    page.goto(f"{server['url']}/settings#models")
    expect(section(page).get_by_role("heading", name="Your agent CLIs")).to_be_visible()
    page.wait_for_function(
        "() => Math.abs(document.querySelector('.setting.mx').getBoundingClientRect().top"
        " - document.querySelector('.content').getBoundingClientRect().top) < 1"
    )  # scrolled to it once its entries came
    seen = []
    for _ in range(16):
        seen.append(models_top(page))
        page.wait_for_timeout(200)
    expect(page.locator(".pv-refresh.spinning")).to_have_count(0, timeout=30_000)
    page.wait_for_timeout(300)
    seen.append(models_top(page))
    assert all(abs(at) < 1 for at in seen), seen
    grow = (
        "() => { const d = document.createElement('div'); d.style.height = '300px';"
        " document.querySelector('.pv-list').prepend(d); }"
    )
    page.evaluate(grow)
    page.wait_for_timeout(300)
    assert abs(models_top(page)) < 1, models_top(page)
    page.add_style_tag(content=".content { overflow-anchor: none; }")  # as Safari, which has none
    page.mouse.move(640, 450)
    page.mouse.wheel(0, 100)  # the human scrolls: the page is theirs
    page.wait_for_timeout(300)
    before = page.evaluate("document.querySelector('.content').scrollTop")
    page.evaluate(grow)
    page.wait_for_timeout(300)
    assert page.evaluate("document.querySelector('.content').scrollTop") == before


def test_a_section_above_growing_is_no_change_to_undo(page: Page, clis, server, lms):
    """The human acted in Models (opened a server, its list still reading); then a section
    above grows by 300 px, the page not following it (Safari has no scroll anchoring): the
    list's read ending scrolls nothing to make up for it."""
    saved_server(lms)
    held: list[Route] = []
    page.route(re.compile(r".*/api/model-servers/.*/probe$"), lambda route: held.append(route))
    page.set_viewport_size({"width": 1280, "height": 900})
    open_settings(page, server)
    page.add_style_tag(content=".content { overflow-anchor: none; }")  # as Safari, which has none
    toggle(page, "LM Studio дома").click()
    expect(source(page, "LM Studio дома").get_by_text("reading the models…")).to_be_visible()
    page.evaluate(
        "() => { const d = document.createElement('div'); d.style.height = '300px';"
        " document.querySelector('.pv-list').prepend(d); }"
    )
    before = page.evaluate("document.querySelector('.content').scrollTop")
    assert len(held) == 1
    held[0].continue_()
    expect(source(page, "LM Studio дома").get_by_role("button", name="qwen3-8b")).to_be_visible()
    page.wait_for_timeout(300)
    assert page.evaluate("document.querySelector('.content').scrollTop") == before


def test_the_focus_out_of_view_holds_nothing(page: Page, clis, server, lms):
    """The focus on Add server, the human scrolled up so that the last card shows and Add
    server is below the view: 300 px growing between them moves nothing that shows."""
    saved_server(lms)
    page.set_viewport_size({"width": 1280, "height": 500})
    open_settings(page, server)
    add = section(page).get_by_role("button", name="Add server", exact=True)
    add.focus()
    page.mouse.move(640, 250)
    page.mouse.wheel(0, -1)  # the human's: #models no longer kept at the top
    page.evaluate(
        "(at) => { const c = document.querySelector('.content');"
        " c.scrollTop += at - c.getBoundingClientRect().bottom - 100; }",
        top(add),
    )
    page.wait_for_timeout(300)
    picked = section(page).locator(".model-pick").last
    before = top(picked)
    assert 0 < before < 500 and top(add) > 500, (before, top(add))
    assert page.evaluate("document.activeElement.textContent").endswith("Add server")
    page.evaluate(
        "() => { const h = [...document.querySelectorAll('.setting.mx h3')]"
        ".find((e) => e.textContent.startsWith('Model servers'));"
        " const d = document.createElement('div'); d.style.height = '300px'; h.after(d); }"
    )
    page.wait_for_timeout(300)
    stays(picked, before)


def test_a_list_read_ending_above_the_focus_moves_nothing(page: Page, clis, server, lms):
    saved_server(lms)
    held: list[Route] = []
    page.route(re.compile(r".*/api/model-servers/.*/probe$"), lambda route: held.append(route))
    page.set_viewport_size({"width": 1280, "height": 900})
    open_settings(page, server)
    toggle(page, "LM Studio дома").click()
    expect(source(page, "LM Studio дома").get_by_text("reading the models…")).to_be_visible()
    add = section(page).get_by_role("button", name="Add server", exact=True)
    add.focus()
    add.scroll_into_view_if_needed()
    before = top(add)
    assert len(held) == 1  # the probe, held while the list reads
    held[0].continue_()
    expect(source(page, "LM Studio дома").get_by_role("button", name="qwen3-8b")).to_be_visible()
    stays(add, before)


def whole(locator: Locator) -> bool:
    """The element shows its whole text: nothing cut by an ellipsis or hidden."""
    return locator.evaluate("e => e.scrollWidth <= e.clientWidth + 1")


def test_a_phones_rows_keep_the_whole_id_and_name(browser: Browser, clis, server, lms, shot):
    """At 390 px: a server model's marks go under its id, which keeps its width; a server's
    name is not cut by its badges; a card shows a model's whole id and where it runs."""
    gone = "qwen/qwen-gone-7b-instruct-q4"
    saved_server(lms)
    state.add_model("Gone", "opencode", gone, "s1")
    gateway = "http://vm-litellm-gw.example.com:4000"
    state.add_model_server("g1", "LiteLLM на работе", gateway, "OpenAI-compatible", [CHAT])
    state.add_model("Opus", "claude", "claude-opus-4-1-20250805", "g1")
    model_settings._write_key("g1", "k-1")  # its badges: OpenAI-compatible, key
    context = browser.new_context(
        viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True
    )
    try:
        page = context.new_page()
        open_settings(page, server)
        name = source(page, "LiteLLM на работе").locator(".mx-src-name")
        expect(name).to_have_text("LiteLLM на работе")
        assert whole(name)
        toggle(page, "LM Studio дома").click()
        row = source(page, "LM Studio дома").get_by_role("button", name=gone, exact=True)
        expect(row).to_contain_text("no longer listed")
        expect(row).to_contain_text("in OpenCode")
        ident = row.locator(".mx-id")
        box = ident.bounding_box()
        assert box and box["width"] >= 200, box  # not squeezed to a letter a line
        for mark in (row.locator(".mx-gone"), row.locator(".mx-in")):
            assert top(mark) >= box["y"] + box["height"] - 1, (top(mark), box)
        row.scroll_into_view_if_needed()
        shot(page, "phone-marks", full_page=False)
        your = card(page, "Claude Code")
        your.scroll_into_view_if_needed()
        for cell in (your.locator(".mx-model"), your.locator(".mx-from")):
            assert whole(cell), cell.text_content()
        shot(page, "phone-whole-ids", full_page=False)
        assert page.evaluate("document.documentElement.scrollWidth") <= 390
    finally:
        context.close()


def test_the_section_at_a_phones_width(browser: Browser, clis, server, lms, shot, monkeypatch):
    twelve = [f"vendor/model-{i}" for i in range(11)] + ["qwen/qwen3-coder-30b-a3b-instruct"]
    listed = dict(fake.PROFILES["lmstudio"])
    listed[("GET", fake.MODELS)] = fake.openai_list(*twelve, fake.EMBEDDINGS)
    monkeypatch.setitem(fake.PROFILES, "lmstudio", listed)
    gateway = "https://litellm-gateway.platform.internal.example.com:4000/v1"
    state.add_model_server("g1", "LiteLLM", gateway, "LiteLLM", ["chat"])
    context = browser.new_context(
        viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True
    )
    try:
        page = context.new_page()
        open_settings(page, server)
        gw = source(page, "LiteLLM")
        expect(gw.locator(".mx-l2")).to_contain_text(gateway)  # whole, wrapped
        assert gw.evaluate(
            "li => { const l = li.querySelector('.mx-l2'); return l.scrollWidth <= l.clientWidth; }"
        )
        change = gw.get_by_role("button", name="Change LiteLLM")
        expect(change).to_be_visible()
        box = change.bounding_box()
        assert box and box["width"] >= 44 and box["height"] >= 44
        # The icons under the name, measured at one moment.
        assert gw.evaluate(
            "li => li.querySelector('.mx-acts').getBoundingClientRect().top >= "
            "li.querySelector('.mx-src-name').getBoundingClientRect().bottom"
        )
        lm = add_server(page, "LM Studio дома", lms.url)
        listing = lm.locator(".mx-list")
        expect(listing.get_by_role("button")).to_have_count(12)
        assert listing.evaluate("l => l.scrollHeight <= l.clientHeight")  # no scroll within
        row = listing.get_by_role("button").first.bounding_box()
        assert row and row["height"] >= 44
        long = twelve[-1]
        lm.get_by_role("button", name=long, exact=True).click()
        lm.get_by_role("checkbox", name=f"{long} on OpenCode", exact=True).click()
        expect(lm.get_by_role("button", name=long, exact=True)).to_contain_text("in OpenCode")
        assert page.evaluate("document.documentElement.scrollWidth") <= 390  # no sideways scroll
        shot(page, "phone", full_page=False)
        opencode = card(page, "OpenCode")
        opencode.scroll_into_view_if_needed()
        expect(opencode).to_contain_text(long)
        x = opencode.get_by_role("button", name=re.compile("^Remove ")).bounding_box()
        assert x and x["width"] >= 44 and x["height"] >= 44
        assert page.evaluate("document.documentElement.scrollWidth") <= 390
        shot(page, "phone-your-models", full_page=False)
    finally:
        context.close()


def test_the_picker_at_a_phones_width(browser: Browser, clis, server, lms, shot):
    saved_server(lms)
    saved = state.add_model(
        "Локальная Qwen для ревью больших репозиториев",
        "opencode",
        "qwen/qwen3-coder-30b-a3b-instruct-mlx-4bit",
        "s1",
    )
    state.set_cli_default(state.ModelRef("opencode", saved.id, None))
    context = browser.new_context(
        viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True
    )
    try:
        page = context.new_page()
        open_settings(page, server)
        field = picker(page, "OpenCode")
        field.scroll_into_view_if_needed()
        box = field.bounding_box()
        assert box and box["height"] >= 44
        label = card(page, "OpenCode").get_by_text("Default model", exact=True).bounding_box()
        assert label and label["y"] + label["height"] <= box["y"] + 1  # over its field
        expect(field.locator(".mp-id")).to_be_hidden()  # the id goes; the name and server stay
        expect(field.locator(".srv")).to_be_visible()
        opencode = card(page, "OpenCode")
        expect(opencode.get_by_text("Your models")).to_be_visible()  # the head's label alone
        expect(opencode.locator(".mx-mhead").get_by_text("From")).to_be_hidden()
        x = opencode.get_by_role("button", name=re.compile("^Remove "))
        x.click()
        ask = opencode.get_by_role("alertdialog")
        for button in ("Remove model", "Cancel"):
            shown = ask.get_by_role("button", name=button).bounding_box()
            assert shown and shown["height"] >= 44, shown
        ask.get_by_role("button", name="Cancel").click()
        expect(x).to_be_focused()
        assert page.evaluate("document.documentElement.scrollWidth") <= 390
        shot(page, "phone-card", full_page=False)
        field.click()
        pop = section(page).locator(".mp-pop")
        expect(pop).to_be_visible()
        shown = pop.bounding_box()
        assert shown and shown["height"] <= 844 * 0.6 + 1, shown
        assert shown["x"] >= 0 and shown["x"] + shown["width"] <= 390, shown
        row = section(page).get_by_role("option").first.bounding_box()
        assert row and row["height"] >= 44
        long = section(page).get_by_role("option", name=re.compile("Локальная Qwen"))
        names = long.locator(".mp-names").bounding_box()
        assert names and names["width"] >= 200, names  # not squeezed to letters by its marks
        mark = long.locator(".srv").bounding_box()
        assert mark and mark["y"] >= names["y"] + names["height"] - 1, (mark, names)  # under it
        assert page.evaluate("document.documentElement.scrollWidth") <= 390
        shot(page, "phone-picker", full_page=False)
        page.keyboard.press("Escape")
        chip = opencode.get_by_role("button", name="Use OpenCode's settings")
        expect(chip).to_be_visible()  # the model is gone from the fake's list
        size = chip.bounding_box()
        assert size and size["height"] >= 32, size
    finally:
        context.close()


def test_a_tick_at_the_page_s_end_stays_under_the_pointer(page: Page, clis, server, lms):
    """At the very end of the page the browser stops the scroll earlier by what went above:
    the anchor must not scroll by that again."""
    saved_server(lms)
    state.add_model("Первая", "opencode", "qwen3-8b", "s1")
    page.set_viewport_size({"width": 1280, "height": 900})
    open_settings(page, server)
    lm = source(page, "LM Studio дома")
    toggle(page, "LM Studio дома").click()
    lm.get_by_role("button", name="qwen3-8b", exact=True).click()
    tick = lm.get_by_role("checkbox", name="qwen3-8b on OpenCode", exact=True)
    expect(lm.get_by_text("as Первая")).to_be_visible()
    page.evaluate(
        "() => { const c = document.querySelector('.content'); c.scrollTop = c.scrollHeight; }"
    )
    page.wait_for_timeout(300)
    before = top(tick)
    tick.click()
    expect(tick).not_to_be_checked()
    page.wait_for_timeout(300)
    stays(tick, before)
