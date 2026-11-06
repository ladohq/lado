"""The team in a session's head in a browser (docs/design/ui.md, Session head; LAD-197): its
levels by the window, the title's limit, the list, the keyboard, and the height the feed gets
from it. Big teams are served by the page's own route: what is measured here is the layout."""

import json
import re

import pytest
from playwright.sync_api import Page, expect
from test_main_screen import log_in, running_session

from lado import runtime
from lado.server import run as server_run

pytestmark = pytest.mark.ui

LONG_TITLE = "lad-197 (session head и бюджет высоты Activity)"  # 47 characters
SHORT_TITLE = "lad-197 fix"
TWENTY = "lad-197 session head"  # 20 characters

OWN = ["supervisor", "analyst"]
RUNS = {
    "task/lad-197": ["developer-1", "developer-2", "developer-3", "reviewer"],
    "ui-design/x": ["designer", "critic"],
    "task/lad-200": ["developer-4", "reviewer-2", "integrator", "analyst-2"],
}
FOUR = {"task/lad-197": ["analyst", "developer", "reviewer"]}


def agent(name: str, run: str | None, status: str = "idle") -> dict:
    return {
        "name": name,
        "role": re.sub(r"-\d+$", "", name),
        "provider": "fake",
        "status": status,
        "run": run,
        "task": None,
        "status_reason": None,
        "login_wait": None,
        "branch": None,
        "worktree": None,
        "spawned_at": "2026-11-06T10:00:00.000Z",
        "since": "2026-11-06T10:00:00.000Z",
    }


def team(own: list[str], runs: dict[str, list[str]]) -> list[dict]:
    return [agent(name, None) for name in own] + [
        agent(name, run) for run, names in runs.items() for name in names
    ]


def serve_team(page: Page, session: str, agents: list[dict]) -> None:
    """The session's agents as `agents`, its project LADO as in the mockup."""
    page.route(
        f"**/api/sessions/{session}/agents",
        lambda route: route.fulfill(json=agents),
    )

    def about(route):
        got = route.fetch().json()
        route.fulfill(json={**got, "project": {"id": "lado", "title": "LADO"}})

    page.route(f"**/api/sessions/{session}/about", about)


def settled(page: Page) -> None:
    """The trial's microtask and the observers' turn are over."""
    page.evaluate("new Promise((done) => requestAnimationFrame(() => setTimeout(done)))")


def open_team(page: Page, server, repo, agents: list[dict], title: str, size) -> str:
    session = running_session(repo)
    runtime.set_title(session, title)
    page.set_viewport_size({"width": size[0], "height": size[1]})
    log_in(page, server)
    serve_team(page, session, agents)
    page.goto(f"{server['url']}/sessions/{session}")
    expect(page.get_by_role("toolbar", name="Team")).to_be_visible()
    page.wait_for_function("document.fonts.status === 'loaded' && document.fonts.size > 0")
    settled(page)
    return session


def fit(page: Page) -> dict:
    return page.evaluate(
        """() => {
          const team = document.querySelector('.head-team');
          const title = document.querySelector('.session-title-text');
          return {
            level: Number(team.dataset.fit),
            avatars: team.querySelectorAll('.strip-agent').length,
            chips: [...team.querySelectorAll('.team-chip-name')].map((one) => one.textContent),
            title: Math.round(title.getBoundingClientRect().width),
            sideways: document.documentElement.scrollWidth > innerWidth,
            head: document.querySelector('.topbar').getBoundingClientRect().height,
          };
        }"""
    )


def at(page: Page, width: int) -> dict:
    page.set_viewport_size({"width": width, "height": 900})
    page.wait_for_function(f"innerWidth === {width}")
    settled(page)
    got = fit(page)
    assert not got["sideways"], (width, got)
    assert got["head"] == 48, (width, got)
    return got


