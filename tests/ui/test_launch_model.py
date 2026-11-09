"""The launch window's Model field in a browser (openspec change session-start-model): the picker
of the chosen agent CLI against a real `lado server`, the fake agent and a fake model server in
the test's process: a pick and the start on it, refusals and their ways out, Resume, the agent's
page, and all of it at a phone's width. The server is `lado` with the fake providers."""

import re

import fake_model_server as fake
import pytest
from launch_window import agent, open_team, other_folder, start_button
from playwright.sync_api import Browser, Locator, Page, expect
from test_launch import idle, log_in, stopped_session

from lado import model_settings, runtime, state

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
    dialog, where = other_folder(page)  # no sessions: New empty folder
    where.fill(str(repo))
    expect(dialog).to_contain_text("✓ Ready · branch main")
    agent(dialog).select_option(cli)
    return dialog


def advanced(dialog: Locator) -> Locator:
    """Team, which holds the Model field."""
    return dialog.locator(".launch-team")


def open_advanced(dialog: Locator) -> Locator:
    open_team(dialog)
    return dialog.get_by_role("combobox", name="Model")


def fold(dialog: Locator) -> Locator:
    """Team folded: its summary's model part."""
    dialog.get_by_role("button", name="Hide").click()
    return dialog.locator(".team-sum .launch-first-line")


def test_a_session_starts_on_a_model_picked_and_its_page_says_so(
    page: Page, fake_models, home_server, server, repo, shot
):
    page.set_viewport_size({"width": 1400, "height": 1000})
    dialog = new_window(page, server, repo)
    model = open_advanced(dialog)
    expect(model).to_contain_text(f"{TITLE}'s settings")
    shot(page, "settings")
    # The whole row of Team, of Agent's height, with a chevron of its own.
    agent_cli = dialog.get_by_label("Agent", exact=True).bounding_box()
    row = model.locator("xpath=ancestor::div[contains(@class, 'field')][1]").bounding_box()
    box = model.bounding_box()
    assert box["height"] == agent_cli["height"]
    assert box["width"] == pytest.approx(row["width"], abs=1)
    expect(model.locator(".mp-arrow")).to_be_visible()
    model.click()
    listed = dialog.get_by_role("listbox", name=f"Models of {TITLE}")
    expect(listed.get_by_role("option", name=re.compile(f"^{QWEN}"))).to_be_visible()
    foot = dialog.locator(".mp-foot")
    expect(foot).to_contain_text("The default comes from Settings → Agent CLIs.")
    expect(foot.get_by_role("link", name="Settings → Agent CLIs")).to_have_attribute(
        "target", "_blank"
    )
    shot(page, "list")
    listed.get_by_role("option", name=re.compile(f"^{QWEN}")).click()
    expect(model).to_contain_text(QWEN)
    expect(model).to_contain_text("m1")
    expect(model.locator(".srv")).to_contain_text(HOME)
    shot(page, "picked")
    expect(fold(dialog)).to_have_text(f"Model {QWEN} on {HOME}")
    shot(page, "folded")

    start_button(dialog).click()
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
    expect(
        dialog.get_by_text(f"{TITLE}'s default model, from Settings → Agent CLIs.")
    ).to_be_visible()
    shot(page, "default")
    start_button(dialog).click()
    expect(page).to_have_url(f"{server['url']}/sessions/my-repo/activity")
    idle("my-repo")
    assert state.get_session("my-repo").power is None
    assert state.get_agent("my-repo", "supervisor").model_source == state.DEFAULT_MODEL


def test_a_cli_without_its_login_starts_on_its_one_server_model(
    page: Page, fake_models, logins, server, repo, shot
):
    """openspec change window-server-model-without-login: "fake-claude" takes a server's whole
    process, as Claude Code does, and is not logged in (`logins` holds no file)."""
    cloud = fake.Server("all")
    model_settings.add_server("OpenRouter", cloud.url, None, warn=print, note=print)
    state.add_model("CloudClaude", "fake-claude", "m1", state.model_server("OpenRouter").id)
    page.set_viewport_size({"width": 1280, "height": 900})
    log_in(page, server)
    dialog, where = other_folder(page)
    where.fill(str(repo))
    expect(dialog).to_contain_text("✓ Ready · branch main")
    select = agent(dialog)
    option = select.locator('option[value="fake-claude"]')
    expect(option).to_have_text(
        re.compile(r"^Fake Claude \S+ · not logged in: your server's models only$"),
        timeout=30_000,  # CLIs checked
    )
    expect(option).to_be_enabled()
    select.select_option("fake-claude")
    model = open_advanced(dialog)
    note = dialog.locator(".field-note", has_text="its agents run on your server's models only")
    expect(note).to_have_text(
        "Fake Claude is not logged in: its agents run on your server's models only. Log in for "
        "its own models."
    )
    expect(note).not_to_have_class(re.compile(r"\bbad\b"))
    expect(model).to_contain_text("CloudClaude")
    took = "For this session only: Fake Claude is not logged in, so it runs on your server's model."
    expect(dialog.get_by_text(took)).to_be_visible()
    start = start_button(dialog)
    expect(start).to_be_enabled()
    model.scroll_into_view_if_needed()
    shot(page, "server-model")

    model.click()
    listed = dialog.get_by_role("listbox", name="Models of Fake Claude")
    expect(listed.get_by_role("option", name="fake-small")).to_contain_text("needs login")
    expect(listed.get_by_role("option", name=re.compile("^CloudClaude"))).not_to_contain_text(
        "needs login"
    )
    listed.get_by_role("option", name="fake-small").click()
    refusal = dialog.locator(".field-note.bad")
    expect(refusal).to_contain_text(
        "Fake Claude is not logged in, so it cannot run fake-small: pick a model of your server, "
        "or log in first."
    )
    expect(refusal.get_by_role("button", name="Use CloudClaude")).to_be_visible()
    expect(refusal.get_by_role("button", name="Log in first")).to_be_visible()
    expect(start).to_be_disabled()
    expect(dialog.locator(".launch-missing")).to_contain_text("fix the model")
    shot(page, "built-in-refused")

    refusal.get_by_role("button", name="Use CloudClaude").click()
    expect(start).to_be_enabled()
    start.click()
    expect(page).to_have_url(f"{server['url']}/sessions/my-repo/activity")
    idle("my-repo")
    saved = state.model("CloudClaude")
    assert state.get_session("my-repo").power.row().model_id == saved.id
    runtime.stop_session("my-repo")
    cloud.close()


