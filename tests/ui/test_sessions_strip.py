"""The session list collapsed to a strip in a browser (docs/design/ui.md, Structure:
Sessions): the session gets the room, an icon opens another session, Sessions opens the list
at its width again; on a narrow window the strip is a row over the session."""

import pytest
from playwright.sync_api import Page, expect
from test_main_screen import log_in, running_session

from lado import runtime

pytestmark = pytest.mark.ui


def box(locator):
    return locator.bounding_box()


def test_the_list_collapses_to_a_strip_that_gives_the_session_room_and_opens_sessions(
    page: Page, server, repo, shot
):
    page.set_viewport_size({"width": 1440, "height": 900})
    calm = running_session(repo)
    asking = running_session(repo)
    runtime.ask_human(asking, "supervisor", "Merge w1 now?", "Tests pass.", ["yes", "later"])
    log_in(page, server)
    page.goto(f"{server['url']}/sessions/{calm}")
    edge = page.get_by_role("separator", name="Resize the session list")
    edge.focus()
    page.keyboard.press("ArrowRight")  # 300 px, remembered
    expect(edge).to_have_attribute("aria-valuenow", "300")
    detail = page.locator(".session-detail")
    before = box(detail)["width"]

    page.get_by_role("button", name="Collapse sessions").click()
    strip = page.locator("nav.sessions-strip")
    expect(strip).to_be_visible()
    expect(edge).to_have_count(0)
    assert box(strip)["width"] == 44
    expect(strip.get_by_role("button", name="Sessions")).to_be_focused()
    assert box(detail)["width"] >= before + 300 - 44 - 1  # the session takes the room
    icons = strip.get_by_role("link")
    expect(icons).to_have_count(2)
    expect(icons.first).to_have_accessible_name(f"{asking}, needs you")  # the one waiting first
    expect(icons.nth(1)).to_have_accessible_name(calm)
    expect(icons.nth(1)).to_have_attribute("aria-current", "page")
    shot(page, "strip")

    icons.first.hover()
    tip = page.get_by_role("tooltip")
    expect(tip).to_contain_text(asking)
    expect(tip).to_contain_text("Needs you: 1 question")
    expect(tip).to_contain_text(str(repo))
    shot(page, "tooltip")

    icons.first.click()
    expect(page.get_by_role("region", name=f"Session {asking}")).to_be_visible()
    assert page.url == f"{server['url']}/sessions/{asking}"
    expect(icons.first).to_have_attribute("aria-current", "page")

    strip.get_by_role("button", name="Sessions").click()
    expect(strip).to_have_count(0)
    expect(page.get_by_role("button", name="Collapse sessions")).to_be_focused()
    assert round(box(page.locator(".session-list"))["width"]) == 300  # its width, kept


def test_on_a_narrow_window_the_list_starts_as_a_row_over_the_session(
    page: Page, server, repo, shot
):
    page.set_viewport_size({"width": 800, "height": 700})
    first = running_session(repo)
    running_session(repo)
    log_in(page, server)
    page.goto(f"{server['url']}/sessions/{first}")
    strip = page.locator("nav.sessions-strip")
    expect(strip).to_be_visible()  # collapsed at first here
    icons = strip.get_by_role("link")
    expect(icons).to_have_count(2)
    show = strip.get_by_role("button", name="Sessions")
    plus = strip.get_by_role("button", name="New session")
    row = box(strip)
    assert row["height"] <= 52
    assert box(strip)["y"] + row["height"] <= box(page.locator(".session-detail"))["y"] + 1
    content = box(page.locator(".content"))
    assert abs(row["width"] - content["width"]) <= 1  # the whole width
    # Sessions, +, then the icons, on one line; the icons scroll sideways.
    parts = [box(show), box(plus), box(icons.first), box(icons.nth(1))]
    assert [part["x"] for part in parts] == sorted(part["x"] for part in parts)
    middles = [part["y"] + part["height"] / 2 for part in parts]
    assert max(middles) - min(middles) <= 2
    column = strip.locator(".strip-icons")
    assert column.evaluate("e => getComputedStyle(e).overflowX") == "auto"
    assert show.evaluate("e => getComputedStyle(e).writingMode") == "horizontal-tb"
    shot(page, "narrow")
