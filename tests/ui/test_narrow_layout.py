"""A session's page by the window's width in a browser (docs/design/ui.md, Structure; LAD-193):
the chat keeps 420 px above 900 px while the columns fold and come back, the tabs give way in
levels, and at 601 to 900 px the page stands still with the list and the terminals over it."""

import json
import re

import pytest
from playwright.sync_api import Page, expect
from test_gates import LONG_NOTE, gated_session, in_sight, waiting_card
from test_main_screen import log_in, running_session

from lado import runtime, state

pytestmark = pytest.mark.ui

LIST_KEY = "lado.sessionsList"
PANEL_KEY = "lado.terminals"
# The tabs' level has settled: they fit, or they are at the last one.
FITS = """() => {
  const row = document.querySelector('.session-tabs-scroll');
  const bar = document.querySelector('.session-tabs');
  return bar.dataset.fit === '3' || row.scrollWidth <= row.clientWidth;
}"""
# The Artifacts tab is whole in the bar, or an arrow says there is more.
TAB_OR_ARROW = """() => {
  const row = document.querySelector('.session-tabs-scroll').getBoundingClientRect();
  const tabs = document.querySelectorAll('.session-tabs .tab-item');
  const last = tabs[tabs.length - 1].getBoundingClientRect();
  const arrow = document.querySelector('.session-tabs-more.end');
  return last.right <= row.right + 1 || arrow !== null;
}"""


def size(page: Page, width: int, height: int = 800) -> None:
    page.set_viewport_size({"width": width, "height": height})


def open_session(page: Page, server, session: str, stored: dict | None = None) -> None:
    log_in(page, server)
    page.goto(f"{server['url']}/sessions/{session}")
    if stored:
        for key, value in stored.items():
            page.evaluate("([k, v]) => localStorage.setItem(k, v)", [key, value])
        page.reload()
    expect(page.get_by_role("region", name=f"Session {session}")).to_be_visible()


def stored(page: Page, key: str):
    return page.evaluate("k => localStorage.getItem(k)", key)


def panel(page: Page):
    return page.get_by_role("complementary", name="Terminals")


def session_list(page: Page):
    return page.locator(".session-list")


def strip(page: Page):
    return page.locator("nav.sessions-strip")


def width_of(locator) -> int:
    return round(locator.bounding_box()["width"])


def chat_width(page: Page) -> int:
    return width_of(page.locator(".session-main"))


def folded(locator) -> None:
    expect(locator).to_have_class(re.compile(r"\bcollapsed\b"))


def not_folded(locator) -> None:
    expect(locator).not_to_have_class(re.compile(r"\bcollapsed\b"))


@pytest.mark.parametrize("opened", [False, True], ids=["nobody-opened", "the-human-opened"])
def test_the_chat_keeps_420_px_at_every_width_and_on_every_tab(
    page: Page, server, repo, shot, opened
):
    size(page, 1440)
    session = running_session(repo)
    keys = {PANEL_KEY: json.dumps({"collapsed": False})} if opened else None
    open_session(page, server, session, keys)
    tabs = page.get_by_role("navigation", name="Session sections")
    for tab in ("Activity", "Agents", "Flows", "Artifacts"):
        tabs.get_by_role("link", name=re.compile(f"^{tab}")).click()
        for width in (1440, 1280, 1101, 1024, 901):
            size(page, width)
            page.wait_for_function(TAB_OR_ARROW)
            assert chat_width(page) >= 420, (tab, width)
        size(page, 1440)
    shot(page, full_page=False)


def test_the_measures_with_nothing_stored(page: Page, server, repo, shot):
    size(page, 1440, 900)
    session = running_session(repo)
    open_session(page, server, session)
    rail = page.locator(".rail")
    expect(panel(page).locator(".term")).to_be_visible()
    assert (width_of(rail), width_of(panel(page)), chat_width(page)) == (60, 448, 672)
    shot(page, "1440", full_page=False)
    size(page, 1280, 900)
    expect(panel(page)).to_have_css("width", "384px")
    assert chat_width(page) == 576
    shot(page, "1280", full_page=False)
    size(page, 1024, 760)
    folded(panel(page))
    assert (width_of(panel(page)), chat_width(page)) == (32, 672)
    shot(page, "1024", full_page=False)
    size(page, 1600, 900)
    expect(rail).to_have_css("width", "216px")


