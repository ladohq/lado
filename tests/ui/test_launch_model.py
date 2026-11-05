"""The launch window's Model field in a browser (openspec change session-start-model): the picker
of the chosen agent CLI against a real `lado server`, the fake agent and a fake model server in
the test's process: a pick and the start on it, refusals and their ways out, Resume, the agent's
page, and all of it at a phone's width. The server is `lado` with the fake providers."""

import re

import fake_model_server as fake
import pytest
from playwright.sync_api import Browser, Locator, Page, expect
from test_launch import idle, log_in, stopped_session

from lado import model_settings, state

pytestmark = pytest.mark.ui

CLI = "fake-server"
TITLE = "Fake server agent"
QWEN = "Локальная Qwen"
HOME = "LM Studio дома"


@pytest.fixture
def fake_models(monkeypatch):
    """The fake CLI's own list of models, in the server's agents' environment; taken before
    `server`."""
    monkeypatch.setenv("FAKE_AGENT_MODELS", "fake-small,fake-large")


@pytest.fixture
def home_server():
    """A model server saved as LM Studio дома, with the model `m1`, and a saved model on it."""
    server = fake.Server("all")
    model_settings.add_server(HOME, server.url, None, warn=print, note=print)
    state.add_model(QWEN, CLI, "m1", state.model_server(HOME).id)
    yield server
    server.close()


def set_default(name: str = QWEN) -> None:
    saved = state.model(name)
    state.set_cli_default(state.ModelRef(saved.cli, saved.id, None))


def new_window(page: Page, server, repo, cli: str = CLI) -> Locator:
    log_in(page, server)
    page.get_by_role("navigation", name="Sections").get_by_role("button", name="Launch").click()
    dialog = page.get_by_role("dialog", name="New session")
    dialog.get_by_role("button", name="Folder", exact=True).click()  # no sessions: From scratch
    dialog.get_by_role("combobox", name=re.compile("Where")).fill(str(repo))
    expect(dialog).to_contain_text("✓ git repository · branch main")
    dialog.get_by_label("Agent CLI").select_option(cli)
    return dialog


def advanced(dialog: Locator) -> Locator:
    return dialog.locator("details.launch-advanced").last  # after the first message's


def open_advanced(dialog: Locator) -> Locator:
    row = advanced(dialog)
    if row.get_attribute("open") is None:
        row.locator("summary").click()
    return dialog.get_by_role("combobox", name="Model")


def test_a_session_starts_on_a_model_picked_and_its_page_says_so(
    page: Page, fake_models, home_server, server, repo, shot
):
    page.set_viewport_size({"width": 1400, "height": 1000})
    dialog = new_window(page, server, repo)
    model = open_advanced(dialog)
    expect(model).to_contain_text(f"{TITLE}'s settings")
    shot(page, "settings")
    # The whole row of Advanced, of Agent CLI's height, with a chevron of its own.
    agent_cli = dialog.get_by_label("Agent CLI").bounding_box()
    row = advanced(dialog).locator(".launch-grid").bounding_box()
    box = model.bounding_box()
    assert box["height"] == agent_cli["height"]
    assert box["width"] == pytest.approx(row["width"], abs=1)
    expect(model.locator(".mp-arrow")).to_be_visible()
    model.click()
    listed = dialog.get_by_role("listbox", name=f"Models of {TITLE}")
    expect(listed.get_by_role("option", name=re.compile(f"^{QWEN}"))).to_be_visible()
    foot = dialog.locator(".mp-foot")
    expect(foot).to_contain_text("The default comes from Settings → Models.")
    expect(foot.get_by_role("link", name="Settings → Models")).to_have_attribute("target", "_blank")
    shot(page, "list")
    listed.get_by_role("option", name=re.compile(f"^{QWEN}")).click()
    expect(model).to_contain_text(QWEN)
    expect(model).to_contain_text("m1")
    expect(model.locator(".srv")).to_contain_text(HOME)
    shot(page, "picked")
    summary = advanced(dialog).locator("summary")
    summary.click()
    expect(summary).to_have_text(f"Advanced: model {QWEN} on {HOME}")
    shot(page, "folded")

    dialog.get_by_role("button", name="Start session").click()
    expect(page).to_have_url(f"{server['url']}/sessions/my-repo/activity")
    idle("my-repo")
    saved = state.model(QWEN)
    assert state.get_session("my-repo").power.row().model_id == saved.id
    page.goto(f"{server['url']}/sessions/my-repo/agents/supervisor")
    page.get_by_role("button", name="Collapse terminals").click()
    supervisor = page.get_by_role("region", name="Agent supervisor")
    expect(supervisor.locator(".agent-title")).to_contain_text(f"supervisor · {CLI} · {QWEN}")
    expect(supervisor.locator("dl.agent-facts")).to_contain_text(
        f"{QWEN} · m1 · server {HOME}, {home_server.url} · chosen for the session"
    )
    shot(page, "agent")


