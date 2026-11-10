"""A new session in a project from the New session window, in a browser (openspec changes
new-session-in-project, new-session-window; docs/design/ui.md, Launch and session control):
Project… chooses a project and one of its repositories and starts there, another project
than the preselected one gets the session, the last repository comes back as a recent place
with a stopped session offered beside a new one, Folder's refusal inside a project leads to
the project or to its page, the project's page opens the window on it, an empty project
leads to its page, and on a phone the Project way fits the sheet. The server is `lado` with
the fake providers. Every wait is for a state, never for time."""

import re
import subprocess

import agent_helpers
import fake_provider
import pytest
from launch_window import agent, name_field, new_session, other_folder, pick_place
from playwright.sync_api import Page, expect
from test_launch import idle, log_in
from test_phone import no_sideways_scroll

from lado import projects, runtime, state

pytestmark = pytest.mark.ui


@pytest.fixture
def shop(tmp_path, monkeypatch, git_config):
    """LADO_REPOS=<tmp>/ws with the project shop titled Shop and its repositories backend and
    frontend, and the project acme titled ACME CRM without any; a test takes it before
    `server`, so the server's process has it. The folder of shop."""
    monkeypatch.setenv("LADO_REPOS", str(tmp_path / "ws"))
    projects.create("shop", "Shop")
    agent_helpers.init_repo(projects.folder("shop") / "backend")
    agent_helpers.init_repo(projects.folder("shop") / "frontend")
    projects.create("acme", "ACME CRM")
    return projects.folder("shop")


def to_project(dialog):
    pick_place(dialog, "Project…")
    expect(dialog.get_by_role("combobox", name="Project")).to_be_visible()


def repo(dialog, name: str):
    return dialog.get_by_role("radiogroup", name="Repository").get_by_role(
        "radio", name=re.compile(f"^{name}")
    )


def test_a_session_starts_in_a_projects_repository(page: Page, shop, server, shot):
    page.set_viewport_size({"width": 1440, "height": 900})
    log_in(page, server)
    dialog = new_session(page)
    to_project(dialog)
    project = dialog.get_by_role("combobox", name="Project")
    expect(project.locator("option")).to_have_text(["ACME CRM · acme", "Shop · shop"])
    project.select_option("shop")
    expect(dialog).to_contain_text("2 repositories · no sessions running · folder")
    expect(repo(dialog, "backend")).to_have_attribute("aria-checked", "true")  # the first
    repo(dialog, "frontend").click()
    expect(repo(dialog, "frontend")).to_have_attribute("aria-checked", "true")
    expect(name_field(dialog)).to_have_value("shop-frontend")
    expect(dialog).to_contain_text("✓ Ready · branch main")
    agent(dialog).select_option("fake")
    shot(page, "window")
    page.emulate_media(color_scheme="dark")
    shot(page, "window-dark")
    page.emulate_media(color_scheme="light")

    dialog.get_by_role("button", name="Start in Shop").click()
    expect(page).to_have_url(f"{server['url']}/sessions/shop-frontend/activity")
    expect(dialog).to_have_count(0)
    idle("shop-frontend")
    bar = page.get_by_role("banner")
    expect(bar.locator(".session-crumb")).to_have_text("Shop")
    bar.locator("h1 button").click()
    details = page.get_by_role("dialog", name="Session details")
    expect(details).to_contain_text(str(shop / "frontend"))
    shot(page, "started")


def test_another_project_than_the_last_used_gets_the_session(page: Page, shop, server, shot):
    agent_helpers.init_repo(projects.folder("acme") / "crm")
    runtime.start_session(None, None, None, "fake", project="shop", repo_name="frontend")
    idle("shop-frontend")
    runtime.stop_session("shop-frontend")
    page.set_viewport_size({"width": 1440, "height": 900})
    log_in(page, server)
    dialog = new_session(page)
    expect(dialog.get_by_role("combobox", name="Where")).to_have_value("frontend")  # the last
    expect(dialog.get_by_role("button", name="Start new session in Shop")).to_be_visible()
    to_project(dialog)
    project = dialog.get_by_role("combobox", name="Project")
    expect(project).to_have_value("shop")  # the last used, preselected
    project.select_option("acme")
    expect(repo(dialog, "crm")).to_have_attribute("aria-checked", "true")
    expect(name_field(dialog)).to_have_value("acme-crm")
    agent(dialog).select_option("fake")
    start = dialog.get_by_role("button", name="Start in ACME CRM")
    expect(start).to_be_enabled()
    shot(page, "chosen")
    start.click()
    expect(page).to_have_url(f"{server['url']}/sessions/acme-crm/activity")
    idle("acme-crm")
    expect(page.get_by_role("banner").locator(".session-crumb")).to_have_text("ACME CRM")
    assert state.get_session("acme-crm").project == "acme"
    listed = subprocess.run(
        fake_provider.lado_command("ls"), capture_output=True, text=True, timeout=60
    )
    assert listed.returncode == 0, listed.stderr
    row = next(line for line in listed.stdout.splitlines() if "acme-crm" in line)
    assert "project acme" in row, listed.stdout
    assert state.get_session("shop-frontend").stopped_at is not None  # not the preselected


