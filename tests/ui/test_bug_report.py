"""Report a bug in the browser (docs/design/ui.md, Report a bug): the rail's item on a
session's page opens the page with the report and GitHub's form, which is never followed."""

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
    page.goto(f"{server['url']}/sessions/{session}?token={server['token']}")
    page.context.grant_permissions(["clipboard-read", "clipboard-write"], origin=server["url"])
    github = []
    page.on("request", lambda request: "github.com" in request.url and github.append(request.url))
    rail = page.get_by_role("navigation", name="Sections")
    rail.get_by_role("link", name="Report a bug").click()
    expect(page).to_have_url(f"{server['url']}/report")
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
    report = rail.get_by_role("link", name="Report a bug")
    expect(report).to_have_attribute("title", "Report a bug")
    expect(report.locator("svg")).to_be_visible()
    expect(report.locator(".rail-name")).to_be_hidden()
    shot(page, "collapsed")
    assert github == []