def test_twelve_agents_give_way_by_the_window_and_the_title_keeps_its_limit(
    page: Page, server, repo, shot
):
    open_team(page, server, repo, team(OWN, RUNS), LONG_TITLE, (1920, 1080))
    wide = at(page, 1920)
    assert wide["level"] == 1, wide
    assert "deve…-2" in wide["chips"], wide  # 4 letters
    assert wide["title"] == 256, wide
    shot(page, "1920", full_page=False)
    for width, title in ((1440, 438), (1280, 414), (1024, 192)):
        got = at(page, width)
        assert (got["level"], got["avatars"], got["title"]) == (2, 12, title), (width, got)
        expect(page.get_by_role("button", name="All 12 agents")).to_be_visible()
    shot(page, "1024", full_page=False)
    for width, avatars, rest in ((768, 8, 4), (601, 4, 8)):
        got = at(page, width)
        assert (got["level"], got["avatars"]) == (3, avatars), (width, got)
        expect(page.get_by_role("button", name=f"{rest} more agents")).to_have_text(f"+{rest}")
        shot(page, str(width), full_page=False)


def test_a_project_that_comes_late_chooses_the_level_again(page: Page, server, repo):
    """The about comes after the agents: the project takes room from the title, in a line whose
    width did not change."""
    session = running_session(repo)
    runtime.set_title(session, LONG_TITLE)
    page.set_viewport_size({"width": 1920, "height": 1080})
    log_in(page, server)
    held = []
    page.route(
        f"**/api/sessions/{session}/agents", lambda route: route.fulfill(json=team(OWN, RUNS))
    )
    page.route(f"**/api/sessions/{session}/about", lambda route: held.append(route))
    page.goto(f"{server['url']}/sessions/{session}")
    expect(page.get_by_role("toolbar", name="Team")).to_be_visible()
    page.wait_for_function("document.fonts.status === 'loaded' && document.fonts.size > 0")
    settled(page)
    assert "devel…-2" in fit(page)["chips"]  # with no project, 5 letters leave the title its limit
    got = held[0].fetch().json()
    held[0].fulfill(json={**got, "project": {"id": "lado", "title": "LADO"}})
    expect(page.locator(".session-crumb")).to_have_text("LADO")
    settled(page)
    assert "deve…-2" in fit(page)["chips"]


def test_a_short_title_leaves_longer_names(page: Page, server, repo):
    open_team(page, server, repo, team(OWN, RUNS), SHORT_TITLE, (1920, 1080))
    got = at(page, 1920)
    assert got["level"] == 1, got
    assert "devel…-2" in got["chips"], got  # 5 letters
    expect(page.locator(".session-title-text")).to_have_text(SHORT_TITLE)
    assert page.locator(".session-title-text").evaluate("e => e.scrollWidth <= e.clientWidth")


def test_four_agents_keep_their_names_before_the_title_gives_way(page: Page, server, repo, shot):
    open_team(page, server, repo, team(["supervisor"], FOUR), TWENTY, (1920, 1080))
    for width in (1920, 1440, 1280):
        assert at(page, width)["level"] == 0, width
    expect(page.locator(".team-label")).to_have_text("Team")
    shot(page, "1280", full_page=False)
    got = at(page, 1024)
    assert got["level"] == 1, got
    assert got["chips"] == ["supervisor", "analyst", "developer", "reviewer"], got  # whole
    assert at(page, 768)["level"] == 2
    assert page.locator(".session-title-text").evaluate("e => e.scrollWidth <= e.clientWidth")
    assert at(page, 601)["level"] == 2


def test_the_title_field_beside_a_large_team_keeps_the_line(page: Page, server, repo, shot):
    open_team(page, server, repo, team(OWN, RUNS), LONG_TITLE, (1024, 768))
    at(page, 1024)
    page.locator(".session-title button").click()
    page.get_by_role("button", name="Rename").click()
    field = page.get_by_role("textbox", name="Session title")
    expect(field).to_be_visible()
    head = page.locator(".topbar").bounding_box()
    assert head["height"] == 48
    assert field.bounding_box()["y"] < head["y"] + 48
    expect(page.locator(".head-team")).to_have_attribute("data-fit", "2")
    shot(page, full_page=False)


def rename(page: Page) -> None:
    page.locator(".session-title button").click()
    page.get_by_role("button", name="Rename").click()
    expect(page.get_by_role("textbox", name="Session title")).to_be_visible()


