"""Launch and session control in a browser: a session started from the New session window,
a refused folder, the session list row's menu, Stop from the session's head, Resume and
Forget, Forget stopped sessions from the Stopped band and Stop and forget. The server is
`lado` with the fake providers, so what it starts runs the fake agent."""

import re
import subprocess
import uuid

import agent_helpers
import pytest
from playwright.sync_api import Page, expect
from test_layout import BUILD

from lado import loop, runs, runtime, state

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


@pytest.fixture
def repos(tmp_path, monkeypatch):
    """A repositories folder of two repositories as LADO_REPOS; a test takes it before
    `server`, so the server's process has it."""
    folder = tmp_path / "repos"
    agent_helpers.init_repo(folder / "api")
    agent_helpers.init_repo(folder / "app")
    monkeypatch.setenv("LADO_REPOS", str(folder))
    return folder


def test_where_starts_in_the_repositories_folder(page: Page, repos, server, shot):
    log_in(page, server)
    page.get_by_role("navigation", name="Sections").get_by_role("button", name="Launch").click()
    dialog = page.get_by_role("dialog", name="New session")
    where = dialog.get_by_role("combobox", name=re.compile("Where"))
    expect(where).to_have_value("")
    expect(where).to_have_attribute("placeholder", f"{repos}/…")
    row = dialog.locator(".recent", has_text="Repositories folder:")
    expect(row.get_by_role("button", name=str(repos))).to_be_visible()
    where.blur()
    shot(page, "empty")
    where.focus()
    folders = dialog.get_by_role("listbox", name="Folders")
    expect(folders.get_by_role("option")).to_have_text(["api/", "app/"])
    shot(page, "list")
    folders.get_by_role("option", name="app/").click()
    expect(where).to_have_value(f"{repos}/app")
    expect(dialog).to_contain_text("✓ git repository · branch main")

    dialog.get_by_role("button", name="Clone from URL").click()
    url = dialog.get_by_role("textbox", name=re.compile("Where"))
    url.fill("https://example.invalid/acme/site.git")
    # Clone into follows /api/clone-target, which needs no network; the branch listing fails.
    expect(dialog.get_by_role("textbox", name="Clone into")).to_have_value(f"{repos}/site")
    shot(page, "clone")


OUTSIDE = "⚠ Outside the repositories folder ({}): this folder is only in the container"


def test_in_a_container_a_folder_outside_the_repositories_folder_is_warned_about(
    page: Page, repos, repo, server_in_container, shot
):
    server = server_in_container
    log_in(page, server)
    page.get_by_role("navigation", name="Sections").get_by_role("button", name="Launch").click()
    dialog = page.get_by_role("dialog", name="New session")
    where = dialog.get_by_role("combobox", name=re.compile("Where"))
    where.fill(f"{repos}/app")
    expect(dialog).to_contain_text("✓ git repository · branch main")
    expect(dialog.locator(".field-note.warn")).to_have_count(0)
    where.blur()
    shot(page, "inside")

    where.fill(str(repo))
    expect(dialog).to_contain_text("✓ git repository · branch main")
    expect(dialog.locator(".field-note.warn")).to_contain_text(OUTSIDE.format(repos))
    dialog.get_by_label("Provider").select_option("fake")
    expect(dialog.get_by_role("button", name="Start session")).to_be_enabled()
    where.blur()
    shot(page, "outside")

    dialog.get_by_role("button", name="Clone from URL").click()
    dialog.get_by_role("textbox", name=re.compile("Where")).fill(
        "https://example.invalid/a/site.git"
    )
    into = dialog.get_by_role("textbox", name="Clone into")
    expect(into).to_have_value(f"{repos}/site")
    expect(dialog.locator(".field-note.warn")).to_have_count(0)
    into.fill(str(repo.parent / "site"))
    expect(dialog.locator(".field-note.warn")).to_contain_text(OUTSIDE.format(repos))
    shot(page, "clone-outside")