def test_the_last_repository_comes_back_with_its_stopped_session_beside_a_new_one(
    page: Page, shop, server, shot
):
    runtime.start_session(None, None, None, "fake", project="shop", repo_name="frontend")
    idle("shop-frontend")
    runtime.stop_session("shop-frontend")
    page.set_viewport_size({"width": 1440, "height": 900})
    log_in(page, server)
    dialog = new_session(page)
    expect(dialog.get_by_role("combobox", name="Where")).to_have_value("frontend")
    expect(dialog.locator(".place-box .place-badge")).to_have_text("Project Shop")
    expect(dialog.locator(".place-line")).to_contain_text("Session shop-frontend stopped here")
    expect(agent(dialog)).to_have_value("fake")  # its last session's
    expect(name_field(dialog)).to_have_value("shop-frontend-2")
    start = dialog.get_by_role("button", name="Start new session in Shop")
    expect(start).to_have_class("primary")
    expect(start).to_be_enabled()
    expect(dialog.get_by_role("button", name="Resume shop-frontend")).to_have_count(0)
    shot(page, "taken")
    start.click()
    expect(page).to_have_url(f"{server['url']}/sessions/shop-frontend-2/activity")
    idle("shop-frontend-2")
    assert state.get_session("shop-frontend-2").project == "shop"


def test_folders_refusal_inside_a_project_leads_to_the_project(page: Page, shop, server, shot):
    page.set_viewport_size({"width": 1440, "height": 900})
    log_in(page, server)
    dialog, where = other_folder(page)
    where.fill(str(shop / "backend"))
    refusal = dialog.locator(".field-note.bad")
    expect(refusal.locator("code")).to_have_text("lado start --project shop --repo backend")
    where.blur()
    shot(page, "refused")
    refusal.get_by_role("button", name="Start in the project Shop").click()
    expect(dialog.get_by_role("combobox", name="Where")).to_have_value("backend")
    expect(dialog.locator(".place-box .place-badge")).to_have_text("Project Shop")
    expect(name_field(dialog)).to_have_value("shop-backend")

    # A folder of the project that is no repository: its page.
    (shop / "notes").mkdir()
    pick_place(dialog, "Other folder…")
    where.fill(str(shop / "notes"))
    dialog.get_by_role("button", name="Open the project Shop").click()
    expect(page).to_have_url(f"{server['url']}/projects/shop")
    expect(dialog).to_have_count(0)


def test_the_projects_page_opens_the_window_on_it(page: Page, shop, server, shot):
    page.set_viewport_size({"width": 1440, "height": 900})
    log_in(page, server)
    page.goto(f"{server['url']}/projects/shop")
    view = page.get_by_role("region", name="Project shop", exact=True)
    expect(view.get_by_role("button", name="Delete project…")).to_be_visible()
    shot(page, "page")
    view.get_by_role("button", name="New session…").click()
    dialog = page.get_by_role("dialog", name="New session")
    expect(dialog.get_by_role("combobox", name="Where")).to_have_value("Project")
    expect(dialog.get_by_role("combobox", name="Project")).to_have_value("shop")
    expect(repo(dialog, "backend")).to_have_attribute("aria-checked", "true")


def test_an_empty_project_leads_to_its_page(page: Page, shop, server, shot):
    page.set_viewport_size({"width": 1440, "height": 900})
    log_in(page, server)
    dialog = new_session(page)
    to_project(dialog)
    expect(dialog.get_by_role("combobox", name="Project")).to_have_value("acme")  # by title
    expect(dialog).to_contain_text("No repositories yet. Add one on the project's page:")
    expect(dialog.get_by_role("button", name="Start in ACME CRM")).to_be_disabled()
    shot(page, "empty")
    dialog.get_by_role("button", name="Open ACME CRM").click()
    expect(page).to_have_url(f"{server['url']}/projects/acme")
    expect(dialog).to_have_count(0)


def test_on_a_phone_the_project_way_fits_the_sheet(page: Page, shop, server, shot):
    page.set_viewport_size({"width": 390, "height": 844})
    log_in(page, server)
    dialog = new_session(page)
    where = dialog.get_by_role("combobox", name="Where")
    where.focus()
    where.press("ArrowDown")
    options = dialog.get_by_role("listbox", name="Places").get_by_role("option")
    for at in range(options.count()):
        assert options.nth(at).bounding_box()["height"] >= 44
    shot(page, "phone-list", full_page=False)
    dialog.get_by_role("listbox", name="Places").get_by_role("option", name="Project…").click()
    dialog.get_by_role("combobox", name="Project").select_option("shop")
    expect(repo(dialog, "backend")).to_be_visible()
    no_sideways_scroll(page)
    expect(dialog.locator(".launch-buttons .primary")).to_be_in_viewport(ratio=1)
    shot(page, "phone", full_page=False)
    page.emulate_media(color_scheme="dark")
    dialog.get_by_role("combobox", name="Project").select_option("acme")
    expect(dialog).to_contain_text("No repositories yet.")
    shot(page, "phone-empty-dark", full_page=False)