@pytest.mark.parametrize(("width", "level"), [(1024, "1"), (768, "2")])
def test_opening_the_title_field_leaves_the_team_as_it_stands(
    page: Page, server, repo, width, level
):
    open_team(page, server, repo, team(["supervisor"], FOUR), TWENTY, (width, 900))
    expect(page.locator(".head-team")).to_have_attribute("data-fit", level)
    rename(page)
    settled(page)
    expect(page.locator(".head-team")).to_have_attribute("data-fit", level)
    page.keyboard.press("Escape")
    expect(page.locator(".session-title-text")).to_be_visible()
    settled(page)
    expect(page.locator(".head-team")).to_have_attribute("data-fit", level)


def test_the_focus_lives_through_a_trial(page: Page, server, repo):
    open_team(page, server, repo, team(OWN, RUNS), LONG_TITLE, (1024, 900))
    toolbar = page.get_by_role("toolbar", name="Team")
    avatar = toolbar.get_by_role("button", name=re.compile("^developer-1,"))
    avatar.focus()
    page.keyboard.press("ArrowRight")
    focused = toolbar.get_by_role("button", name=re.compile("^developer-2,"))
    expect(focused).to_be_focused()
    at(page, 1010)
    expect(focused).to_be_focused()
    page.keyboard.press("Tab")
    expect(page.get_by_role("button", name="Stop session…")).to_be_focused()
    page.keyboard.press("Shift+Tab")
    expect(focused).to_be_focused()  # the toolbar's stop stayed where it was


def test_a_focused_agent_that_goes_behind_the_button_leaves_the_focus_on_it(
    page: Page, server, repo
):
    open_team(page, server, repo, team(OWN, RUNS), LONG_TITLE, (1024, 900))
    toolbar = page.get_by_role("toolbar", name="Team")
    toolbar.get_by_role("button", name=re.compile("^analyst-2,")).focus()
    at(page, 768)
    expect(toolbar.get_by_role("button", name="4 more agents")).to_be_focused()


def test_an_open_list_lives_through_a_trial(page: Page, server, repo):
    open_team(page, server, repo, team(OWN, RUNS), LONG_TITLE, (1024, 900))
    page.get_by_role("button", name="All 12 agents").click()
    dialog = page.get_by_role("dialog", name="Team")
    row = dialog.get_by_role("button", name=re.compile("^reviewer-2"))
    row.focus()
    at(page, 1010)
    expect(dialog).to_be_visible()
    expect(row).to_be_focused()
    at(page, 768)  # another button
    expect(dialog).to_be_visible()
    expect(row).to_be_focused()
    at(page, 1920)  # a level with names, and whole names need no button but this one
    expect(dialog).to_be_visible()
    page.keyboard.press("Escape")
    expect(dialog).to_have_count(0)


def test_the_lost_mark_takes_its_room_from_the_team_not_from_stop(page: Page, server, repo, shot):
    open_team(page, server, repo, team(OWN, RUNS), TWENTY, (1024, 900))
    server_run.stop()
    expect(page.locator(".link-lost, .topbar [role=status]").first).to_have_text("reconnecting…")
    settled(page)
    team_box = page.locator(".head-team").bounding_box()
    last = page.locator(".head-team > *").last.bounding_box()
    stop = page.locator(".session-head-actions").bounding_box()
    assert last["x"] + last["width"] <= team_box["x"] + team_box["width"] + 0.5, (last, team_box)
    assert team_box["x"] + team_box["width"] <= stop["x"], (team_box, stop)
    shot(page, full_page=False)


def test_the_feed_starts_under_the_tabs_whatever_the_team_and_the_terminals(
    page: Page, server, repo, shot
):
    open_team(page, server, repo, team(["supervisor"], FOUR), TWENTY, (1440, 900))
    feed = page.get_by_role("log", name="Chat with the session")
    box = feed.bounding_box()
    assert (box["y"], box["height"]) == (88, 742), box
    shot(page, "open", full_page=False)
    page.get_by_role("button", name="Collapse terminals").click()
    expect(page.get_by_role("button", name="Show the terminals")).to_be_visible()
    box = feed.bounding_box()
    assert (box["y"], box["height"]) == (88, 742), box
    shot(page, "folded", full_page=False)
    for theme in ("dark",):
        page.emulate_media(color_scheme=theme)
        shot(page, theme, full_page=False)
    page.emulate_media(color_scheme="light")