@pytest.fixture
def server_in_container(monkeypatch, request):
    """The UI server as LADO's image runs it (LADO_CONTAINER), started after `repos`."""
    monkeypatch.setenv("LADO_CONTAINER", "1")
    return request.getfixturevalue("server")


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


def test_a_session_starts_with_a_first_message(page: Page, server, repo, shot):
    """The folded row above Advanced takes the human's first message; the session's chat
    shows it as the human's (openspec change first-message)."""
    log_in(page, server)
    page.get_by_role("navigation", name="Sections").get_by_role("button", name="Launch").click()
    dialog = page.get_by_role("dialog", name="New session")
    dialog.get_by_role("combobox", name=re.compile("Where")).fill(str(repo))
    expect(dialog).to_contain_text("✓ git repository · branch main")
    dialog.get_by_label("Provider").select_option("fake")
    field = dialog.get_by_role("textbox", name="First message")
    expect(field).to_be_hidden()  # folded when the window opens
    row = dialog.locator("details.launch-first > summary")
    expect(row).to_have_text("First message to the supervisor (optional)")
    row.click()
    field.fill("Take LAD-19 from the tracker.\nAsk me about the scope first.")
    shot(page, "window")
    row.click()
    expect(field).to_be_hidden()
    expect(dialog).to_contain_text("First message to the supervisor: Take LAD-19 from the tracker.")
    shot(page, "folded")

    dialog.get_by_role("button", name="Start session").click()
    expect(page).to_have_url(f"{server['url']}/sessions/my-repo/activity")
    chat = page.get_by_role("log", name="Chat with the session")
    mine = chat.get_by_role("article", name="Message from you")
    expect(mine).to_contain_text("Take LAD-19 from the tracker.")
    expect(mine).to_contain_text("Ask me about the scope first.")
    [message] = [m for m in state.list_messages("my-repo") if m.sender == state.HUMAN]
    assert message.summary == runtime.FIRST_MESSAGE
    agent_helpers.wait_for(
        lambda: state.get_message("my-repo", message.id).state == state.DELIVERED,
        "the first message delivered",
        "my-repo",
    )
    shot(page, "chat")


def test_a_role_in_two_kits_is_switched_off_from_the_refusal(page: Page, server, repo, shot):
    for kit in ("kit-a", "kit-b"):
        folder = repo.parent / "kits" / kit
        (folder / "agents").mkdir(parents=True)
        (folder / "kit.yaml").write_text(f"name: {kit}\nversion: 1.0.0\n")
        (folder / "agents" / "reviewer.md").write_text(
            f"---\nname: reviewer\ndescription: reviews for {kit}\n---\nReview.\n"
        )
        agent_helpers.install_kit(folder)
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


def test_a_folder_without_commits_shows_the_command_that_makes_one(
    page: Page, server, tmp_path, shot
):
    empty = tmp_path / "empty"
    subprocess.run(["git", "init", "-q", str(empty)], check=True)
    log_in(page, server)
    page.get_by_role("button", name="New session").click()
    dialog = page.get_by_role("dialog", name="New session")
    dialog.get_by_role("combobox", name=re.compile("Where")).fill(str(empty))
    expect(dialog).to_contain_text(f"{empty} has no commits yet")
    expect(dialog).to_contain_text("Make a first commit, in that folder:")
    command = "git add -A && git commit -m 'First commit'"
    expect(dialog.locator("code", has_text=command)).to_be_visible()
    expect(dialog.get_by_role("button", name="Copy command")).to_be_visible()
    expect(dialog.get_by_role("button", name="Start session")).to_be_disabled()
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
    expect(menu.get_by_role("menuitem")).to_have_text(["Rename…", "Copy link", "Open in new tab"])
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

    # Without the Clipboard API (http from another machine) the legacy copy copies it.
    page.evaluate("navigator.clipboard.writeText('stale')")
    page.evaluate(
        "Object.defineProperty(navigator, 'clipboard', {value: undefined, configurable: true})"
    )
    more = row.get_by_role("button", name=f"Actions for {session}")
    more.click()
    menu.get_by_role("menuitem", name="Copy link").click()
    expect(row.get_by_role("status")).to_have_text("Link copied")
    expect(page.get_by_role("dialog")).to_have_count(0)
    expect(more).to_be_focused()
    assert page.evaluate("document.querySelectorAll('body > textarea').length") == 0
    shot(page, "copied-without-api")
    page.evaluate("delete navigator.clipboard")  # the API again, to read what was copied
    assert page.evaluate("navigator.clipboard.readText()") == link

    # When no copy works the address is shown to copy by hand.
    page.evaluate(
        """() => {
          Object.defineProperty(navigator, 'clipboard', {value: undefined, configurable: true});
          document.execCommand = () => false;
        }"""
    )
    more.click()
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


