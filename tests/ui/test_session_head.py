"""A session's head in a browser: its name, status and run time, its folder, kits and
agents' CLI, Copy link and Copy path; and the Activity chat in the middle of a wide column.
The fake agent's sessions."""

import re

import pytest
from playwright.sync_api import Page, expect
from test_main_screen import log_in, running_session

from lado import runtime

pytestmark = pytest.mark.ui


def head(page: Page):
    return page.locator(".session-head")


def test_the_head_shows_the_session_and_copies_its_link_and_folder(page: Page, server, repo, shot):
    page.set_viewport_size({"width": 1440, "height": 900})
    page.context.grant_permissions(["clipboard-read", "clipboard-write"])
    session = running_session(repo)
    log_in(page, server)
    page.goto(f"{server['url']}/sessions/{session}")
    expect(head(page).get_by_role("heading")).to_have_text(session)
    expect(head(page).locator(".session-ran")).to_have_text(re.compile(r"^(<1|\d+) min$"))
    path = head(page).locator(".session-path")
    expect(path).to_have_text(str(repo))
    expect(path).to_have_attribute("title", str(repo))
    expect(head(page).locator(".session-kits")).to_have_text("default")
    expect(head(page).locator(".session-agent-cli")).to_have_text("fake")
    shot(page, "running")

    head(page).get_by_role("button", name="Copy link").click()
    expect(head(page).get_by_role("status").filter(has_text="Link copied")).to_be_visible()
    shot(page, "link-copied")
    copied = page.evaluate("navigator.clipboard.readText()")
    assert copied == f"{server['url']}/sessions/{session}"
    head(page).get_by_role("button", name="Copy path").click()
    expect(head(page).get_by_role("status").filter(has_text="Path copied")).to_be_visible()
    assert page.evaluate("navigator.clipboard.readText()") == str(repo)

    runtime.stop_session(session)
    expect(head(page).locator(".session-ran")).to_have_text(
        re.compile(r"^stopped <1 min ago · ran (<1|\d+) min$")
    )
    shot(page, "stopped")


def gaps(page: Page, box: str, item: str) -> tuple[float, float]:
    """The room left and right of `item` in the content box of `box` (no padding, no
    scroll bar)."""
    return page.evaluate(
        """([box, item]) => {
            const outer = document.querySelector(box);
            const style = getComputedStyle(outer);
            const rect = outer.getBoundingClientRect();
            const left = rect.left + outer.clientLeft + parseFloat(style.paddingLeft);
            const right = rect.left + outer.clientLeft + outer.clientWidth
                - parseFloat(style.paddingRight);
            const inner = document.querySelector(item).getBoundingClientRect();
            return [inner.left - left, right - inner.right];
        }""",
        [box, item],
    )


def chat_with_a_reply(page: Page, server, repo) -> str:
    session = running_session(repo)
    log_in(page, server)
    page.goto(f"{server['url']}/sessions/{session}")
    field = page.get_by_role("textbox", name="Write to the supervisor…")
    field.fill("send human hello")
    field.press("Enter")
    reply = page.get_by_role("article", name="Message from supervisor")
    expect(reply).to_contain_text("hello")
    return session


REPLY = ".chat-feed > [aria-label='Message from supervisor']"


def test_with_the_terminals_folded_the_chat_stands_in_the_middle(page: Page, server, repo, shot):
    # Wide enough for an agent's page to be at its widest, 900 px (below).
    page.set_viewport_size({"width": 2200, "height": 900})
    session = chat_with_a_reply(page, server, repo)
    page.get_by_role("button", name="Collapse terminals").click()
    expect(page.get_by_role("button", name="Collapse terminals")).to_have_count(0)
    for item in (REPLY, ".chat-feed > .chat-start"):  # a message, the start of the session
        left, right = gaps(page, ".chat-feed", item)
        assert left > 50 and abs(left - right) <= 2, (item, left, right)
    left, right = gaps(page, ".chat", ".chat > .composer")
    assert left > 50 and abs(left - right) <= 2, (left, right)
    shot(page, "folded")

    # An agent's composer stays at its page's left edge (the page is at most 900 px, the
    # composer 860: centred, it would stand 20 px in).
    page.goto(f"{server['url']}/sessions/{session}/agents/supervisor")
    composer = ".agent-composer .composer"
    expect(page.locator(composer)).to_be_visible()
    shot(page, "agent")
    left, right = gaps(page, ".agent-page", composer)
    assert abs(left) <= 2 and right > 10, (left, right)
    shot(page, "agent")


def test_in_a_narrow_column_the_chat_takes_its_width(page: Page, server, repo, shot):
    page.set_viewport_size({"width": 1280, "height": 900})
    chat_with_a_reply(page, server, repo)
    expect(page.get_by_role("button", name="Collapse terminals")).to_be_visible()
    left, right = gaps(page, ".chat-feed", REPLY)
    assert abs(left) <= 2 and abs(right) <= 2, (left, right)
    shot(page)


def test_in_a_column_of_360_px_the_head_wraps_without_scrolling(page: Page, server, repo, shot):
    page.set_viewport_size({"width": 360, "height": 800})
    session = running_session(repo)
    log_in(page, server)
    page.goto(f"{server['url']}/sessions/{session}")
    expect(head(page).get_by_role("heading")).to_have_text(session)
    width = page.evaluate("document.querySelector('.session-head').clientWidth")
    assert width <= 360
    overflows = page.evaluate(
        """() => [document.documentElement, document.querySelector('.session'),
                  ...document.querySelectorAll('.session-head, .session-head *')]
            .filter((e) => e.scrollWidth > e.clientWidth + 1
                && !e.classList.contains('session-path') && getComputedStyle(e).overflowX !== 'visible'
                || e === document.documentElement && e.scrollWidth > innerWidth)
            .map((e) => e.className || e.tagName)"""
    )
    assert overflows == []
    # Nothing in the head lies outside it.
    outside = page.evaluate(
        """() => {
            const box = document.querySelector('.session-head').getBoundingClientRect();
            return [...document.querySelectorAll('.session-head button, .session-head h2,'
                + ' .session-ran, .session-path, .session-kits, .session-agent-cli')]
                .filter((e) => { const r = e.getBoundingClientRect();
                    return r.left < box.left - 1 || r.right > box.right + 1; })
                .map((e) => e.getAttribute('aria-label') || e.className || e.tagName);
        }"""
    )
    assert outside == []
    shot(page)
