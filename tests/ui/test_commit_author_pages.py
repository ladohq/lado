"""Commit authors in a browser (openspec change commit-author-levels; docs/design/ui.md, Git
servers, Projects, Launch and session control): on a LADO and a git that know nobody, New
session → New empty folder shows the note of a missing author, its link opens Settings → Git
servers in a new tab with LADO's author form open, the author saved there reaches the window
when it gets the focus back, and the repository's first commit carries it; a project's author
set, removed and put back on its page; the pages at a phone's width without a sideways scroll.
The server is `lado` with the fake providers; screenshots of each changed screen."""

import subprocess

import pytest
from launch_window import agent, new_session
from playwright.sync_api import Browser, expect
from test_launch import idle, log_in
from test_phone import no_sideways_scroll

from lado import projects as lado_projects
from lado import state

pytestmark = pytest.mark.ui

ANN = "Ann Lee <ann@example.com>"


@pytest.fixture
def nobody(tmp_path, monkeypatch, git_config):
    """A workspace (LADO_REPOS) and a git that knows no author, both taken before `server`,
    so the server's process has them; the workspace."""
    git_config.write_text("")
    folder = tmp_path / "ws"
    folder.mkdir()
    monkeypatch.setenv("LADO_REPOS", str(folder))
    return folder


def test_a_fresh_start_on_a_clean_lado_without_a_terminal(browser: Browser, nobody, server, shot):
    context = browser.new_context(viewport={"width": 1440, "height": 900})
    try:
        page = context.new_page()
        log_in(page, server)
        dialog = new_session(page)
        expect(dialog.get_by_role("combobox", name="Where")).to_have_value("New empty folder")
        dialog.get_by_role("textbox", name="Folder name").fill("coffee-site")
        expect(dialog).to_contain_text(
            "Agents need a name and email to sign their commits, and none is set yet."
        )
        agent(dialog).select_option("fake")
        create = dialog.get_by_role("button", name="Create and start")
        expect(create).to_be_disabled()
        expect(dialog.locator(".launch-missing")).to_contain_text("set the commit author")
        expect(dialog.get_by_role("textbox", name="Email")).to_have_count(0)
        shot(page, "nobody")

        link = dialog.get_by_role(
            "link", name="Set the commit author in Settings (opens a new tab)"
        )
        with context.expect_page() as opened:
            link.click()
        settings = opened.value
        name = settings.get_by_role("textbox", name="Name")
        expect(name).to_be_focused()
        expect(settings).to_have_url(f"{server['url']}/settings/git-servers")
        shot(settings, "settings-form")
        name.fill("Ann Lee")
        settings.get_by_role("textbox", name="Email").fill("ann@example.com")
        settings.get_by_role("button", name="Save author").click()
        expect(settings.locator(".gx-result")).to_have_text(
            "Author saved. Go back to the New session tab: it checks again by itself."
        )
        expect(settings.get_by_role("button", name="Edit LADO's author")).to_be_focused()
        assert state.commit_author() == state.Author("Ann Lee", "ann@example.com")
        shot(settings, "settings-saved")

        page.bring_to_front()
        page.evaluate("window.dispatchEvent(new Event('focus'))")  # the tab got the focus back
        expect(dialog).to_contain_text(f"✓ Agents commit as {ANN}.")
        expect(dialog).not_to_contain_text("Agents need a name and email")
        expect(dialog.get_by_role("textbox", name="Task")).to_be_focused()
        expect(create).to_be_enabled()
        shot(page, "known")
        create.click()
        expect(page).to_have_url(f"{server['url']}/sessions/coffee-site/activity")
        idle("coffee-site")
        log = subprocess.run(
            ["git", "-C", str(nobody / "coffee-site"), "log", "-1", "--format=%an <%ae>|%cn <%ce>"],
            capture_output=True,
            text=True,
            check=True,
        )
        assert log.stdout.strip() == f"{ANN}|{ANN}"
    finally:
        context.close()