def test_the_default_is_chosen_in_advance_and_the_session_follows_it(
    page: Page, fake_models, home_server, server, repo, shot
):
    set_default()
    page.set_viewport_size({"width": 1400, "height": 1000})
    dialog = new_window(page, server, repo)
    model = open_advanced(dialog)
    expect(model).to_contain_text(QWEN)
    expect(model.locator(".mc-default")).to_have_text("default")
    expect(dialog.get_by_text(f"{TITLE}'s default model, from Settings → Models.")).to_be_visible()
    shot(page, "default")
    dialog.get_by_role("button", name="Start session").click()
    expect(page).to_have_url(f"{server['url']}/sessions/my-repo/activity")
    idle("my-repo")
    assert state.get_session("my-repo").power is None
    assert state.get_agent("my-repo", "supervisor").model_source == state.DEFAULT_MODEL


def test_a_silent_server_turns_start_off_and_names_the_ways_out(
    page: Page, fake_models, home_server, server, repo, shot
):
    set_default()
    home_server.close()
    page.set_viewport_size({"width": 1400, "height": 1000})
    dialog = new_window(page, server, repo)
    note = advanced(dialog).locator(".field-note.bad")
    expect(note).to_contain_text(f"{HOME} does not answer (", timeout=15_000)
    expect(note).to_contain_text("m1 is on it. Start the server or pick another model.")
    expect(advanced(dialog)).to_have_attribute("open", "")
    start = dialog.get_by_role("button", name="Start session")
    expect(start).to_be_disabled()
    model = dialog.get_by_role("combobox", name="Model")
    expect(model).to_have_attribute("aria-invalid", "true")
    expect(model.locator(".srv.down")).to_be_visible()
    # The note under the focused field, as far below it as Permission mode's note: the focus
    # ring (2 px at a 2 px offset) does not reach it.
    model.focus()
    box, below = model.bounding_box(), note.bounding_box()
    assert below["y"] >= box["y"] + box["height"] + 6
    mode_note = dialog.get_by_text(f"{CLI} takes no permission mode")
    mode = dialog.get_by_label("Permission mode").bounding_box()
    assert below["y"] - (box["y"] + box["height"]) == pytest.approx(
        mode_note.bounding_box()["y"] - (mode["y"] + mode["height"]), abs=0.5
    )
    shot(page, "silent")
    summary = advanced(dialog).locator("summary")
    summary.click()
    expect(summary).to_have_text(f"Advanced: model {QWEN} on {HOME} ! not answering")
    shot(page, "folded")
    summary.click()
    dialog.get_by_role("button", name=f"Use {TITLE}'s settings").click()
    expect(start).to_be_enabled()
    expect(
        dialog.get_by_text(f"For this session only: the agent CLI chooses, not {QWEN}.")
    ).to_be_visible()
    shot(page, "settings")


def test_a_start_refused_at_a_phone_s_width_comes_into_sight(
    browser: Browser, fake_models, home_server, server, repo, shot
):
    """The first message open and long: the field is far below the window's edge when Start is
    pressed."""
    set_default()
    context = browser.new_context(viewport={"width": 390, "height": 844})
    page = context.new_page()
    dialog = new_window(page, server, repo)
    dialog.get_by_text("First message to the supervisor").click()
    dialog.get_by_role("textbox", name="First message").fill("line\n" * 30)
    start = dialog.get_by_role("button", name="Start session")
    expect(start).to_be_enabled()
    expect(advanced(dialog).locator("summary")).to_contain_text(QWEN, timeout=15_000)
    home_server.close()
    start.click()
    expect(dialog.get_by_text("Not started:")).to_contain_text(f"{HOME} does not answer")
    model = dialog.get_by_role("combobox", name="Model")
    expect(model).to_be_focused()
    expect(model).to_be_in_viewport()
    expect(advanced(dialog).locator(".field-note.bad")).to_be_in_viewport()
    shot(page, "refused")
    context.close()


def test_tab_walks_the_list_s_foot_with_the_keyboard(
    page: Page, fake_models, home_server, server, repo, shot
):
    page.set_viewport_size({"width": 1400, "height": 1000})
    dialog = new_window(page, server, repo)
    model = open_advanced(dialog)
    model.focus()
    page.keyboard.press("Enter")
    link = dialog.get_by_role("link", name="Settings → Models")
    expect(link).to_be_visible()
    page.keyboard.press("Tab")
    expect(link).to_be_focused()
    page.keyboard.press("Tab")
    refresh = dialog.get_by_role("button", name="Read the models again")
    if refresh.count():
        expect(refresh).to_be_focused()
        page.keyboard.press("Shift+Tab")
        expect(link).to_be_focused()
        page.keyboard.press("Tab")
        page.keyboard.press("Tab")
    expect(dialog.locator(".mp-pop")).to_have_count(0)
    shot(page, "past-the-foot")