def test_the_humans_rail_wins_and_survives_a_reload(page: Page, server, repo):
    size(page, 1280)
    session = running_session(repo)
    open_session(page, server, session)
    page.get_by_role("button", name="Expand menu").click()
    page.reload()
    expect(page.locator(".rail")).to_have_css("width", "216px")


def test_a_fold_for_room_comes_back_and_stores_nothing(page: Page, server, repo):
    size(page, 1440)
    session = running_session(repo)
    open_session(page, server, session)
    not_folded(panel(page))
    size(page, 1024)
    folded(panel(page))
    expect(session_list(page)).to_be_visible()
    assert stored(page, PANEL_KEY) is None
    assert stored(page, LIST_KEY) is None
    size(page, 1440)
    not_folded(panel(page))
    assert stored(page, PANEL_KEY) is None


def test_the_human_opens_a_column_short_of_room(page: Page, server, repo, shot):
    size(page, 1024, 760)
    session = running_session(repo)
    open_session(page, server, session)
    folded(panel(page))

    panel(page).get_by_role("button", name="Show the terminals").click()
    not_folded(panel(page))
    expect(strip(page)).to_be_visible()
    assert width_of(strip(page)) == 48
    assert (width_of(panel(page)), chat_width(page)) == (366, 550)
    assert json.loads(stored(page, PANEL_KEY)) == {"collapsed": False}
    assert stored(page, LIST_KEY) is None  # the list's fold is the room's
    shot(page, "terminals", full_page=False)
    page.reload()
    not_folded(panel(page))  # the choice survives, and goes by the rule again
    expect(strip(page)).to_be_visible()

    strip(page).get_by_role("button", name="Sessions").click()
    expect(session_list(page)).to_be_visible()
    folded(panel(page))
    assert chat_width(page) >= 420
    shot(page, "list", full_page=False)


def test_the_humans_fold_stays_through_a_narrow_window_and_a_reload(page: Page, server, repo):
    size(page, 1440)
    session = running_session(repo)
    open_session(page, server, session)
    panel(page).get_by_role("button", name="Collapse terminals").click()
    size(page, 1024)
    size(page, 1440)
    page.reload()
    folded(panel(page))


def test_the_rail_opened_by_hand_and_the_terminals_at_901_px(page: Page, server, repo, shot):
    size(page, 901)
    session = running_session(repo)
    open_session(
        page,
        server,
        session,
        {PANEL_KEY: json.dumps({"collapsed": False}), "lado.rail": "expanded"},
    )
    folded(panel(page))
    expect(strip(page)).to_be_visible()
    assert width_of(page.locator(".rail")) == 216
    assert chat_width(page) >= 420
    shot(page, full_page=False)


def test_the_tabs_give_way_in_levels(page: Page, server, repo, shot):
    size(page, 1440)
    session = running_session(repo)
    runtime.spawn_worker(session, "Work", name="w1")
    open_session(page, server, session)
    bar = page.get_by_role("navigation", name="Session sections")
    row = page.locator(".session-tabs-scroll")
    expect(bar.get_by_role("link", name=re.compile("^Agents · 2"))).to_be_visible()
    seen = []
    for width in range(460, 180, -20):
        page.add_style_tag(content=f".session-tabs {{ width: {width}px; }}")
        page.wait_for_function(FITS)
        level = bar.get_attribute("data-fit")
        if level not in seen:
            seen.append(level)
            shot(page, f"level-{level}", full_page=False)
        if level in ("1", "2", "3"):
            assert bar.locator(".tab-item svg").first.is_hidden()
        if level in ("2", "3"):
            assert bar.locator(".tab-count").first.is_hidden()
        if level != "3":
            assert row.evaluate("e => e.scrollWidth <= e.clientWidth"), width
    assert seen == sorted(seen) and "3" in seen, seen

    more = bar.get_by_role("button", name="More tabs")
    earlier = bar.get_by_role("button", name="Earlier tabs")
    expect(more).to_be_visible()
    expect(earlier).to_have_count(0)
    assert width_of(more) == 26
    assert width_of(page.locator(".session-tabs-more.end")) == 56
    more.click()
    expect(more).to_have_count(0)
    expect(earlier).to_be_visible()
    artifacts = bar.get_by_role("link", name=re.compile("^Artifacts")).bounding_box()
    box = row.bounding_box()
    assert artifacts["x"] + artifacts["width"] <= box["x"] + box["width"] + 1
    bar.get_by_role("link", name=re.compile("^Artifacts")).click()  # the tab shown stays in view
    expect(earlier).to_be_visible()