def test_the_settings_block_and_a_servers_minor_line(browser: Browser, nobody, server, shot):
    from lado import git_kinds, git_servers

    checked = git_servers.Checked(git_kinds.by_name("gitlab"), "ivan")
    git_servers.save(git_servers.address("https://gitlab.example.com"), checked, "glpat-x")
    context = browser.new_context(viewport={"width": 1440, "height": 900})
    try:
        page = context.new_page()
        log_in(page, server, "/settings/git-servers")
        block = page.locator(".mx-block").first
        expect(block).to_contain_text("⚠ Nobody: agents cannot commit")
        page.get_by_role("button", name="https://gitlab.example.com").click()
        minor = page.locator(".gx-minor .gx-val")
        expect(minor).to_have_text("Commit author: none yet · Set one for this server")
        shot(page, "nobody")
        page.get_by_role("button", name="Set LADO's author").click()
        page.get_by_role("textbox", name="Name").fill("Ann Lee")
        page.get_by_role("textbox", name="Email").fill("ann")
        page.get_by_role("button", name="Save author").click()
        expect(page.get_by_role("alert")).to_contain_text("not an email address: name@host")
        page.get_by_role("textbox", name="Email").fill("ann@example.com")
        page.get_by_role("button", name="Save author").click()
        expect(minor).to_have_text(f"Commit author: {ANN} (LADO's) · Set one for this server")
        shot(page, "set")
        page.get_by_role("button", name="Remove LADO's author").click()
        undo = page.get_by_role("button", name="Undo the removal of LADO's author")
        expect(undo).to_be_focused()
        expect(block).to_contain_text("⚠ Nobody: agents cannot commit")
        shot(page, "removed")
        undo.click()
        expect(block).to_contain_text(ANN)
    finally:
        context.close()
    phone = browser.new_context(viewport={"width": 390, "height": 844})
    try:
        page = phone.new_page()
        log_in(page, server, "/settings/git-servers")
        page.get_by_role("button", name="https://gitlab.example.com").click()
        expect(page.locator(".gx-minor .gx-val")).to_contain_text("(LADO's)")
        no_sideways_scroll(page)
        shot(page, "phone")
    finally:
        phone.close()


def test_a_projects_author_on_its_page(browser: Browser, nobody, server, shot):
    lado_projects.create("shop", "Coffee shop")
    subprocess.run(["git", "init", "-q", str(lado_projects.folder("shop") / "site")], check=True)
    state.set_commit_author("Ann Lee", "ann@example.com")
    context = browser.new_context(viewport={"width": 1440, "height": 900})
    try:
        page = context.new_page()
        log_in(page, server, "/projects/shop")
        view = page.get_by_role("region", name="Project shop", exact=True)
        line = view.locator(".pa-line")
        expect(line).to_have_text(f"Commit author {ANN} (LADO's) · Set one for this project")
        shot(page, "lados")
        view.get_by_role("button", name="Set a commit author for Coffee shop").click()
        view.get_by_role("textbox", name="Name").fill("Coffee Team")
        view.get_by_role("textbox", name="Email").fill("team@example.com")
        shot(page, "form")
        view.get_by_role("button", name="Save author").click()
        expect(line).to_have_text(
            "Commit author Coffee Team <team@example.com> (this project's, in every repository)"
        )
        expect(
            view.get_by_role("button", name="Edit the commit author of Coffee shop")
        ).to_be_focused()
        assert state.get_project("shop").author_email == "team@example.com"
        shot(page, "set")
        view.get_by_role("button", name="Remove the commit author of Coffee shop").click()
        undo = view.get_by_role(
            "button", name="Undo the removal of the commit author of Coffee shop"
        )
        expect(undo).to_be_focused()
        expect(line).to_contain_text("(LADO's)")
        shot(page, "removed")
        undo.click()
        expect(line).to_contain_text("Coffee Team <team@example.com>")
    finally:
        context.close()
    phone = browser.new_context(viewport={"width": 390, "height": 844})
    try:
        page = phone.new_page()
        log_in(page, server, "/projects/shop")
        view = page.get_by_role("region", name="Project shop", exact=True)
        expect(view.locator(".pa-line")).to_contain_text("Coffee Team <team@example.com>")
        no_sideways_scroll(page)
        shot(page, "phone")
    finally:
        phone.close()