def test_other_tabs_keep_their_gap_under_the_tabs(page: Page, server, repo):
    session = open_team(page, server, repo, team(["supervisor"], {}), TWENTY, (1440, 900))
    page.goto(f"{server['url']}/sessions/{session}/artifacts")
    expect(page.get_by_role("toolbar", name="Team")).to_be_visible()
    gap = page.locator(".session-tabs").evaluate("e => getComputedStyle(e).marginBottom")
    assert gap == "12px"


def test_the_list_opens_a_hidden_agents_terminal_and_closes_as_details_do(
    page: Page, server, repo, shot
):
    agents = team(OWN, RUNS)
    agents[-1]["status"] = "waiting"
    open_team(page, server, repo, agents, LONG_TITLE, (768, 900))
    more = page.get_by_role("button", name="4 more agents, 1 waits for you")
    expect(more).to_be_visible()
    expect(more.locator(".dot-waiting")).to_be_visible()
    more.click()
    dialog = page.get_by_role("dialog", name="Team")
    expect(dialog.get_by_role("heading")).to_have_text("Team · 12 agents")
    expect(dialog.locator(".team-popover-name")).to_have_count(12)
    expect(dialog.get_by_role("link", name="task/lad-197")).to_be_visible()
    box = dialog.bounding_box()
    assert box["width"] == 320
    assert box["x"] + box["width"] <= 768
    assert box["y"] >= more.bounding_box()["y"] + 24
    shot(page, "open", full_page=False)
    page.keyboard.press("Escape")
    expect(dialog).to_have_count(0)
    expect(more).to_be_focused()
    more.click()
    more.click()
    expect(dialog).to_have_count(0)
    more.click()
    page.mouse.click(400, 600)
    expect(dialog).to_have_count(0)
    more.click()
    dialog.get_by_role("button", name=re.compile("^analyst-2")).click()
    expect(dialog).to_have_count(0)
    expect(more).to_have_attribute("data-shown", "true")
    more.click()
    expect(dialog.locator('[aria-current="true"]')).to_contain_text("analyst-2")


def test_the_toolbar_is_one_stop_and_the_head_has_five(page: Page, server, repo):
    open_team(page, server, repo, team(["supervisor"], FOUR), TWENTY, (1440, 900))
    toolbar = page.get_by_role("toolbar", name="Team")
    first = toolbar.get_by_role("button").first
    first.focus()
    page.keyboard.press("ArrowRight")
    expect(toolbar.get_by_role("link")).to_be_focused()
    page.keyboard.press("End")
    expect(toolbar.get_by_role("button").last).to_be_focused()
    page.keyboard.press("Home")
    expect(first).to_be_focused()
    page.keyboard.press("Tab")
    expect(page.get_by_role("button", name="Stop")).to_be_focused()


def test_a_focused_avatars_ring_stands_clear_of_its_pressed_frame(page: Page, server, repo, shot):
    open_team(page, server, repo, team(OWN, RUNS), LONG_TITLE, (1024, 768))
    page.locator(".head-team .strip-agent").nth(
        3
    ).click()  # a narrow window starts with no terminal
    pressed = page.locator('.head-team .strip-agent[aria-pressed="true"]')
    expect(pressed).to_have_count(1)
    pressed.focus()
    page.keyboard.press("ArrowRight")
    page.keyboard.press("ArrowLeft")
    expect(pressed).to_be_focused()
    look = pressed.evaluate(
        """e => {
          const s = getComputedStyle(e);
          return [s.outlineOffset, getComputedStyle(e.querySelector('.dot')).outlineStyle];
        }"""
    )
    assert look == ["5px", "solid"]
    shot(page, full_page=False)