def test_the_terminal_strip_has_a_button_per_agent(page: Page, server, repo, shot):
    size(page, 1024)
    session = running_session(repo)
    runtime.spawn_worker(session, "Work", name="critic")
    open_session(page, server, session)
    terminals = panel(page)
    button = terminals.get_by_role("button", name="Open critic's terminal")
    expect(button).to_be_visible()
    assert width_of(terminals) == 32
    measured = button.bounding_box()
    assert (measured["width"], measured["height"]) == (24, 24)
    expect(button).to_have_text("C")
    order = [
        terminals.get_by_role("button", name="Show the terminals").bounding_box()["y"],
        terminals.get_by_role("button", name="Open supervisor's terminal").bounding_box()["y"],
        measured["y"],
        terminals.get_by_text("Terminals", exact=True).bounding_box()["y"],
    ]
    assert order == sorted(order)
    shot(page, full_page=False)
    button.click()
    expect(terminals.get_by_role("tab", name=re.compile("^critic,"))).to_have_attribute(
        "aria-selected", "true"
    )


def test_a_waiting_agents_button_shows_the_diamond(page: Page, server, repo):
    size(page, 1024)
    session = running_session(repo)
    state.set_status(session, "supervisor", state.WAITING)
    open_session(page, server, session)
    button = panel(page).get_by_role("button", name="Open supervisor's terminal")
    expect(button.locator(".dot")).to_have_class(re.compile("dot-waiting"))


def test_the_strips_badges_tell_task_sessions_apart(page: Page, server, repo, shot):
    size(page, 800, 700)
    first = running_session(repo)
    second = running_session(repo)
    third = running_session(repo)
    state.set_title(first, "lad-154-epic")
    state.set_title(second, "lad-189 (session UI review)")
    state.set_title(third, "web-2154")
    open_session(page, server, first)
    icons = strip(page).locator(".strip-session")
    expect(icons).to_have_text(["154", "189", "154·2"], ignore_case=False)
    assert icons.nth(2).evaluate("e => e.scrollWidth <= e.clientWidth")
    shot(page, full_page=False)


@pytest.mark.parametrize("width", [768, 880])
def test_at_601_to_900_px_the_page_stands_still(page: Page, server, repo, shot, width):
    size(page, width, 1024)
    session = gated_session(repo, LONG_NOTE)
    open_session(page, server, session)
    card = waiting_card(page, session)
    approve = card.get_by_role("button", name="Approve", exact=True)
    composer = page.get_by_role("textbox", name=re.compile("^Write to"))
    expect(approve).to_be_visible()
    in_sight(page, approve, composer)
    page.mouse.move(width / 2, 300)
    page.mouse.wheel(0, 3000)
    page.wait_for_timeout(200)
    assert page.evaluate("window.scrollY") == 0
    in_sight(page, approve, composer)
    assert width_of(strip(page)) == width - 60
    assert strip(page).bounding_box()["height"] == 48
    assert width_of(panel(page)) == 32
    shot(page, full_page=False)


def test_at_768_px_the_list_opens_over_the_session(page: Page, server, repo, shot):
    size(page, 768, 760)
    session = running_session(repo)
    other = running_session(repo)
    open_session(page, server, session)
    sessions = strip(page).get_by_role("button", name="Sessions")
    chat = page.get_by_role("region", name="Chat")
    before = chat.bounding_box()

    sessions.click()
    expect(session_list(page)).to_be_visible()
    placed = session_list(page).bounding_box()
    row = strip(page).bounding_box()
    assert (placed["x"], placed["width"]) == (row["x"], 300)
    assert placed["y"] == row["y"] + row["height"]
    assert chat.bounding_box() == before
    assert page.evaluate("window.scrollY") == 0
    shot(page, full_page=False)

    page.keyboard.press("Escape")
    expect(session_list(page)).to_have_count(0)
    expect(sessions).to_be_focused()

    sessions.click()
    sessions.click()  # its own button closes it
    expect(session_list(page)).to_have_count(0)
    expect(sessions).to_be_focused()

    sessions.click()
    page.mouse.click(600, 300)  # beside it
    expect(session_list(page)).to_have_count(0)
    expect(sessions).to_be_focused()

    sessions.click()
    session_list(page).get_by_role("link", name=re.compile(other)).click()
    expect(page.get_by_role("region", name=f"Session {other}")).to_be_visible()
    expect(session_list(page)).to_have_count(0)
    assert stored(page, LIST_KEY) is None


