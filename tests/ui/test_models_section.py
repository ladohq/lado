"""Settings → Models in a browser (openspec change model-settings-page): its three blocks, Your
models, Model servers and Models of your agent CLIs, against a real `lado server`, the fake
model server of tests/fake_model_server.py in the test's process, and stand-ins of Claude Code,
Codex CLI, OpenCode and Kilo CLI on the server's PATH that print a version (Claude Code's
aliases are its provider's own list; Kilo CLI's `kilo models` prints 323 models). Nothing moves
under the pointer: each action keeps the top of what it acted on, or of what holds the focus,
to the pixel, whatever it changes above. On a computer and at a phone's width."""

import os
import re
import socket
import stat

import fake_model_server as fake
import pytest
from playwright.sync_api import Browser, Locator, Page, Route, expect
from test_main_screen import log_in

from lado import model_settings, state

pytestmark = pytest.mark.ui

EMPTY = "No models yet. Without them each agent runs on its agent CLI's default model."
EMPTY_HOW = "Add a model server below, or tick the models your agent CLIs already offer."
KILO_MODELS = 323
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
    expect(section(page).get_by_role("heading", name="Models of your agent CLIs")).to_be_visible()
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


def test_first_open_and_ticking_claude_sonnet(page: Page, clis, server, lms, shot):
    page.set_viewport_size({"width": 1280, "height": 900})
    open_settings(page, server)
    models = section(page)
    expect(models.get_by_role("tablist")).to_have_count(0)
    expect(models.get_by_role("heading", level=3)).to_have_text(
        ["Your models 0", "Model servers", "Models of your agent CLIs"]
    )
    expect(models.get_by_text(EMPTY)).to_be_visible()
    expect(models.get_by_text(EMPTY_HOW)).to_be_visible()
    expect(models.locator(".mx-hit[aria-expanded=true]")).to_have_count(0)  # all closed
    assert lms.requests == []
    shot(page, "first-open")
    claude = source(page, "Claude Code")
    expect(claude.locator(".badge")).to_have_count(0)
    claude.get_by_text("Claude Code", exact=True).click()  # the row's name opens it
    sonnet = claude.get_by_role("checkbox", name="sonnet on Claude Code", exact=True)
    sonnet.scroll_into_view_if_needed()  # where the click would scroll it: measured there
    before = top(sonnet)
    sonnet.click()  # the tick follows the saved model, not the click: no check()
    expect(claude.get_by_text("as Claude Sonnet")).to_be_visible()
    expect(card(page, "Claude Code")).to_be_visible()  # a card above
    stays(sonnet, before)  # nothing moved under the pointer
    expect(models.get_by_role("heading", name="Your models 1")).to_be_visible()
    assert [m.name for m in state.models()] == ["Claude Sonnet"]
    shot(page, "claude-sonnet")
    sonnet.click()
    expect(sonnet).not_to_be_checked()
    expect(card(page, "Claude Code")).to_have_count(0)  # the card above went
    stays(sonnet, before)
    expect(models.get_by_role("button", name="Undo")).to_have_count(0)  # the tick is its undo
    assert state.models() == []


def test_a_tick_in_the_middle_of_a_long_list_moves_nothing(page: Page, clis, server, shot):
    page.set_viewport_size({"width": 1280, "height": 900})
    open_settings(page, server)
    kilo = source(page, "Kilo CLI")
    toggle(page, "Kilo CLI").click()
    expect(kilo.get_by_text(f"{KILO_MODELS} models", exact=True)).to_be_visible()
    listing = kilo.locator(".mx-list")
    box = listing.bounding_box()
    assert box and box["height"] <= 9 * 36 + 2  # nine rows, scrolled within
    listing.evaluate("list => { list.scrollTop = list.scrollHeight / 2; }")
    middle = kilo.get_by_role("checkbox", name="vendor/model-160 on Kilo CLI", exact=True)
    middle.scroll_into_view_if_needed()
    before = top(middle)
    middle.click()
    expect(card(page, "Kilo CLI")).to_be_visible()  # its card added above
    expect(middle).to_be_checked()
    stays(middle, before)
    shot(page, "kilo")
    kilo.get_by_role("searchbox", name=f"Search {KILO_MODELS} models").fill("model-32")
    expect(kilo.get_by_text(f"4 of {KILO_MODELS} models")).to_be_visible()  # 32, 320-322


