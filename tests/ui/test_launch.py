"""Launch and session control in a browser: a session started from the New session window,
a refused folder, the session list row's menu, Stop from the session's head, Resume and
Forget. The server is `lado` with the fake providers, so what it starts runs the fake
agent."""

import re
import uuid

import agent_helpers
import pytest
from playwright.sync_api import Page, expect

from lado import loop, runtime, state

pytestmark = pytest.mark.ui


def log_in(page: Page, server, path: str = "/sessions") -> None:
    page.goto(f"{server['url']}{path}?token={server['token']}")


def idle(session: str) -> None:
    def ready():
        agent = state.get_agent(session, "supervisor")
        return agent is not None and agent.status == state.IDLE

    agent_helpers.wait_for(ready, "the supervisor idle", session)


def running_session(repo) -> str:
    session = f"ui-{uuid.uuid4().hex[:6]}"
    runtime.start_session(str(repo), session, None, "fake")
    idle(session)
    agent_helpers.wait_for(lambda: loop.running(session), "the session loop", session)
    return session


def stopped_session(repo) -> str:
    session = running_session(repo)
    runtime.stop_session(session)
    return session


def test_a_session_starts_from_the_new_session_window(page: Page, server, repo, shot):
    log_in(page, server)
    page.get_by_role("navigation", name="Sections").get_by_role("button", name="Launch").click()
    dialog = page.get_by_role("dialog", name="New session")
    dialog.get_by_role("combobox", name=re.compile("Where")).fill(str(repo))
    expect(dialog).to_contain_text("✓ git repository · branch main")
    expect(dialog.get_by_role("textbox", name="Name")).to_have_value("my-repo")
    dialog.get_by_label("Provider").select_option("fake")
    shot(page, "window")

    dialog.get_by_role("button", name="Start session").click()
    expect(page).to_have_url(f"{server['url']}/sessions/my-repo/activity")
    expect(dialog).to_have_count(0)
    idle("my-repo")
    view = page.get_by_role("region", name="Session my-repo")
    expect(view.get_by_role("group", name="Team")).to_contain_text("supervisor")
    assert state.get_session("my-repo").provider == "fake"
    shot(page)


def test_a_role_in_two_kits_is_switched_off_from_the_refusal(page: Page, server, repo, shot):
    for kit in ("kit-a", "kit-b"):
        folder = repo / ".lado" / "kits" / kit
        (folder / "agents").mkdir(parents=True)
        (folder / "kit.yaml").write_text(f"name: {kit}\nversion: 1.0.0\n")
        (folder / "agents" / "reviewer.md").write_text(
            f"---\nname: reviewer\ndescription: reviews for {kit}\n---\nReview.\n"
        )
    log_in(page, server)
    page.get_by_role("button", name="New session").click()
    dialog = page.get_by_role("dialog", name="New session")
    dialog.get_by_role("combobox", name=re.compile("Where")).fill(str(repo))
    expect(dialog).to_contain_text("✓ git repository · branch main")
    dialog.get_by_label("Provider").select_option("fake")
    dialog.get_by_label("Add kit").select_option("kit-a")
    dialog.get_by_label("Add kit").select_option("kit-b")
    dialog.get_by_role("button", name="Start session").click()
    expect(dialog.get_by_role("alert")).to_contain_text('agent "reviewer" is defined by two kits')
    dialog.get_by_role("button", name="Switch off reviewer of kit-b").click()
    expect(dialog.get_by_role("textbox", name=re.compile("Switch off"))).to_have_value(
        "agent:reviewer@kit-b"
    )
    expect(dialog.get_by_role("button", name="Switch off reviewer of kit-b")).to_be_disabled()
    dialog.get_by_role("button", name="Switch off reviewer of kit-a").scroll_into_view_if_needed()
    shot(page, "refused")

    dialog.get_by_role("button", name="Start session").click()
    expect(page).to_have_url(f"{server['url']}/sessions/my-repo/activity")
    assert state.get_session("my-repo").without == ["agent:reviewer@kit-b"]
    idle("my-repo")


def test_a_folder_that_will_not_do_shows_the_cores_reason(page: Page, server, tmp_path, shot):
    plain = tmp_path / "plain"
    plain.mkdir()
    log_in(page, server)
    page.get_by_role("button", name="New session").click()
    dialog = page.get_by_role("dialog", name="New session")
    dialog.get_by_role("combobox", name=re.compile("Where")).fill(str(plain))
    expect(dialog).to_contain_text(f"{plain} is not inside a git repository")
    expect(dialog.get_by_role("button", name="Start session")).to_be_disabled()
    # The CLIs checked: each `--version` may take seconds on a loaded machine.
    expect(dialog.get_by_label("Provider")).to_be_enabled(timeout=30_000)
    shot(page)