def test_the_resume_notice_stands_above_the_tabs(page: Page, server, repo, shot):
    session = stopped_session(repo)
    log_in(page, server, f"/sessions/{session}")
    page.get_by_role("button", name="Resume…").click()
    dialog = page.get_by_role("dialog", name="Resume session")
    expect(dialog.get_by_label("Provider")).to_have_value("fake", timeout=30_000)  # CLIs checked
    dialog.get_by_label("Provider").select_option("fake-paste")
    dialog.get_by_role("button", name="Resume session").click()
    expect(dialog).to_have_count(0)
    idle(session)
    notice = page.locator(".started-notice")
    expect(notice.get_by_role("status")).to_contain_text("Resumed with new settings:")
    expect(notice).to_contain_text("fake-paste")

    def gaps() -> dict:
        return page.evaluate(
            """() => {
              const box = (selector) => document.querySelector(selector)?.getBoundingClientRect();
              const bar = box(".topbar").bottom;
              const notice = box(".started-notice");
              return {
                above: notice ? notice.top - bar : null,
                below: notice ? box(".session-tabs").top - notice.bottom : null,
                tabs: box(".session-tabs").top - bar,
              };
            }"""
        )

    # 12 px under the top bar, 10 px above the tabs.
    found = gaps()
    assert (found["above"], found["below"]) == (12, 10), found
    shot(page, "notice")

    notice.get_by_role("button", name="Close").click()
    expect(notice).to_have_count(0)
    assert gaps()["tabs"] == 0
    shot(page, "closed")


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


# Forget stopped sessions and Stop and forget (openspec change forget-stopped-sessions)


def stopped_band(page: Page):
    return (
        page.get_by_role("navigation", name="Sessions")
        .get_by_role("region", name="Stopped")
        .locator("h3")
    )


def test_forget_stopped_sessions(page: Page, server, repo, shot):
    page.set_viewport_size({"width": 1280, "height": 900})
    first, second, third = (stopped_session(repo) for _ in range(3))
    running = running_session(repo)
    log_in(page, server)
    sessions = page.get_by_role("navigation", name="Sessions")
    bin_ = stopped_band(page).get_by_role("button", name="Forget stopped sessions…")
    expect(bin_).to_be_visible()
    expect(
        sessions.get_by_role("region", name="Running").get_by_role(
            "button", name="Forget stopped sessions…"
        )
    ).to_have_count(0)
    bin_.hover()
    expect(page.get_by_role("tooltip")).to_have_text("Forget stopped sessions…")
    shot(page, "band")

    bin_.click()
    asked = page.get_by_role("dialog", name="Forget stopped sessions?")
    expect(asked.get_by_role("listitem")).to_have_count(3)
    expect(asked.get_by_role("checkbox", name="All 3")).to_be_checked()
    forget = asked.get_by_role("button", name="Forget 3 sessions")
    expect(forget).to_be_enabled()  # the previews came: no open runs
    expect(asked.get_by_role("button", name="Cancel")).to_be_focused()
    asked.get_by_role("checkbox", name=re.compile(f"^{third}")).uncheck()
    forget = asked.get_by_role("button", name="Forget 2 sessions")
    shot(page, "window")

    forget.click()
    expect(asked).to_have_count(0)
    for gone in (first, second):
        expect(sessions.get_by_role("link", name=gone)).to_have_count(0)
        assert state.get_session(gone) is None
    assert state.get_session(third) is not None
    assert state.get_session(running) is not None
    expect(stopped_band(page).get_by_role("button", name="Stopped 1")).to_be_visible()
    shot(page)