def test_x_undo_and_undo_running_out_move_nothing(page: Page, clis, server, shot):
    state.add_model("Claude Sonnet", "claude", "sonnet", None)
    state.add_model("gpt-5-codex", "codex", "gpt-5-codex", None)
    page.set_viewport_size({"width": 1280, "height": 900})
    open_settings(page, server)
    claude = card(page, "Claude Code")
    x = claude.get_by_role("button", name="Remove Claude Sonnet")
    x.scroll_into_view_if_needed()
    row = claude.get_by_role("row").nth(1)
    at = top(row)
    x.click()
    undo = claude.get_by_role("button", name="Undo")
    expect(undo).to_be_focused()
    stays(row, at)  # the row keeps its place and height
    expect(row).to_have_text("Removed Claude Sonnet.Undo")
    shot(page, "your-models-undo")
    undo.click()
    name = claude.get_by_role("button", name="Rename Claude Sonnet")
    expect(name).to_be_focused()
    stays(row, at)
    assert sorted(m.name for m in state.models()) == ["Claude Sonnet", "gpt-5-codex"]

    # × again, then the human works below while its Undo runs out.
    claude.get_by_role("button", name="Remove Claude Sonnet").click()
    expect(undo).to_be_visible()
    toggle(page, "Codex CLI").click()
    codex = source(page, "Codex CLI").get_by_role("checkbox", name="gpt-5-codex on Codex CLI")
    codex.focus()
    below = top(codex)
    page.wait_for_timeout(UNDO_S * 1000 + 500)
    expect(undo).to_have_count(0)
    expect(row).to_have_text("Removed Claude Sonnet.")  # the line stays
    stays(codex, below)
    codex.click()  # the next change: the line goes, Claude Code's card above with it
    expect(row).to_have_count(0)
    expect(card(page, "Claude Code")).to_have_count(0)
    stays(codex, below)


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
    expect(found).to_contain_text("Codex CLI, Kilo CLI, OpenCode")
    expect(models.locator("label", has_text="Key")).to_contain_text("optional")
    shot(page, "form-checked")
    add = models.get_by_role("button", name="Add server", exact=True)
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
    expect(card(page, "OpenCode")).to_be_visible()  # a card above
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
    expect(card(page, "OpenCode")).to_have_count(0)  # the card above went
    line = models.locator("li.mx-src").filter(has=page.get_by_text(removed))
    stays(line, at)  # its line in its place
    assert state.model_servers() == [] and state.models() == []
    assert not model_settings.key_folder(id).exists()
    expect(models.get_by_text(EMPTY)).to_be_visible()


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


def test_the_page_never_scrolls_by_itself(page: Page, clis, server, lms):
    """Opened at /settings, no #models, nothing pressed: the sections above grow as their
    rows come and Models renders as its rows come, and the page stays at its top."""
    state.add_model("Claude Sonnet", "claude", "sonnet", None)
    state.add_model_server("s1", "LM Studio дома", lms.url, "LM Studio", ["chat completions"])
    page.set_viewport_size({"width": 1280, "height": 900})
    log_in(page, server)
    page.goto(f"{server['url']}/settings")
    expect(section(page).get_by_role("heading", name="Models of your agent CLIs")).to_be_visible()
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
    state.add_model("Claude Sonnet", "claude", "sonnet", None)
    page.set_viewport_size({"width": 1280, "height": 900})
    log_in(page, server)
    page.goto(f"{server['url']}/settings#models")
    expect(section(page).get_by_role("heading", name="Models of your agent CLIs")).to_be_visible()
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