def test_at_768_px_the_terminals_open_over_the_session(page: Page, server, repo, shot):
    size(page, 768, 760)
    session = running_session(repo)
    open_session(page, server, session, {"lado.askControl": "never"})
    show = panel(page).get_by_role("button", name="Show the terminals")
    chat = page.get_by_role("region", name="Chat")
    before = chat.bounding_box()

    show.click()
    expect(panel(page)).to_have_class(re.compile(r"\bover\b"))
    assert width_of(panel(page)) == 560
    placed = panel(page).bounding_box()
    assert placed["x"] + placed["width"] == 768
    assert chat.bounding_box() == before
    expect(panel(page).locator(".term")).to_have_attribute("data-link", "open")
    shot(page, full_page=False)
    page.keyboard.press("Escape")
    folded(panel(page))
    expect(panel(page).get_by_role("button", name="Show the terminals")).to_be_focused()
    assert stored(page, PANEL_KEY) is None

    panel(page).get_by_role("button", name="Show the terminals").click()
    expect(panel(page).locator(".term")).to_have_attribute("data-link", "open")
    panel(page).get_by_role("button", name="Take control").click()
    expect(panel(page).locator(".term")).to_have_attribute("data-mode", "control")
    expect(panel(page).locator(".term")).to_have_attribute("data-link", "open")
    panel(page).locator(".term-xterm textarea").focus()
    page.keyboard.press("Escape")  # the terminal's
    expect(panel(page)).to_have_class(re.compile(r"\bover\b"))


def test_a_team_chip_at_768_px_opens_the_panel_on_its_agent_and_stores_nothing(
    page: Page, server, repo
):
    size(page, 768, 760)
    session = running_session(repo)
    open_session(page, server, session)
    page.get_by_role("group", name="Team").get_by_role("button").first.click()
    expect(panel(page)).to_have_class(re.compile(r"\bover\b"))
    assert stored(page, PANEL_KEY) is None


def test_a_wide_windows_choice_stays_through_768_px(page: Page, server, repo):
    size(page, 1440)
    session = running_session(repo)
    open_session(
        page,
        server,
        session,
        {PANEL_KEY: json.dumps({"collapsed": False}), LIST_KEY: json.dumps({"collapsed": False})},
    )
    expect(session_list(page)).to_be_visible()
    not_folded(panel(page))
    size(page, 768)
    folded(panel(page))
    expect(session_list(page)).to_have_count(0)
    size(page, 1440)
    expect(session_list(page)).to_be_visible()
    not_folded(panel(page))


@pytest.mark.parametrize("height", [700, 1024])
def test_at_768_px_the_expanded_card_takes_the_window_under_the_top_bar(
    page: Page, server, repo, shot, height
):
    size(page, 768, height)
    session = gated_session(repo, LONG_NOTE)
    open_session(page, server, session)
    card = waiting_card(page, session)
    card.get_by_role("button", name="Expand the card").click()
    expect(card).to_have_class(re.compile(r"\bexpanded\b"))
    expect(strip(page)).to_be_hidden()
    expect(page.get_by_role("navigation", name="Session sections")).to_be_hidden()
    bar = page.get_by_role("banner").bounding_box()
    placed = card.bounding_box()
    assert placed["y"] <= bar["y"] + bar["height"] + 16
    assert placed["y"] + placed["height"] <= height
    assert page.locator(".waiting-card > .splitter-top").count() == 0 or (
        page.locator(".waiting-card > .splitter-top").is_hidden()
    )
    expect(panel(page)).to_be_visible()
    shot(page, full_page=False)