def test_the_session_list_row_has_only_the_entrys_menu(page: Page, server, repo, shot):
    session = running_session(repo)
    log_in(page, server, f"/sessions/{session}")
    row = page.get_by_role("navigation", name="Sessions").get_by_role("listitem")
    row.hover()
    expect(row.get_by_role("button")).to_have_count(1)
    row.get_by_role("button", name=f"Actions for {session}").click()
    menu = page.get_by_role("menu", name=session)
    expect(menu.get_by_role("menuitem")).to_have_text(["Copy link", "Open in new tab"])
    expect(menu.get_by_role("menuitem", name="Open in new tab")).to_have_attribute(
        "href", f"/sessions/{session}"
    )
    shot(page, "menu")

    link = f"{server['url']}/sessions/{session}"
    page.context.grant_permissions(["clipboard-read", "clipboard-write"], origin=server["url"])
    menu.get_by_role("menuitem", name="Copy link").click()
    expect(row.get_by_role("status")).to_have_text("Link copied")
    expect(menu).to_have_count(0)
    assert page.evaluate("navigator.clipboard.readText()") == link
    shot(page, "copied")

    # Without the Clipboard API (http from another machine) the address is shown to copy by hand.
    page.evaluate("Object.defineProperty(navigator, 'clipboard', {value: undefined})")
    row.get_by_role("button", name=f"Actions for {session}").click()
    menu.get_by_role("menuitem", name="Copy link").click()
    by_hand = page.get_by_role("dialog", name=f"Link to {session}")
    expect(by_hand.get_by_role("textbox", name="Link")).to_have_value(link)
    expect(by_hand).to_contain_text("Press ⌘C / Ctrl+C to copy")
    shot(page)
    page.keyboard.press("Escape")
    expect(by_hand).to_have_count(0)


def test_stop_from_the_session_head(page: Page, server, repo, shot):
    session = running_session(repo)
    log_in(page, server, f"/sessions/{session}")
    head = page.get_by_role("banner").locator(".session-head")
    head.get_by_role("button", name="Stop session…").hover()
    expect(page.get_by_role("tooltip")).to_have_text("Stop session…")
    shot(page, "running")

    head.get_by_role("button", name="Stop session…").click()
    asked = page.get_by_role("dialog", name=f'Stop session "{session}"?')
    expect(asked).to_contain_text("its agent is closed")
    expect(asked).to_contain_text("you can resume it later")
    # Whole, not cut by the session's scrolling box: its left edge is its own.
    box = asked.bounding_box()
    edge = page.evaluate(
        "([x, y]) => document.elementFromPoint(x, y).closest('[role=dialog]')?.ariaLabel ?? null",
        [box["x"] + 4, box["y"] + box["height"] / 2],
    )
    assert edge == f'Stop session "{session}"?'
    shot(page, "asked")

    asked.get_by_role("button", name=f"Stop {session}").click()
    expect(head.get_by_role("button", name="Resume…")).to_be_visible()
    expect(head.get_by_role("button", name="Forget…")).to_be_visible()
    expect(head.get_by_role("button", name="Stop session…")).to_have_count(0)
    assert state.get_session(session).stopped_at
    shot(page)


def test_resume_a_stopped_session(page: Page, server, repo, shot):
    session = stopped_session(repo)
    log_in(page, server, f"/sessions/{session}")
    page.get_by_role("button", name="Resume…").click()
    dialog = page.get_by_role("dialog", name="Resume session")
    expect(dialog.get_by_role("combobox", name=re.compile("Where"))).to_have_value(str(repo))
    expect(dialog.get_by_role("combobox", name=re.compile("Where"))).to_be_disabled()
    expect(dialog.get_by_label("Provider")).to_have_value("fake", timeout=30_000)  # CLIs checked
    shot(page, "window")

    dialog.get_by_role("button", name="Resume session").click()
    expect(dialog).to_have_count(0)
    idle(session)
    head = page.get_by_role("banner").locator(".session-head")
    expect(head.get_by_role("button", name="Resume…")).to_have_count(0)
    assert state.get_session(session).stopped_at is None
    shot(page)


def test_forget_a_stopped_session(page: Page, server, repo, shot):
    session = stopped_session(repo)
    log_in(page, server, f"/sessions/{session}")
    # The name stays on one line beside the status and the icons, its whole text in a tooltip.
    head = page.get_by_role("banner").locator(".session-head")
    name = head.locator("h1")
    expect(name).to_have_attribute("title", session)
    assert name.bounding_box()["height"] < 36
    expect(head.get_by_role("button", name="Session actions")).to_have_count(0)
    head.get_by_role("button", name="Forget…").focus()
    expect(page.get_by_role("tooltip")).to_have_text("Forget…")
    shot(page, "stopped")
    head.get_by_role("button", name="Forget…").click()
    asked = page.get_by_role("dialog", name=f'Forget session "{session}"?')
    expect(asked).to_contain_text("This cannot be undone.")
    forget = asked.get_by_role("button", name=f"Forget {session}")
    expect(forget).to_be_enabled()  # the preview came: no open runs to tick
    shot(page, "asked")

    forget.click()
    expect(page).to_have_url(f"{server['url']}/sessions")
    expect(page.get_by_role("navigation", name="Sessions").get_by_role("link")).to_have_count(0)
    assert state.get_session(session) is None
    shot(page)
