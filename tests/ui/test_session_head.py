"""A session's head in a browser, the page's top bar: one line of 48 px with its project,
title, run time, Stop and the link; its facts in the popover Details, Skip to chat; and the
Activity chat in the middle of a wide column. The fake agent's sessions."""

import os
import re
import subprocess
import sys

import agent_helpers
import fake_provider
import pytest
from playwright.sync_api import Page, expect
from test_main_screen import log_in, running_session

from lado import kits, projects, runtime, state

pytestmark = pytest.mark.ui


def head(page: Page):
    return page.get_by_role("banner").locator(".session-head")


def box(page: Page, selector: str) -> dict:
    return page.locator(selector).first.bounding_box()


def title_button(page: Page):
    return head(page).locator("h1 button")


def details(page: Page):
    return page.get_by_role("dialog", name="Session details")


def open_session(page: Page, server, session: str) -> None:
    log_in(page, server)
    page.goto(f"{server['url']}/sessions/{session}")
    expect(title_button(page)).to_be_visible()


def test_the_head_shows_the_session_and_details_copy_its_link_and_folder(
    page: Page, server, repo, shot
):
    page.set_viewport_size({"width": 1440, "height": 900})
    page.context.grant_permissions(["clipboard-read", "clipboard-write"])
    session = running_session(repo)
    open_session(page, server, session)
    expect(head(page).get_by_role("heading", level=1)).to_have_text(session)
    expect(head(page).get_by_role("img", name="running")).to_be_visible()
    # One line, the bar's own height; the tabs follow it, no head block between.
    expect(
        page.get_by_role("region", name=f"Session {session}").locator(".session-head")
    ).to_have_count(0)
    bar = box(page, ".topbar")
    assert bar["height"] == 48, bar
    for item in (".session-dot", ".session-head h1", ".session-head-actions", ".link"):
        inner = box(page, item)
        assert (
            bar["y"] <= inner["y"] and inner["y"] + inner["height"] <= bar["y"] + bar["height"]
        ), item
    assert box(page, ".session-tabs")["y"] - (bar["y"] + bar["height"]) < 20
    expect(head(page).locator(".session-ran")).to_have_text(re.compile(r"^(<1|\d+) min$"))
    expect(page.get_by_role("banner")).not_to_contain_text(str(repo))
    expect(page.get_by_role("banner").get_by_role("button", name="Copy link")).to_have_count(0)
    shot(page, "running")

    title_button(page).click()
    expect(details(page)).to_contain_text(str(repo))
    expect(details(page)).to_contain_text(f"id {session}")
    expect(details(page).locator(".session-kits")).to_contain_text("default")
    expect(details(page).locator(".session-agent-cli")).to_contain_text("fake")
    shot(page, "details")
    details(page).get_by_role("button", name="Copy link").click()
    expect(details(page).get_by_role("status").filter(has_text="Link copied")).to_be_visible()
    shot(page, "link-copied")
    copied = page.evaluate("navigator.clipboard.readText()")
    assert copied == f"{server['url']}/sessions/{session}"
    details(page).get_by_role("button", name="Copy path").click()
    expect(details(page).get_by_role("status").filter(has_text="Path copied")).to_be_visible()
    assert page.evaluate("navigator.clipboard.readText()") == str(repo)
    page.keyboard.press("Escape")
    expect(details(page)).to_have_count(0)

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


LONG_TITLE = "Экран сессии: шапка в одну строку, факты в Details, много слов (LAD-192)"


def line_is_whole(page: Page) -> None:
    """The top bar is 48 px, its items on one line inside it, none over another, and the page
    does not scroll sideways."""
    found = page.evaluate(
        """() => {
            const bar = document.querySelector('.topbar').getBoundingClientRect();
            const shown = (e) => e.getClientRects().length > 0;
            const items = [...document.querySelectorAll('.session-dot, .session-crumb,'
                + ' .session-title-box, .session-state, .session-ran, .session-branch,'
                + ' .session-head-actions, .system')].filter(shown);
            const boxes = items.map((e) => [e.className, e.getBoundingClientRect()]);
            const middle = bar.top + bar.height / 2;
            const off = boxes.filter(([, r]) => r.top > middle || r.bottom < middle
                    || r.left < bar.left - 1 || r.right > bar.right + 1).map(([name]) => name);
            const over = boxes.flatMap(([a, r], at) => boxes.slice(at + 1)
                .filter(([, s]) => r.right > s.left + 1).map(([b]) => `${a} over ${b}`));
            return { height: bar.height, off, over,
                     wide: document.documentElement.scrollWidth > innerWidth };
        }"""
    )
    assert found == {"height": 48, "off": [], "over": [], "wide": False}