def test_at_768_px_a_short_cards_expanded_card_fills_the_window_too(page: Page, server, repo, shot):
    size(page, 768, 1024)
    session = gated_session(repo)
    open_session(page, server, session)
    card = waiting_card(page, session)
    card.get_by_role("button", name="Expand the card").click()
    expect(card).to_have_class(re.compile(r"\bexpanded\b"))
    placed = card.bounding_box()
    assert placed["y"] + placed["height"] >= 1024 - 40
    terminals = panel(page).bounding_box()
    assert terminals["y"] + terminals["height"] == 1024
    shot(page, full_page=False)


def test_the_lists_edge_stops_where_the_chat_keeps_its_room(page: Page, server, repo):
    """A drag that would fold the list under the pointer stops: the edge stays in hand."""
    size(page, 1440, 900)
    session = running_session(repo)
    open_session(page, server, session, {PANEL_KEY: json.dumps({"width": 640, "collapsed": False})})
    edge = page.get_by_role("separator", name="Resize the session list")
    placed = edge.bounding_box()
    x, y = placed["x"] + placed["width"] / 2, placed["y"] + placed["height"] / 2
    page.mouse.move(x, y)
    page.mouse.down()
    page.mouse.move(x + 40, y)
    page.mouse.move(x + 120, y)
    page.mouse.up()
    expect(edge).to_have_attribute("aria-valuenow", str(1380 - 640 - 420))
    expect(session_list(page)).to_be_visible()
    assert chat_width(page) >= 420
    page.reload()
    expect(session_list(page)).to_be_visible()


def test_the_tabs_choose_their_level_again_when_the_search_comes(page: Page, server, repo):
    """Flows has Find at the bar's end, which takes room from the tabs with the window as it was."""
    size(page, 1440)
    session = running_session(repo)
    runtime.spawn_worker(session, "Work", name="w1")
    open_session(page, server, session)
    bar = page.get_by_role("navigation", name="Session sections")
    expect(bar.get_by_role("link", name=re.compile("^Agents · 2"))).to_be_visible()
    for width in range(240, 460, 10):
        bar.get_by_role("link", name=re.compile("^Activity")).click()
        expect(page.get_by_role("button", name="Find a run")).to_have_count(0)
        page.add_style_tag(content=f".session-tabs {{ width: {width}px; }}")
        page.wait_for_function(FITS)
        bar.get_by_role("link", name=re.compile("^Flows")).click()
        expect(page.get_by_role("button", name="Find a run")).to_be_visible()
        page.wait_for_function(TAB_OR_ARROW, timeout=2000)


def test_expanded_at_768_px_the_terminals_cover_the_page(page: Page, server, repo):
    size(page, 768, 760)
    session = running_session(repo)
    open_session(page, server, session)
    panel(page).get_by_role("button", name="Show the terminals").click()
    panel(page).get_by_role("button", name="Expand terminal").click()
    content = page.locator(".content").bounding_box()
    expect(panel(page)).to_have_class(re.compile(r"\bexpanded\b"))
    assert panel(page).bounding_box() == content
    page.keyboard.press("Escape")
    expect(panel(page)).to_have_class(re.compile(r"\bover\b"))


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_the_screens_by_width(page: Page, server, repo, shot, scheme):
    """A gate's session at each width of the design, for the design's review."""
    page.emulate_media(color_scheme=scheme)
    size(page, 1440, 900)
    session = gated_session(repo)
    open_session(page, server, session)
    for width in (1440, 1280, 1024, 901, 768, 390):
        size(page, width, 844 if width == 390 else 900)
        expect(waiting_card(page, session)).to_be_visible()
        page.wait_for_timeout(200)
        shot(page, f"{width}-{scheme}", full_page=False)


def test_other_pages_at_768_px_scroll_as_before(page: Page, server, repo, shot):
    size(page, 768, 400)
    session = gated_session(repo, LONG_NOTE)
    log_in(page, server)
    page.goto(f"{server['url']}/needs-you")
    card = waiting_card(page, session)
    expect(card).to_be_visible()
    assert page.evaluate("getComputedStyle(document.documentElement).overflowY") == "visible"
    page.mouse.move(400, 200)
    page.mouse.wheel(0, 300)
    page.wait_for_function("window.scrollY > 0")
    shot(page, full_page=False)