def test_a_context_too_small_warns_in_the_field_and_start_stays_on(
    page: Page, fake_models, server, repo, shot
):
    small = fake.Server("gateway-limits")
    model_settings.add_server(HOME, small.url, None, warn=print, note=print)
    state.add_model(QWEN, CLI, "small", state.model_server(HOME).id)
    set_default()
    page.set_viewport_size({"width": 1400, "height": 1000})
    dialog = new_window(page, server, repo)
    open_advanced(dialog)
    expect(dialog).to_contain_text(
        f"{QWEN} on {HOME} has a context of 16,000 tokens; {TITLE} needs about 32,768 for its "
        "instructions and tools: load the model with a larger context"
    )
    link = dialog.get_by_role("link", name="docs/install.md ↗")
    expect(link).to_have_attribute(
        "href",
        "https://github.com/ladohq/lado/blob/main/docs/install.md#what-to-expect-of-a-small-model",
    )
    expect(link).to_have_attribute("target", "_blank")
    start = start_button(dialog)
    expect(start).to_be_enabled()
    shot(page, "warning")
    expect(fold(dialog)).to_have_text(f"Model {QWEN} on {HOME} ⚠ context too small")
    shot(page, "folded")
    start.click()
    expect(page).to_have_url(f"{server['url']}/sessions/my-repo/activity")
    idle("my-repo")
    small.close()


def test_a_public_server_s_unknown_context_warns_and_links_its_section(
    page: Page, fake_models, server, repo, shot
):
    """`localhost.` reaches the fake and is no name LADO takes for the human's own machine."""
    public = fake.Server("all")
    address = f"http://localhost.:{public.port}"
    model_settings.add_server(HOME, address, None, warn=print, note=print)
    state.add_model(QWEN, CLI, "m1", state.model_server(HOME).id)
    set_default()
    page.set_viewport_size({"width": 1400, "height": 1000})
    dialog = new_window(page, server, repo)
    open_advanced(dialog)
    expect(dialog).to_contain_text(
        f"{QWEN} on {HOME}: the server reports no context for it, so the agent compacts late and "
        "its answers have no limit"
    )
    expect(dialog.get_by_role("link", name="docs/install.md ↗")).to_have_attribute(
        "href", "https://github.com/ladohq/lado/blob/main/docs/install.md#a-cloud-provider"
    )
    start = start_button(dialog)
    expect(start).to_be_enabled()
    shot(page, "warning")
    expect(fold(dialog)).to_have_text(f"Model {QWEN} on {HOME} ⚠ context unknown")
    shot(page, "folded")
    public.close()


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
    expect(dialog.get_by_role("button", name="Hide")).to_be_visible()  # Team open
    expect(dialog.locator(".launch-missing")).to_have_text("To start: fix the model.")
    start = start_button(dialog)
    expect(start).to_be_disabled()
    model = dialog.get_by_role("combobox", name="Model")
    expect(model).to_have_attribute("aria-invalid", "true")
    expect(model.locator(".srv.down")).to_be_visible()
    # The frame of danger, as the note's bar has it.
    border = model.evaluate("(field) => getComputedStyle(field).borderTopColor")
    danger = page.evaluate(
        """() => {
          const probe = document.body.appendChild(document.createElement("i"));
          probe.style.color = "var(--danger)";
          const color = getComputedStyle(probe).color;
          probe.remove();
          return color;
        }"""
    )
    assert border == danger
    # The note under the focused field: the focus ring (2 px at a 2 px offset) does not
    # reach it.
    model.focus()
    box, below = model.bounding_box(), note.bounding_box()
    assert below["y"] >= box["y"] + box["height"] + 6
    shot(page, "silent")
    expect(fold(dialog)).to_have_text(f"Model {QWEN} on {HOME} ! not answering")
    shot(page, "folded")
    open_team(dialog)
    dialog.get_by_role("button", name=f"Use {TITLE}'s settings").click()
    expect(start).to_be_enabled()
    expect(
        dialog.get_by_text(f"For this session only: the agent CLI chooses, not {QWEN}.")
    ).to_be_visible()
    shot(page, "settings")


