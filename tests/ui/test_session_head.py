"""A session's head in a browser, the page's top bar: its name, status and run time, its
folder, kits and agents' CLI, Copy link and Copy path, over the page's content; and the
Activity chat in the middle of a wide column. The fake agent's sessions."""

import re
import subprocess

import pytest
from playwright.sync_api import Page, expect
from test_main_screen import log_in, running_session

from lado import kits, runtime

pytestmark = pytest.mark.ui


def head(page: Page):
    return page.get_by_role("banner").locator(".session-head")


def box(page: Page, selector: str) -> dict:
    return page.locator(selector).first.bounding_box()


def test_the_head_shows_the_session_and_copies_its_link_and_folder(page: Page, server, repo, shot):
    page.set_viewport_size({"width": 1440, "height": 900})
    page.context.grant_permissions(["clipboard-read", "clipboard-write"])
    session = running_session(repo)
    log_in(page, server)
    page.goto(f"{server['url']}/sessions/{session}")
    expect(head(page).get_by_role("heading", level=1)).to_have_text(session)
    expect(head(page).get_by_role("img", name="running")).to_be_visible()
    # One line, the bar's own height; the tabs follow it, no head block between.
    expect(
        page.get_by_role("region", name=f"Session {session}").locator(".session-head")
    ).to_have_count(0)
    bar = box(page, ".topbar")
    assert bar["height"] <= 53, bar
    for item in (
        ".session-dot",
        ".session-head h1",
        ".session-path",
        ".session-head-actions",
        ".link",
    ):
        inner = box(page, item)
        assert (
            bar["y"] <= inner["y"] and inner["y"] + inner["height"] <= bar["y"] + bar["height"]
        ), item
    assert box(page, ".session-tabs")["y"] - (bar["y"] + bar["height"]) < 20
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


@pytest.mark.parametrize("width", [600, 360])
def test_in_a_narrow_window_the_facts_wrap_to_a_second_line_without_scrolling(
    page: Page, server, repo, shot, width
):
    page.set_viewport_size({"width": width, "height": 800})
    session = running_session(repo)
    log_in(page, server)
    page.goto(f"{server['url']}/sessions/{session}")
    expect(head(page).get_by_role("heading", level=1)).to_have_text(session)
    expect(head(page).locator(".session-agent-cli")).to_have_text("fake")
    overflows = page.evaluate(
        """() => [document.documentElement, document.querySelector('.topbar'),
                  document.querySelector('.session'), ...document.querySelectorAll('.topbar *')]
            .filter((e) => e.scrollWidth > e.clientWidth + 1
                && !e.classList.contains('session-path') && !e.classList.contains('link-word')
                && e.tagName !== 'H1'
                && getComputedStyle(e).overflowX !== 'visible'
                || e === document.documentElement && e.scrollWidth > innerWidth)
            .map((e) => e.className || e.tagName)"""
    )
    assert overflows == []
    # Nothing in the head lies outside the top bar, which stays at the window's top.
    outside = page.evaluate(
        """() => {
            const box = document.querySelector('.topbar').getBoundingClientRect();
            return [...document.querySelectorAll('.topbar button, .topbar h1, .session-dot,'
                + ' .session-ran, .session-path, .session-kits, .session-agent-cli, .link')]
                .filter((e) => { const r = e.getBoundingClientRect();
                    return r.left < box.left - 1 || r.right > box.right + 1
                        || r.top < box.top - 1 || r.bottom > box.bottom + 1; })
                .map((e) => e.getAttribute('aria-label') || e.className || e.tagName);
        }"""
    )
    assert outside == []
    if width == 600:
        # The first line: the dot, the name, the run time, the icons and the link's dot;
        # the facts under it.
        name = box(page, ".session-head h1")
        middle = name["y"] + name["height"] / 2
        for item in (".session-dot", ".session-ran", ".session-head-actions", ".link"):
            inner = box(page, item)
            assert inner["y"] <= middle <= inner["y"] + inner["height"], item
        assert box(page, ".session-meta")["y"] >= name["y"] + name["height"]
        expect(page.locator(".link")).to_have_text("live")  # named, its word not shown
        assert box(page, ".link")["width"] < 20
    page.evaluate("window.scrollTo(0, 400)")
    assert box(page, ".topbar")["y"] == 0  # sticky
    page.evaluate("window.scrollTo(0, 0)")
    shot(page)