def test_a_model_the_list_lacks_is_refused_in_the_window(
    page: Page, fake_models, server, repo, shot
):
    state.set_cli_default(state.ModelRef("fake", None, "fake-old"))
    page.set_viewport_size({"width": 1400, "height": 1000})
    dialog = new_window(page, server, repo, "fake")
    note = advanced(dialog).locator(".field-note.bad")
    expect(note).to_contain_text("fake-old is not in Fake agent's list of models", timeout=15_000)
    expect(dialog.get_by_role("button", name="Start session")).to_be_disabled()
    expect(dialog.get_by_role("button", name="Use Fake agent's settings")).to_be_visible()
    shot(page, "refused")


def test_resume_of_a_kept_model_the_cli_lacks_says_the_way_out(
    page: Page, fake_models, server, repo, shot
):
    page.set_viewport_size({"width": 1400, "height": 1000})
    session = stopped_session(repo)
    with state.connect() as db:  # as a start with --model fake-old stored it
        db.execute(
            "UPDATE sessions SET power = ? WHERE name = ?",
            (state.PowerTable.single("fake", "fake-old").to_json(), session),
        )
    log_in(page, server, f"/sessions/{session}")
    page.get_by_role("button", name="Resume…").click()
    dialog = page.get_by_role("dialog", name="Resume session")
    note = advanced(dialog).locator(".field-note.bad")
    expect(note).to_contain_text(
        "The session ran on it before. Pick another model, or resume on Fake agent's settings.",
        timeout=30_000,  # the CLIs checked
    )
    resume = dialog.get_by_role("button", name="Resume session")
    expect(resume).to_be_disabled()
    shot(page, "refused")
    dialog.get_by_role("button", name="Use Fake agent's settings").click()
    expect(resume).to_be_enabled()
    resume.click()
    expect(dialog).to_have_count(0)
    idle(session)
    assert state.get_session(session).power == state.PowerTable.single("fake", "")


def test_resume_of_a_model_no_longer_saved_says_so(
    page: Page, fake_models, home_server, server, repo, shot
):
    page.set_viewport_size({"width": 1400, "height": 1000})
    session = stopped_session(repo)
    saved = state.model(QWEN)
    row = state.PowerRow(CLI, saved.model, saved.id, saved.name)
    with state.connect() as db:
        db.execute(
            "UPDATE sessions SET power = ?, provider = ? WHERE name = ?",
            (state.PowerTable.of(row).to_json(), CLI, session),
        )
    state.remove_model(QWEN)
    log_in(page, server, f"/sessions/{session}")
    page.get_by_role("button", name="Resume…").click()
    dialog = page.get_by_role("dialog", name="Resume session")
    expect(advanced(dialog).locator(".field-note.bad")).to_contain_text(
        f"The session ran on the model {QWEN}, which is no longer in Settings → Models.",
        timeout=30_000,
    )
    expect(dialog.get_by_role("combobox", name="Model")).to_contain_text("not in Settings")
    expect(dialog.get_by_role("button", name="Resume session")).to_be_disabled()
    shot(page, "gone")


def test_the_field_and_its_refusal_at_a_phone_s_width(
    browser: Browser, fake_models, home_server, server, repo, shot
):
    set_default()
    home_server.close()
    context = browser.new_context(viewport={"width": 390, "height": 844})
    page = context.new_page()
    dialog = new_window(page, server, repo)
    note = advanced(dialog).locator(".field-note.bad")
    expect(note).to_contain_text(f"{HOME} does not answer (", timeout=15_000)
    scrolls = page.evaluate(
        "() => document.documentElement.scrollWidth > document.documentElement.clientWidth"
    )
    assert not scrolls
    model = dialog.get_by_role("combobox", name="Model")
    box = model.bounding_box()
    assert box["x"] >= 0 and box["x"] + box["width"] <= 390
    # Scrolled into the window by itself: the field and the refusal are on the screen.
    expect(model).to_be_in_viewport()
    expect(note).to_be_in_viewport()
    shot(page, "refused")
    summary = advanced(dialog).locator("summary")
    summary.click()
    mark = summary.locator(".launch-first-mark")
    expect(mark).to_have_text(" ! not answering")
    line = summary.bounding_box()
    shown = mark.bounding_box()
    assert shown["x"] + shown["width"] <= line["x"] + line["width"] + 0.5  # not cut
    shot(page, "folded")
    summary.click()
    model.click()
    popup = dialog.locator(".mp-pop")
    expect(popup).to_be_visible()
    pop = popup.bounding_box()
    assert pop["x"] >= 0 and pop["x"] + pop["width"] <= 390
    shot(page, "list")
    context.close()