def test_a_start_refused_at_a_phone_s_width_comes_into_sight(
    browser: Browser, fake_models, home_server, server, repo, shot
):
    """A long task and Team folded: the field is far below the window's edge when Start is
    pressed."""
    set_default()
    context = browser.new_context(viewport={"width": 390, "height": 844})
    page = context.new_page()
    dialog = new_window(page, server, repo)
    expect(dialog.get_by_role("combobox", name="Model")).to_contain_text(QWEN, timeout=15_000)
    dialog.get_by_role("button", name="Hide").click()
    dialog.get_by_role("textbox", name="Task").fill("line\n" * 30)
    start = start_button(dialog)
    expect(start).to_be_enabled()
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
    link = dialog.get_by_role("link", name="Settings → Agent CLIs")
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


def test_the_focus_in_the_foot_outlives_a_new_read_of_the_list(
    page: Page, fake_models, home_server, server, repo, shot
):
    """The window reads an open list again at its focus, and ↻ reads it too: what has the focus
    in the foot stays, or Esc would reach the dialog and close the window."""
    page.set_viewport_size({"width": 1400, "height": 1000})
    dialog = new_window(page, server, repo)
    model = open_advanced(dialog)
    model.focus()
    page.keyboard.press("Enter")
    link = dialog.get_by_role("link", name="Settings → Agent CLIs")
    expect(link).to_be_visible()
    page.keyboard.press("Tab")
    expect(link).to_be_focused()
    with page.context.expect_page() as settings:
        page.keyboard.press("Enter")
    settings.value.close()
    page.bring_to_front()
    page.evaluate("window.dispatchEvent(new Event('focus'))")
    expect(dialog.get_by_role("option", name=re.compile(f"^{QWEN}"))).to_be_visible()
    expect(link).to_be_focused()

    page.keyboard.press("Tab")
    refresh = dialog.get_by_role("button", name="Read the models again")
    expect(refresh).to_be_focused()
    page.keyboard.press("Enter")
    expect(dialog.get_by_role("option", name=re.compile(f"^{QWEN}"))).to_be_visible()
    expect(refresh).to_be_focused()

    page.keyboard.press("Escape")
    expect(dialog.locator(".mp-pop")).to_have_count(0)
    expect(dialog).to_be_visible()  # the list closed, not the window
    expect(model).to_be_focused()
    shot(page, "closed")


def test_a_model_the_list_lacks_is_refused_in_the_window(
    page: Page, fake_models, server, repo, shot
):
    state.set_cli_default(state.ModelRef("fake", None, "fake-old"))
    page.set_viewport_size({"width": 1400, "height": 1000})
    dialog = new_window(page, server, repo, "fake")
    note = advanced(dialog).locator(".field-note.bad")
    expect(note).to_contain_text("fake-old is not in Fake agent's list of models", timeout=15_000)
    expect(start_button(dialog)).to_be_disabled()
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
    page.locator(".stopped-bar").get_by_role("button", name="Resume session").click()
    dialog = page.get_by_role("dialog", name="Resume session")
    note = advanced(dialog).locator(".field-note.bad")
    expect(note).to_contain_text(
        "The session ran on it before. Pick another model, or resume on Fake agent's settings.",
        timeout=30_000,  # the CLIs checked
    )
    resume = dialog.get_by_role("button", name=f"Resume {session}")
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
    page.locator(".stopped-bar").get_by_role("button", name="Resume session").click()
    dialog = page.get_by_role("dialog", name="Resume session")
    expect(advanced(dialog).locator(".field-note.bad")).to_contain_text(
        f"The session ran on the model {QWEN}, which is no longer in Settings → Model servers.",
        timeout=30_000,
    )
    expect(dialog.get_by_role("combobox", name="Model")).to_contain_text("not in Settings")
    expect(dialog.get_by_role("button", name=f"Resume {session}")).to_be_disabled()
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
    summary = fold(dialog)
    mark = summary.locator(".launch-first-mark")
    expect(mark).to_have_text(" ! not answering")
    line = dialog.locator(".team-sum").bounding_box()
    shown = mark.bounding_box()
    assert shown["x"] + shown["width"] <= line["x"] + line["width"] + 0.5  # not cut
    shot(page, "folded")
    open_team(dialog)
    model.click()
    popup = dialog.locator(".mp-pop")
    expect(popup).to_be_visible()
    pop = popup.bounding_box()
    assert pop["x"] >= 0 and pop["x"] + pop["width"] <= 390
    shot(page, "list")
    context.close()