def test_a_section_above_growing_is_no_change_to_undo(page: Page, clis, server):
    """The human acted in Models (opened Claude Code, its list still reading); then a section
    above grows by 300 px, the page not following it (Safari has no scroll anchoring): the
    list's read ending scrolls nothing to make up for it."""
    held: list[Route] = []
    page.route(re.compile(r".*/api/providers/claude/models.*"), lambda route: held.append(route))
    page.set_viewport_size({"width": 1280, "height": 900})
    open_settings(page, server)
    page.add_style_tag(content=".content { overflow-anchor: none; }")  # as Safari, which has none
    toggle(page, "Claude Code").click()
    expect(source(page, "Claude Code").get_by_text("reading the models…")).to_be_visible()
    page.evaluate(
        "() => { const d = document.createElement('div'); d.style.height = '300px';"
        " document.querySelector('.pv-list').prepend(d); }"
    )
    before = page.evaluate("document.querySelector('.content').scrollTop")
    assert len(held) == 1
    held[0].continue_()
    expect(
        source(page, "Claude Code").get_by_role("checkbox", name="sonnet on Claude Code")
    ).to_be_visible()
    page.wait_for_timeout(300)
    assert page.evaluate("document.querySelector('.content').scrollTop") == before


def test_the_focus_out_of_view_holds_nothing(page: Page, clis, server):
    """The focus on Kilo CLI's row, the human scrolled up so that Your models shows and Kilo
    CLI is below the view: 300 px growing between them moves nothing that shows."""
    state.add_model("Claude Sonnet", "claude", "sonnet", None)
    page.set_viewport_size({"width": 1280, "height": 900})
    open_settings(page, server)
    kilo = toggle(page, "Kilo CLI")
    kilo.focus()
    page.mouse.move(640, 450)
    page.mouse.wheel(0, -1)  # the human's: #models no longer kept at the top
    page.evaluate(
        "(at) => { const c = document.querySelector('.content');"
        " c.scrollTop += at - c.getBoundingClientRect().bottom - 100; }",
        top(kilo),
    )
    page.wait_for_timeout(300)
    heading = section(page).get_by_role("heading", name=re.compile(r"^Your models"))
    before = top(heading)
    assert 0 < before < 900 and top(kilo) > 900, (before, top(kilo))
    assert page.evaluate("document.activeElement.textContent").startswith("Kilo CLI")
    page.evaluate(
        "() => { const h = [...document.querySelectorAll('.setting.mx h3')]"
        ".find((e) => e.textContent.startsWith('Models of your agent CLIs'));"
        " const d = document.createElement('div'); d.style.height = '300px'; h.after(d); }"
    )
    page.wait_for_timeout(300)
    stays(heading, before)


def test_a_list_read_ending_above_the_focus_moves_nothing(page: Page, clis, server, lms):
    state.add_model_server("s1", "LM Studio дома", lms.url, "LM Studio", ["chat completions"])
    held: list[Route] = []
    page.route(re.compile(r".*/api/model-servers/.*/probe$"), lambda route: held.append(route))
    page.set_viewport_size({"width": 1280, "height": 900})
    open_settings(page, server)
    toggle(page, "LM Studio дома").click()
    expect(source(page, "LM Studio дома").get_by_text("reading the models…")).to_be_visible()
    toggle(page, "Claude Code").click()
    sonnet = source(page, "Claude Code").get_by_role("checkbox", name="sonnet on Claude Code")
    sonnet.focus()
    sonnet.scroll_into_view_if_needed()
    before = top(sonnet)
    assert len(held) == 1  # the probe, held while the list reads
    held[0].continue_()
    expect(source(page, "LM Studio дома").get_by_role("button", name="qwen3-8b")).to_be_visible()
    stays(sonnet, before)


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