def test_a_team_that_fails_to_load_says_so(page: Page, server, repo):
    session = running_session(repo)
    log_in(page, server)
    page.route(
        f"**/api/sessions/{session}/agents",
        lambda route: route.fulfill(
            status=500, body=json.dumps({"detail": "the database is locked"})
        ),
    )
    page.goto(f"{server['url']}/sessions/{session}")
    alert = page.get_by_role("alert").filter(has_text="team not loaded")
    expect(alert).to_be_visible()
    alert.hover()
    expect(page.get_by_role("tooltip")).to_contain_text("locked")


def test_the_keys_hint_comes_with_the_focus_and_nothing_moves(page: Page, server, repo, shot):
    open_team(page, server, repo, team(["supervisor"], {}), TWENTY, (1440, 900))
    field = page.get_by_role("textbox", name="Write to the supervisor…")
    keys = page.locator(".composer-keys")
    expect(keys).to_be_hidden()
    before = field.bounding_box()
    feed = page.get_by_role("log", name="Chat with the session").bounding_box()
    field.click()
    expect(keys).to_be_visible()
    expect(keys).to_have_text("Enter to send · Shift+Enter for a new line · paste or drop files")
    assert field.bounding_box() == before
    assert page.get_by_role("log", name="Chat with the session").bounding_box() == feed
    for theme in ("light", "dark"):
        page.emulate_media(color_scheme=theme)
        shot(page, f"hint-{theme}", full_page=False)
    page.emulate_media(color_scheme="light")
    field.press("a")
    expect(keys).to_be_hidden()
    assert field.bounding_box() == before
    expect(page.locator(".composer-to")).to_have_count(0)


def test_a_narrow_column_shows_no_hint(page: Page, server, repo):
    open_team(page, server, repo, team(["supervisor"], {}), TWENTY, (1160, 900))
    column = page.get_by_role("region", name="Chat").bounding_box()
    assert column["width"] < 560
    page.get_by_role("textbox", name="Write to the supervisor…").click()
    expect(page.locator(".composer-keys")).to_be_hidden()


def test_an_agents_page_names_the_agent(page: Page, server, repo, shot):
    session = open_team(
        page, server, repo, team(["supervisor", "developer-2"], {}), TWENTY, (1440, 900)
    )
    page.goto(f"{server['url']}/sessions/{session}/agents/developer-2")
    expect(page.locator(".composer-to")).to_have_text("to developer-2")
    shot(page, full_page=False)


def test_the_word_messages_goes_before_the_tabs_give_up_anything(page: Page, server, repo, shot):
    open_team(page, server, repo, team(OWN, RUNS), TWENTY, (1920, 900))
    word = page.locator(".between-label")
    tabs = page.locator(".session-tabs")
    expect(word).to_be_visible()
    expect(tabs).to_have_attribute("data-fit", "0")
    seen = []
    for width in range(1900, 600, -20):
        page.set_viewport_size({"width": width, "height": 900})
        settled(page)
        seen.append((word.is_visible(), tabs.get_attribute("data-fit")))
    assert (False, "0") in seen  # the word gone, the tabs as they were
    assert seen.index((False, "0")) < next(i for i, one in enumerate(seen) if one[1] != "0")
    assert all(one[0] is False for one in seen if one[1] != "0")  # no word on a tab's cost
    expect(page.get_by_role("radio", name="Yours")).to_be_visible()
    shot(page, full_page=False)


def test_yours_all_reads_in_both_themes_and_only_on_activity(page: Page, server, repo, shot):
    session = open_team(page, server, repo, team(["supervisor"], {}), TWENTY, (1440, 900))
    chosen = page.get_by_role("radio", name="All")
    chosen.click()
    expect(chosen).to_have_attribute("aria-checked", "true")
    for theme in ("light", "dark"):
        page.emulate_media(color_scheme=theme)
        look = chosen.evaluate(
            """e => {
              const s = getComputedStyle(e);
              const probe = document.createElement('i');
              probe.style.color = 'var(--action)';
              e.append(probe);
              const action = getComputedStyle(probe).color;
              probe.remove();
              return [s.fontWeight, s.borderTopColor === action];
            }"""
        )
        assert look == ["600", True], theme
        shot(page, theme, full_page=False)
    page.emulate_media(color_scheme="light")
    page.reload()
    expect(page.get_by_role("radio", name="All")).to_have_attribute("aria-checked", "true")
    page.goto(f"{server['url']}/sessions/{session}/flows")
    expect(page.get_by_role("radiogroup")).to_have_count(0)
    expect(page.get_by_role("button", name=re.compile("^Find"))).to_be_visible()