@pytest.fixture
def long_session(tmp_path, monkeypatch, shop_long):
    """A session of 4 kits in a project of a long title, with a long title and branch."""
    subprocess.run(
        ["git", "-C", str(shop_long), "checkout", "-q", "-b", "feature/" + "long-branch-" * 6],
        check=True,
    )
    runtime.start_session(
        None, None, None, "fake", project="shop", repo_name="frontend", title=LONG_TITLE
    )
    agent_helpers.wait_for(
        lambda: state.get_agent("shop-frontend", "supervisor").status == state.IDLE,
        "idle",
        "shop-frontend",
    )
    with state.connect() as db:
        db.execute(
            "UPDATE sessions SET kits = ? WHERE name = ?",
            ('["default", "tracker-yougile", "design-studio", "sdlc"]', "shop-frontend"),
        )
    yield "shop-frontend"
    runtime.stop_session("shop-frontend")


@pytest.mark.parametrize("width", [601, 768, 1101, 1280, 1440, 1600, 1920])
def test_the_line_is_48_px_at_every_width_with_long_names(
    page: Page, long_session, server, shot, width
):
    page.set_viewport_size({"width": width, "height": 800})
    open_session(page, server, long_session)
    crumb = head(page).locator(".session-crumb")
    expect(crumb).to_be_visible()
    line_is_whole(page)
    # At most 16ch; the actions and the link whole.
    assert crumb.evaluate(
        "e => e.getBoundingClientRect().width <= 16 * parseFloat(getComputedStyle(e).fontSize)"
    )
    stop = head(page).get_by_role("button", name="Stop session…")
    assert stop.bounding_box()["height"] == 32
    # Its icon and word side by side, inside the button (a word under the icon overflows it).
    assert stop.evaluate(
        """(e) => { const out = e.getBoundingClientRect();
            return [...e.querySelectorAll('svg, span')].filter((one) => one.getClientRects().length)
                .every((one) => { const r = one.getBoundingClientRect();
                    return r.top >= out.top && r.bottom <= out.bottom
                        && r.left >= out.left && r.right <= out.right; }); }"""
    )
    shot(page, "line")

    title_button(page).click()
    details(page).get_by_role("button", name="Rename").click()
    field = head(page).get_by_role("textbox", name="Session title")
    expect(field).to_be_focused()
    line_is_whole(page)
    hint = head(page).locator(".title-edit-hint")
    expect(hint).to_be_visible()
    assert hint.bounding_box()["y"] >= box(page, ".topbar")["y"] + 48 - 1  # under the line
    shot(page, "editing")
    field.press("Escape")


@pytest.mark.parametrize(
    ("width", "shown"),
    [(1599, False), (1600, True)],
)
def test_the_branch_shows_on_a_wide_window_only(page: Page, server, repo, shot, width, shown):
    page.set_viewport_size({"width": width, "height": 800})
    session = running_session(repo)
    open_session(page, server, session)
    branch = head(page).locator(".session-branch")
    expect(branch).to_have_count(1)
    (expect(branch).to_be_visible if shown else expect(branch).to_be_hidden)()
    if shown:
        expect(branch).to_have_text("main")
        branch.hover()
        expect(page.get_by_role("tooltip")).to_contain_text(str(repo))
    shot(page)


@pytest.mark.parametrize(
    ("width", "word", "link"),
    [(900, False, False), (901, True, False), (1100, True, False), (1101, True, True)],
)
def test_stop_and_the_link_keep_their_words_by_width(
    page: Page, server, repo, shot, width, word, link
):
    page.set_viewport_size({"width": width, "height": 800})
    session = running_session(repo)
    open_session(page, server, session)
    stop = head(page).get_by_role("button", name="Stop session…")
    live = page.get_by_role("button", name="System")
    stop_word = stop.locator(".session-action-word")
    (expect(stop_word).to_be_visible if word else expect(stop_word).to_be_hidden)()
    assert (live.bounding_box()["width"] > 30) == link
    if not link:
        live.hover()
        expect(page.get_by_role("tooltip")).to_have_text("live · LADO server")
    shot(page)