def stopped_with_an_open_run(repo) -> str:
    """A stopped session of the fake agent whose run build/x is still open."""
    kit = repo.parent / "kits" / "uibuild"
    (kit / "flows").mkdir(parents=True, exist_ok=True)
    (kit / "kit.yaml").write_text("name: uibuild\nversion: 1.0.0\n")
    (kit / "flows" / "build.yaml").write_text(BUILD)
    agent_helpers.install_kit(kit)
    session = f"ui-{uuid.uuid4().hex[:6]}"
    runtime.start_session(str(repo), session, None, "fake", ["default", "uibuild"])
    idle(session)
    runs.start(session, "build", "Add a login page", name="x")
    runtime.stop_session(session)
    return session


def test_forget_stopped_sessions_open_runs(page: Page, server, repo, shot):
    page.set_viewport_size({"width": 1280, "height": 900})
    plain = stopped_session(repo)
    busy = stopped_with_an_open_run(repo)
    log_in(page, server)
    stopped_band(page).get_by_role("button", name="Forget stopped sessions…").click()
    asked = page.get_by_role("dialog", name="Forget stopped sessions?")
    expect(asked).to_contain_text("1 open run")
    switch = asked.get_by_role("checkbox", name=f"Also forget their 1 open run ({busy})")
    expect(switch).not_to_be_checked()
    expect(asked).to_contain_text(f"While this is off, {busy} stays.")
    shot(page, "switch-off")
    asked.get_by_role("button", name="Forget 1 session").click()
    expect(asked).to_have_count(0)
    assert state.get_session(plain) is None
    assert state.get_session(busy) is not None  # its open run kept it

    stopped_band(page).get_by_role("button", name="Forget stopped sessions…").click()
    asked.get_by_role("checkbox", name=f"Also forget their 1 open run ({busy})").check()
    asked.get_by_role("button", name="Forget 1 session").click()
    expect(asked).to_have_count(0)
    assert state.get_session(busy) is None


def test_stop_and_forget(page: Page, server, repo, shot):
    session = running_session(repo)
    log_in(page, server, f"/sessions/{session}")
    page.get_by_role("banner").locator(".session-head").get_by_role(
        "button", name="Stop session…"
    ).click()
    asked = page.get_by_role("dialog", name=f'Stop session "{session}"?')
    expect(asked).to_contain_text("its agent is closed")
    both = asked.get_by_role("button", name="Stop and forget")
    expect(both).to_be_enabled()
    both.hover()
    expect(page.get_by_role("tooltip")).to_have_text("Stops it, then deletes its history for good")
    shot(page, "asked")

    both.click()
    expect(page).to_have_url(f"{server['url']}/sessions")
    expect(page.get_by_role("navigation", name="Sessions").get_by_role("link")).to_have_count(0)
    assert state.get_session(session) is None
    shot(page)


# Clone from URL (openspec change clone-from-url)


def clone_window(page: Page, server, url: str, into) -> object:
    log_in(page, server)
    page.get_by_role("button", name="New session").click()
    dialog = page.get_by_role("dialog", name="New session")
    dialog.get_by_role("button", name="Clone from URL").click()
    dialog.get_by_role("textbox", name=re.compile("Where")).fill(url)
    dialog.get_by_role("textbox", name="Clone into").fill(str(into))
    expect(dialog).to_contain_text("✓ repository found · 3 branches")
    return dialog