def test_the_icon_chooses_as_the_radios_do(page: Page, server, repo, shot):
    open_team(page, server, repo, team(OWN, RUNS), TWENTY, (1100, 900))
    bar = page.get_by_role("navigation", name="Session sections")
    icon = bar.get_by_role("button", name="Messages between agents")
    expect(icon).to_have_attribute("aria-pressed", "false")
    icon.click()
    expect(icon).to_have_attribute("aria-pressed", "true")
    shot(page, full_page=False)
    at(page, 1440)
    expect(bar.get_by_role("radio", name="All")).to_have_attribute("aria-checked", "true")
    bar.get_by_role("radio", name="Yours").click()
    at(page, 1100)
    expect(icon).to_have_attribute("aria-pressed", "false")


def test_the_focus_passes_between_the_radios_and_the_icon(page: Page, server, repo):
    open_team(page, server, repo, team(OWN, RUNS), TWENTY, (1440, 900))
    bar = page.get_by_role("navigation", name="Session sections")
    yours = bar.get_by_role("radio", name="Yours")
    icon = bar.get_by_role("button", name="Messages between agents")
    yours.focus()
    at(page, 1100)
    expect(icon).to_be_focused()
    expect(page.get_by_role("tooltip")).to_have_count(0)
    at(page, 1120)  # a trial hides the icon for a moment
    expect(icon).to_be_focused()
    expect(page.get_by_role("tooltip")).to_have_count(0)
    at(page, 1440)
    expect(yours).to_be_focused()
    expect(page.get_by_role("tooltip")).to_have_count(0)


def test_find_on_flows_stays_when_the_tabs_scroll(page: Page, server, repo):
    session = open_team(page, server, repo, team(["supervisor"], {}), TWENTY, (1440, 900))
    page.goto(f"{server['url']}/sessions/{session}/flows")
    bar = page.get_by_role("navigation", name="Session sections")
    find = bar.get_by_role("button", name=re.compile("^Find"))
    expect(find).to_be_visible()
    page.add_style_tag(content=".session-tabs { width: 260px; }")
    expect(bar).to_have_attribute("data-fit", "4")
    expect(find).to_be_visible()
    expect(bar.get_by_role("button", name="Messages between agents")).to_have_count(0)


def test_the_agents_tab_says_the_popups_words(page: Page, server, repo, shot):
    agents = [
        agent("supervisor", None, "busy"),
        agent("analyst", None, "waiting"),
        agent("developer", None, "background"),
        agent("reviewer", None, "idle"),
    ]
    session = open_team(page, server, repo, agents, TWENTY, (1440, 900))
    page.get_by_role("link", name=re.compile("^Agents")).click()
    rows = page.get_by_role("navigation", name="Agents")
    for name, words in (
        ("supervisor", "working · "),
        ("analyst", "waits for you · "),
        ("developer", "in the background · "),
        ("reviewer", "idle · "),
    ):
        expect(rows.get_by_role("link", name=re.compile(f"^{name}"))).to_contain_text(words)
    shot(page, full_page=False)
    page.goto(f"{server['url']}/sessions/{session}/agents/analyst")
    expect(page.locator(".agent-now")).to_contain_text(re.compile(r"waits for you · .+ · spawned"))


def test_the_list_buttons_tooltip_is_its_name_and_goes_with_the_list(
    page: Page, server, repo, shot
):
    open_team(page, server, repo, team(OWN, RUNS), LONG_TITLE, (1024, 900))
    button = page.get_by_role("button", name=re.compile(r"^(All 12 agents|\d+ more agents)"))
    name = button.get_attribute("aria-label")
    button.hover()
    expect(page.get_by_role("tooltip")).to_have_text(name)
    shot(page, full_page=False)
    button.click()
    expect(page.get_by_role("dialog", name="Team")).to_be_visible()
    expect(page.get_by_role("tooltip")).to_have_count(0)