def test_details_opens_by_click_enter_and_space_and_gives_the_focus_back(
    page: Page, server, repo, shot
):
    page.set_viewport_size({"width": 1440, "height": 900})
    session = running_session(repo)
    open_session(page, server, session)
    title = title_button(page)
    copy_path = details(page).get_by_role("button", name="Copy path")
    title.click()
    expect(copy_path).to_be_focused()
    expect(page.get_by_role("tooltip")).to_have_count(0)  # the focus came from no keyboard
    page.keyboard.press("Escape")
    for key in ("Enter", "Space"):
        title.focus()
        page.keyboard.press(key)
        expect(title).to_have_attribute("aria-expanded", "true")
        expect(copy_path).to_be_focused()
        page.keyboard.press("Escape")
        expect(details(page)).to_have_count(0)
        expect(title).to_be_focused()

    title.click()
    placed = details(page).bounding_box()
    under = title.bounding_box()
    assert placed["width"] == 470
    assert placed["y"] >= under["y"] + under["height"]
    shot(page, "open")
    title.click()  # a second click
    expect(details(page)).to_have_count(0)
    expect(title).to_be_focused()

    title.click()
    page.mouse.click(700, 500)  # an empty place of the feed
    expect(details(page)).to_have_count(0)
    expect(title).to_be_focused()

    title.click()
    composer = page.get_by_role("textbox", name="Write to the supervisor…")
    composer.click()
    expect(details(page)).to_have_count(0)
    expect(composer).to_be_focused()
    page.keyboard.type("hello")
    expect(composer).to_have_value("hello")


def test_details_stays_inside_a_narrow_window(page: Page, server, repo, shot):
    page.set_viewport_size({"width": 480, "height": 800})
    session = running_session(repo)
    open_session(page, server, session)
    title_button(page).click()
    placed = details(page).bounding_box()
    assert placed["width"] == 448
    assert placed["x"] >= 0 and placed["x"] + placed["width"] <= 480
    shot(page)


def test_tab_goes_through_skip_the_rail_and_the_heads_four_stops(page: Page, shop, server, shot):
    page.set_viewport_size({"width": 1440, "height": 900})
    runtime.start_session(None, None, None, "fake", project="shop", repo_name="frontend")
    agent_helpers.wait_for(
        lambda: state.get_agent("shop-frontend", "supervisor").status == state.IDLE,
        "idle",
        "shop-frontend",
    )
    try:
        open_session(page, server, "shop-frontend")
        crumb = head(page).locator(".session-crumb")
        expect(crumb).to_be_visible()
        skip = page.get_by_role("link", name="Skip to chat")
        assert skip.bounding_box()["y"] + skip.bounding_box()["height"] <= 0  # out of sight
        skip.focus()
        assert skip.bounding_box()["y"] >= 0  # in sight once it has the focus
        shot(page, "skip")
        page.keyboard.press("Tab")  # the rail follows it: nothing comes before it
        expect(page.get_by_role("navigation", name="Sections", exact=True)).to_contain_text(
            page.evaluate("document.activeElement.textContent")
        )
        crumb.focus()
        stops = []
        for _ in range(4):
            stops.append(
                page.evaluate(
                    """() => {
                        const e = document.activeElement;
                        return e.getAttribute('aria-label') || e.textContent;
                    }"""
                )
            )
            page.keyboard.press("Tab")
        assert stops == ["Shop", "shop-frontend", "Stop session…", "System"]
    finally:
        runtime.stop_session("shop-frontend")


@pytest.mark.parametrize("tab", ["activity", "flows"])
def test_skip_to_chat_puts_the_focus_on_the_feed(page: Page, server, repo, shot, tab):
    page.set_viewport_size({"width": 1440, "height": 900})
    session = running_session(repo)
    log_in(page, server)
    page.goto(f"{server['url']}/sessions/{session}/{tab}")
    expect(title_button(page)).to_be_visible()
    page.get_by_role("link", name="Skip to chat").focus()
    page.keyboard.press("Enter")
    expect(page).to_have_url(re.compile(rf"/sessions/{session}(/activity)?$"))
    expect(page.get_by_role("log", name="Chat with the session")).to_be_focused()


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

    title_button(page).click()
    expect(details(page)).to_be_visible()
    # Its foot, where on_top looks, is over the terminals, well under the bar.
    assert on_top(details(page))
    details(page).get_by_role("button", name="Copy link").click()
    note = details(page).get_by_role("status").filter(has_text="Link copied")
    expect(note).to_be_visible()
    assert on_top(note)
    shot(page, "copied")