def test_a_session_starts_in_a_clone_of_a_url(page: Page, server, tmp_path, shot):
    url = agent_helpers.bare_remote(tmp_path)
    into = tmp_path / "work" / "app"
    dialog = clone_window(page, server, url, into)
    expect(dialog).to_contain_text("✓ a new folder")
    expect(dialog.get_by_label("Branch")).to_have_value("main")
    dialog.get_by_label("Branch").select_option("develop")
    dialog.get_by_label("Provider").select_option("fake")
    expect(dialog.get_by_role("textbox", name="Name")).to_have_value("app")
    shot(page, "form")

    dialog.get_by_role("button", name="Clone and start").click()
    expect(page).to_have_url(f"{server['url']}/sessions/app/activity", timeout=30_000)
    idle("app")
    assert runtime.branch(str(into)) == "develop"
    assert state.get_session("app").repo == str(into.resolve())


@pytest.fixture
def slow_clone(tmp_path, monkeypatch):
    """A remote's URL, and a git whose clone prints progress and then waits, on the
    server's PATH (before the server starts); ls-remote is the real git's."""
    url = agent_helpers.bare_remote(tmp_path)  # by the real git
    for key, value in agent_helpers.fake_git(tmp_path / "fake", "slow-clone").items():
        monkeypatch.setenv(key, value)
    return url


def test_a_clone_shows_its_progress_and_cancel_clone_stops_it(
    page: Page, slow_clone, server, tmp_path, shot
):
    into = tmp_path / "work" / "app"
    dialog = clone_window(page, server, slow_clone, into)
    dialog.get_by_label("Provider").select_option("fake")
    dialog.get_by_role("button", name="Clone and start").click()
    expect(dialog.get_by_role("progressbar", name="Clone")).to_be_visible()
    expect(dialog).to_contain_text("Receiving objects")
    expect(dialog.get_by_role("button", name="Close")).to_be_disabled()
    page.keyboard.press("Escape")
    expect(dialog).to_be_visible()
    shot(page, "progress")

    dialog.get_by_role("button", name="Cancel clone").click()
    expect(dialog).to_contain_text("the clone was cancelled", timeout=15_000)
    expect(dialog.get_by_role("button", name="Clone and start")).to_be_enabled()
    assert not into.exists()
    assert [p.name for p in into.parent.iterdir() if ".clone-" in p.name] == []


def test_a_clone_there_already_is_used_as_it_is(page: Page, server, tmp_path, shot):
    url = agent_helpers.bare_remote(tmp_path)
    into = tmp_path / "app"
    subprocess.run(["git", "clone", "-q", url, str(into)], check=True)
    dialog = clone_window(page, server, url, into)
    expect(dialog).to_contain_text("is already a clone of this repository")
    expect(dialog).to_contain_text("LADO will use it as it is: no clone, no pull, no branch switch")
    shot(page, "use-this-clone")

    dialog.get_by_role("button", name="Use this clone").click()
    expect(dialog.get_by_role("button", name="Folder")).to_have_attribute("aria-pressed", "true")
    expect(dialog.get_by_role("combobox", name=re.compile("Where"))).to_have_value(str(into))
    expect(dialog).to_contain_text("✓ git repository · branch main")


def test_a_page_reloaded_during_a_clone_cancels_it_at_once(
    page: Page, slow_clone, server, tmp_path, shot
):
    into = tmp_path / "work" / "app"
    dialog = clone_window(page, server, slow_clone, into)
    dialog.get_by_label("Provider").select_option("fake")
    dialog.get_by_role("button", name="Clone and start").click()
    expect(dialog).to_contain_text("Receiving objects")
    [call] = agent_helpers.fake_git_calls(tmp_path / "fake")
    page.reload()  # pagehide: the window's beacon, long before clone.ABANDONED

    def ended():
        temps = [p for p in into.parent.iterdir() if ".clone-" in p.name]
        return not temps and agent_helpers.gone(call["pid"]) and agent_helpers.gone(call["child"])

    agent_helpers.wait_for(ended, "the clone cancelled by the beacon", "none", timeout=15)
    assert not into.exists()
