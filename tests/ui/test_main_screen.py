"""The main screen in a browser: the rail and its sections, a session's tabs, the link that
logs in on any page, the theme. Database → API → UI, behind the token."""

import uuid

import agent_helpers
import pytest
from playwright.sync_api import Page, expect

from lado import loop, runtime, state

pytestmark = pytest.mark.ui

SECTIONS = ["Home", "Needs you", "Sessions", "Projects", "Kits", "Marketplace", "Settings"]


def running_session(repo) -> str:
    session = f"ui-{uuid.uuid4().hex[:6]}"
    runtime.start_session(str(repo), session, None, "fake")
    agent_helpers.wait_for(
        lambda: state.get_agent(session, "supervisor").status == state.IDLE, "idle", session
    )
    agent_helpers.wait_for(lambda: loop.running(session), "the session loop", session)
    return session


def log_in(page: Page, server) -> None:
    page.goto(f"{server['url']}/?token={server['token']}")
    assert page.url == f"{server['url']}/"


def test_the_link_opens_the_page_it_names_and_the_session_shows_there(
    page: Page, server, repo, shot
):
    session = running_session(repo)

    page.goto(f"{server['url']}/sessions/{session}/flows?token={server['token']}")
    assert page.url == f"{server['url']}/sessions/{session}/flows"  # the token left the bar
    [cookie] = page.context.cookies()
    assert cookie["name"] == f"lado_token_{server['port']}"
    assert cookie["httpOnly"] and cookie["sameSite"] == "Strict"

    view = page.get_by_role("region", name=f"Session {session}")
    expect(view.get_by_role("region", name="Flows")).to_be_visible()
    expect(view).to_contain_text("running")
    expect(page.get_by_role("navigation", name="Sessions").get_by_role("link")).to_contain_text(
        [session]
    )
    shot(page)

    view.get_by_role("link", name="Agents").click()
    assert page.url == f"{server['url']}/sessions/{session}/agents"
    page.reload()  # an address of the UI holds on a reload
    expect(view.get_by_role("table", name=f"Agents of {session}")).to_be_visible()

    runtime.stop_session(session)
    page.reload()
    expect(view).to_contain_text("stopped")
    shot(page, "stopped")


def test_every_rail_item_opens_its_section(page: Page, server, shot):
    log_in(page, server)
    rail = page.get_by_role("navigation", name="Sections")
    for name in SECTIONS:
        rail.get_by_role("link", name=name, exact=True).click()
        expect(page.get_by_role("banner").get_by_role("heading")).to_have_text(name)
        expect(rail.get_by_role("link", name=name, exact=True)).to_have_attribute(
            "aria-current", "page"
        )
        shot(page, name.lower().replace(" ", "-"))
    page.goto(f"{server['url']}/gates/7")
    expect(page.get_by_role("region", name="Gate #7")).to_be_visible()
    shot(page, "gate")
    page.goto(f"{server['url']}/no/such/page")
    expect(page.get_by_role("banner").get_by_role("heading")).to_have_text("Not found")
    shot(page, "not-found")


def test_the_launch_button_says_how_to_start_a_session(page: Page, server, shot):
    log_in(page, server)
    page.get_by_role("banner").get_by_role("button", name="Launch").click()
    expect(page.get_by_role("dialog", name="Launch a session")).to_contain_text("lado start <repo>")
    shot(page)
    page.keyboard.press("Escape")
    expect(page.get_by_role("dialog")).to_have_count(0)


def test_the_rail_collapses_and_stays_so(page: Page, server, shot):
    log_in(page, server)
    rail = page.get_by_role("navigation", name="Sections")
    page.get_by_role("button", name="Collapse menu").click()
    expect(rail.get_by_text("Marketplace")).to_be_hidden()
    expect(rail.get_by_role("link", name="Marketplace")).to_be_visible()
    shot(page)
    page.reload()
    expect(page.get_by_role("button", name="Expand menu")).to_have_attribute(
        "aria-expanded", "false"
    )


def test_a_narrow_window_starts_with_the_rail_collapsed(page: Page, server, shot):
    page.set_viewport_size({"width": 800, "height": 700})
    log_in(page, server)
    expect(page.get_by_role("button", name="Expand menu")).to_be_visible()
    shot(page)


def test_the_rail_works_from_the_keyboard(page: Page, server):
    log_in(page, server)
    rail = page.get_by_role("navigation", name="Sections")
    rail.get_by_role("link", name="Home").focus()
    for _ in SECTIONS[1:5]:  # Needs you, Sessions, Projects, Kits
        page.keyboard.press("Tab")
    page.keyboard.press("Enter")
    expect(page.get_by_role("banner").get_by_role("heading")).to_have_text("Kits")


GROUND = {"light": "rgb(246, 247, 249)", "dark": "rgb(17, 19, 23)"}


def ground(page: Page) -> str:
    return page.evaluate("getComputedStyle(document.body).backgroundColor")


def test_the_theme_is_chosen_in_settings_and_follows_the_system(page: Page, server, shot):
    page.emulate_media(color_scheme="light")
    log_in(page, server)
    assert ground(page) == GROUND["light"]
    page.emulate_media(color_scheme="dark")  # System: as the computer says
    assert ground(page) == GROUND["dark"]

    page.emulate_media(color_scheme="light")
    page.get_by_role("navigation", name="Sections").get_by_role("link", name="Settings").click()
    page.get_by_role("radio", name="Dark").check()
    assert ground(page) == GROUND["dark"]
    shot(page, "dark")
    page.goto(f"{server['url']}/sessions")
    assert ground(page) == GROUND["dark"]  # remembered
    shot(page, "dark-sessions")

    page.emulate_media(color_scheme="dark")
    page.goto(f"{server['url']}/settings")
    page.get_by_role("radio", name="Light").check()
    assert ground(page) == GROUND["light"]


def test_without_the_token_the_page_says_how_to_get_in(page: Page, server, shot):
    page.goto(f"{server['url']}/settings")
    expect(page.get_by_role("alert")).to_have_text("no valid token: open the link `lado ui` prints")
    assert page.request.get(f"{server['url']}/api/sessions").status == 401
    shot(page)


def test_a_wrong_token_in_the_link_is_refused(page: Page, server):
    answer = page.goto(f"{server['url']}/sessions?token=nope")
    assert answer is not None and answer.status == 401
    assert page.context.cookies() == []


def test_a_missing_file_of_the_bundle_is_not_the_page(page: Page, server):
    assert page.request.get(f"{server['url']}/assets/gone-1234.js").status == 404
    assert page.request.get(f"{server['url']}/api/nope").status == 404