def test_details_show_the_remote_and_branch_and_a_kits_version_on_hover(
    page: Page, server, repo, shot
):
    page.set_viewport_size({"width": 1440, "height": 900})
    page.context.grant_permissions(["clipboard-read", "clipboard-write"])
    url = "https://user:secret@github.com/ladohq/lado.git"
    subprocess.run(["git", "-C", str(repo), "remote", "add", "origin", url], check=True)
    session = running_session(repo)
    open_session(page, server, session)
    title_button(page).click()
    shown = details(page)
    expect(shown.locator(".session-git")).to_have_text("github.com/ladohq/lado · main")
    shown.locator(".session-kit").filter(has_text="default").hover()
    version = kits.find("default").load().version
    tip = page.get_by_role("tooltip")
    expect(tip).to_contain_text(f"default v{version}")
    expect(tip).to_contain_text("installed now: the next agent starts with it")
    shot(page, "kit-version")
    shown.locator(".session-git .session-hint").hover()
    expect(tip).to_have_text("https://github.com/ladohq/lado.gitbranch main · " + str(repo))
    shot(page, "remote")
    # The fake agent has no permission modes, so no mode line.
    expect(shown.locator(".session-agent-cli")).not_to_contain_text("permissions")
    shown.locator(".session-agent-cli .session-hint").hover()
    expect(tip).to_contain_text("installed now: the next agent starts with it")
    expect(tip).not_to_contain_text("mode")
    shot(page, "cli")
    shown.get_by_role("button", name="Copy URL").click()
    expect(shown.get_by_role("status").filter(has_text="URL copied")).to_be_visible()
    assert page.evaluate("navigator.clipboard.readText()") == "https://github.com/ladohq/lado.git"


def rename(page: Page) -> None:
    title_button(page).click()
    details(page).get_by_role("button", name="Rename").click()


def test_rename_in_details_edits_the_title_in_the_line(page: Page, server, repo, shot):
    page.set_viewport_size({"width": 1440, "height": 900})
    session = running_session(repo)
    open_session(page, server, session)
    title = head(page).get_by_role("heading", level=1)
    expect(title).to_have_text(session)
    title_button(page).dblclick()  # no field: the second click closes Details
    expect(head(page).get_by_role("textbox", name="Session title")).to_have_count(0)
    rename(page)
    expect(details(page)).to_have_count(0)
    field = head(page).get_by_role("textbox", name="Session title")
    expect(field).to_be_focused()
    expect(field).to_have_attribute("placeholder", session)
    field.fill("Переименовать сессии (LAD-66)")
    shot(page, "editing")
    field.press("Enter")
    expect(title).to_have_text("Переименовать сессии (LAD-66)")
    expect(page.get_by_role("banner")).not_to_contain_text(session)  # the name is in Details
    expect(title_button(page)).to_be_focused()
    assert box(page, ".topbar")["height"] == 48
    expect(page).to_have_title("Переименовать сессии (LAD-66) · LADO")
    row = page.get_by_role("navigation", name="Sessions").locator(".session-row").first
    expect(row.locator(".session-name")).to_have_text("Переименовать сессии (LAD-66)")
    expect(row.locator(".session-about")).to_contain_text(f"{session} · ")
    assert page.url == f"{server['url']}/sessions/{session}"  # the address keeps the name
    assert state.get_session(session).title == "Переименовать сессии (LAD-66)"
    assert state.get_agent(session, "supervisor") is not None  # its agents run on
    shot(page, "renamed")

    rename(page)
    field.fill("x" * 81)
    expect(head(page).get_by_text("81 characters, the limit is 80")).to_be_visible()
    shot(page, "too-long")
    field.press("Escape")
    expect(title).to_have_text("Переименовать сессии (LAD-66)")