@pytest.mark.parametrize("width", [1101, 1200])
def test_long_facts_on_a_wide_window_wrap_and_never_lie_over_the_icons(
    page: Page, server, repo, shot, width
):
    page.set_viewport_size({"width": width, "height": 800})
    url = "https://gitlab.example.com/a-group/a-subgroup/a-rather-long-project-name.git"
    subprocess.run(["git", "-C", str(repo), "remote", "add", "origin", url], check=True)
    branch = "feature/session-head-topbar-with-a-long-branch-name"
    subprocess.run(["git", "-C", str(repo), "checkout", "-q", "-b", branch], check=True)
    session = running_session(repo)
    log_in(page, server)
    page.goto(f"{server['url']}/sessions/{session}")
    expect(head(page).locator(".session-git")).to_contain_text(branch)
    # No fact, nor the name or the run time, overlaps the icons or the link; all in the bar.
    found = page.evaluate(
        """() => {
            const bar = document.querySelector('.topbar').getBoundingClientRect();
            const solid = [...document.querySelectorAll('.session-head-actions, .link')]
                .map((e) => e.getBoundingClientRect());
            const over = (a, b) => a.left < b.right - 1 && b.left < a.right - 1
                && a.top < b.bottom - 1 && b.top < a.bottom - 1;
            return [...document.querySelectorAll('.session-meta > *, .session-head h1,'
                    + ' .session-ran, .session-hint, .session-path')]
                .filter((e) => { const r = e.getBoundingClientRect();
                    return solid.some((s) => over(r, s)) || r.left < bar.left - 1
                        || r.right > bar.right + 1 || r.bottom > bar.bottom + 1; })
                .map((e) => e.className || e.tagName);
        }"""
    )
    assert found == []
    # The name stays whole and the icons on the top line.
    name = head(page).locator("h1")
    assert name.evaluate(
        """(e) => { const text = document.createRange(); text.selectNodeContents(e);
            return text.getBoundingClientRect().width <= e.getBoundingClientRect().width; }"""
    )
    assert box(page, ".session-head-actions")["y"] < box(page, ".topbar")["y"] + 20
    shot(page)


def test_what_drops_from_the_top_bar_shows_over_the_expanded_terminals(
    page: Page, server, repo, shot
):
    page.set_viewport_size({"width": 1440, "height": 900})
    page.context.grant_permissions(["clipboard-read", "clipboard-write"])
    session = running_session(repo)
    log_in(page, server)
    page.goto(f"{server['url']}/sessions/{session}")
    panel = page.get_by_role("complementary", name="Terminals")
    panel.get_by_role("button", name="Expand terminal").click()
    expect(panel).to_have_class("terminals expanded")

    def on_top(locator) -> bool:
        found = locator.bounding_box()
        return page.evaluate(
            """([el, x, y]) => el.contains(document.elementFromPoint(x, y))""",
            [
                locator.element_handle(),
                found["x"] + found["width"] / 2,
                found["y"] + found["height"] - 3,
            ],
        )

    head(page).get_by_role("button", name="Stop session…").click()
    asked = page.get_by_role("dialog", name=f'Stop session "{session}"?')
    expect(asked).to_contain_text("you can resume it later")
    # Its foot, where on_top looks, is over the terminals, well under the bar.
    popover = asked.bounding_box()
    assert popover["y"] + popover["height"] > box(page, ".topbar")["height"] + 50
    assert on_top(asked)
    shot(page, "stop")
    page.keyboard.press("Escape")
    expect(asked).to_have_count(0)

    head(page).get_by_role("button", name="Copy link").click()
    note = head(page).get_by_role("status").filter(has_text="Link copied")
    expect(note).to_be_visible()
    assert on_top(note)
    shot(page, "copied")


def test_the_head_shows_the_remote_and_branch_and_a_kits_version_on_hover(
    page: Page, server, repo, shot
):
    page.set_viewport_size({"width": 1440, "height": 900})
    url = "https://user:secret@github.com/ladohq/lado.git"
    subprocess.run(["git", "-C", str(repo), "remote", "add", "origin", url], check=True)
    session = running_session(repo)
    log_in(page, server)
    page.goto(f"{server['url']}/sessions/{session}")
    expect(head(page).locator(".session-git")).to_have_text("github.com/ladohq/lado · main")
    expect(head(page).locator(".session-meta > *")).to_have_count(4)
    # The folder gives up its room, the name stays whole.
    # (Its text against its box: a cut of a fraction of a pixel already shows the "…".)
    assert (
        head(page)
        .locator("h1")
        .evaluate(
            """(e) => { const text = document.createRange(); text.selectNodeContents(e);
            return text.getBoundingClientRect().width <= e.getBoundingClientRect().width; }"""
        )
    )
    head(page).locator(".session-kit").filter(has_text="default").hover()
    version = kits.find("default", str(repo)).load().version
    tip = page.get_by_role("tooltip")
    expect(tip).to_contain_text(f"default v{version}")
    expect(tip).to_contain_text("installed now: the next agent starts with it")
    shot(page, "kit-version")
    head(page).locator(".session-git .session-hint").hover()
    expect(tip).to_have_text("https://github.com/ladohq/lado.gitbranch main · " + str(repo))
    shot(page, "remote")
    # The CLI alone in the line; the fake agent has no permission modes, so no mode line.
    expect(head(page).locator(".session-agent-cli")).to_have_text("fake")
    head(page).locator(".session-agent-cli .session-hint").hover()
    expect(tip).to_contain_text("installed now: the next agent starts with it")
    expect(tip).not_to_contain_text("mode")
    shot(page, "cli")
