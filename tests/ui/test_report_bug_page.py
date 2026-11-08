"""Report a bug in the browser (docs/design/ui.md, Report a bug; Help): the rail's Help on a
session's page opens its menu, whose Report a bug opens the page with the report and GitHub's
form, which is never followed."""

import re

import pytest
from playwright.sync_api import Page, expect
from test_main_screen import running_session

from lado import bug_report, state, telemetry

pytestmark = pytest.mark.ui


def test_report_a_bug_from_a_session_s_page(page: Page, server, repo, shot):
    session = running_session(repo)
    try:
        raise KeyError(f"{repo}/{session}")
    except KeyError as exc:
        telemetry.record("hook:turn_end", exc, "fake", session=session, agent="supervisor")
    page.set_viewport_size({"width": 1600, "height": 900})
    page.goto(f"{server['url']}/sessions/{session}?token={server['token']}")
    page.context.grant_permissions(["clipboard-read", "clipboard-write"], origin=server["url"])
    github = []
    page.on("request", lambda request: "github.com" in request.url and github.append(request.url))
    rail = page.get_by_role("navigation", name="Sections")
    help_ = rail.get_by_role("button", name="Help")
    help_.click()
    menu = page.get_by_role("menu", name="Help")
    expect(menu.get_by_role("menuitem")).to_have_text(["Documentation↗", "GitHub↗", "Report a bug"])
    expect(menu.get_by_role("menuitem", name="Documentation")).to_be_focused()
    box, beside = help_.bounding_box(), menu.bounding_box()
    assert beside["x"] >= box["x"] + box["width"]  # beside the rail, its bottom on Help's
    assert abs(beside["y"] + beside["height"] - (box["y"] + box["height"])) <= 1
    shot(page, "help")
    menu.get_by_role("menuitem", name="Report a bug").click()
    expect(page).to_have_url(f"{server['url']}/report")
    expect(menu).to_have_count(0)
    expect(help_).to_have_class(re.compile(r"\bis-current\b"))
    expect(page.get_by_role("banner").locator("h1")).to_have_text("Report a bug")
    text = page.locator("pre.log")
    expect(text).to_contain_text("### LADO system info")
    expect(text).to_contain_text("- Server: loopback only, up ")
    expect(text).to_contain_text("### LADO errors (last 30 days, 1 kind)")
    expect(text).to_contain_text("- KeyError at hook:turn_end (fake), once, ")
    shown = text.inner_text()
    assert "- Browser: Chrome " in shown
    for secret in (str(state.home()), str(repo), session, server["token"]):
        assert secret not in shown
    link = page.get_by_role("link", name="Open a new issue on GitHub ↗")
    title = "?title=KeyError%20at%20hook%3Aturn_end&body="
    assert link.get_attribute("href").startswith(bug_report.ISSUES_NEW + title)
    assert link.get_attribute("target") == "_blank"
    page.get_by_role("button", name="Copy text").click()
    expect(page.get_by_text("Report copied")).to_be_visible()
    assert page.evaluate("navigator.clipboard.readText()") == shown
    shot(page, "page")
    page.get_by_role("button", name="Collapse menu").click()
    expect(help_).to_have_attribute("title", "Help")
    expect(help_.locator("svg")).to_be_visible()
    expect(help_.locator(".rail-name")).to_be_hidden()
    help_.click()
    expect(page.get_by_role("menu", name="Help")).to_be_in_viewport(ratio=1)
    shot(page, "collapsed")
    page.keyboard.press("Escape")
    expect(help_).to_be_focused()
    assert github == []