def test_a_title_set_by_the_cli_shows_without_a_reload(page: Page, server, repo, shot):
    page.set_viewport_size({"width": 1440, "height": 900})
    session = running_session(repo)
    log_in(page, server)
    page.goto(f"{server['url']}/sessions/{session}")
    title = head(page).get_by_role("heading", level=1)
    expect(title).to_have_text(session)
    done = subprocess.run(
        [sys.executable, str(fake_provider.LADO), "title", session, "Review"],
        capture_output=True,
        text=True,
        env=os.environ,
    )
    assert (done.returncode, done.stdout) == (0, f'{session}: title "Review"\n'), done.stderr
    expect(title).to_have_text("Review")
    row = page.get_by_role("navigation", name="Sessions").locator(".session-row").first
    expect(row.locator(".session-name")).to_have_text("Review")
    shot(page, "from-cli")


def test_tab_takes_the_name_into_the_title_and_other_text_leaves(page: Page, server, repo, shot):
    page.set_viewport_size({"width": 1440, "height": 900})
    session = running_session(repo)
    log_in(page, server)
    page.goto(f"{server['url']}/sessions/{session}")
    title = head(page).get_by_role("heading", level=1)
    expect(title).to_have_text(session)
    rename(page)
    field = head(page).get_by_role("textbox", name="Session title")
    hint = head(page).locator(".title-edit-hint")
    expect(hint).to_have_text("Tab takes the name · Enter to save · Esc to cancel")
    shot(page, "suggested")
    field.press("Tab")
    expect(field).to_have_value(session)
    expect(field).to_be_focused()
    assert field.evaluate("f => [f.selectionStart, f.selectionEnd]") == [len(session)] * 2
    expect(hint).to_have_text("Enter to save · Esc to cancel · empty shows the name")
    assert state.get_session(session).title is None  # nothing sent
    shot(page, "taken")
    field.press_sequentially(" (x)")
    field.press("Enter")
    expect(title).to_have_text(f"{session} (x)")
    expect(title_button(page)).to_be_focused()
    assert state.get_session(session).title == f"{session} (x)"

    rename(page)
    field.fill("zz")
    expect(head(page).locator(".title-edit-rest")).to_have_count(0)
    expect(hint).to_have_text("Enter to save · Esc to cancel · empty shows the name")
    field.press("Tab")
    expect(title).to_have_text("zz")
    expect(field).to_have_count(0)
    assert state.get_session(session).title == "zz"


@pytest.fixture
def shop(tmp_path, monkeypatch):
    """LADO_REPOS=<tmp>/ws with the project shop titled Shop and its repository frontend; a
    test takes it before `server`, so the server's process has it. The repository."""
    monkeypatch.setenv("LADO_REPOS", str(tmp_path / "ws"))
    projects.create("shop", "Shop")
    return agent_helpers.init_repo(projects.folder("shop") / "frontend")


@pytest.fixture
def shop_long(tmp_path, monkeypatch):
    """`shop` under a long title."""
    monkeypatch.setenv("LADO_REPOS", str(tmp_path / "ws"))
    projects.create("shop", "A project with a rather long title that cannot fit")
    return agent_helpers.init_repo(projects.folder("shop") / "frontend")


def test_a_session_in_a_project_has_it_as_the_breadcrumb_and_in_details(
    page: Page, shop, server, shot
):
    page.set_viewport_size({"width": 1440, "height": 900})
    runtime.start_session(None, None, None, "fake", project="shop", repo_name="frontend")
    agent_helpers.wait_for(
        lambda: state.get_agent("shop-frontend", "supervisor").status == state.IDLE,
        "idle",
        "shop-frontend",
    )
    try:
        log_in(page, server)
        page.goto(f"{server['url']}/sessions/shop-frontend")
        crumb = head(page).locator(".session-crumb")
        expect(crumb).to_have_text("Shop")
        crumb.hover()
        expect(page.get_by_role("tooltip")).to_contain_text("Project shop")
        title_button(page).click()
        link = details(page).get_by_role("link", name="Shop")
        expect(link).to_have_attribute("title", "Project shop")
        expect(details(page)).to_contain_text(str(shop))
        shot(page, "project")
        page.keyboard.press("Escape")
        crumb.click()
        expect(page).to_have_url(f"{server['url']}/projects/shop")
    finally:
        runtime.stop_session("shop-frontend")
