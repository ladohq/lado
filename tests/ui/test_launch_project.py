"""A new session in a project from the New session window, in a browser (openspec change
new-session-in-project; docs/design/ui.md, Launch and session control): Project chooses a
project and one of its repositories and starts there, a taken name is the core's refusal,
another project than the preselected one gets the session, Folder's refusal inside a
project leads to Project or to the project's page, the project's
page opens the window on it, an empty project leads to its page, and on a phone the switch
is a grid of two rows. The server is `lado` with the fake providers. Every wait is for a
state, never for time."""

import re
import subprocess

import agent_helpers
import fake_provider
import pytest
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


def new_session(page: Page):
    page.get_by_role("button", name="New session").click()
    return page.get_by_role("dialog", name="New session")


def to_project(dialog):
    dialog.get_by_role("button", name="Project", exact=True).click()
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
    expect(dialog.get_by_role("textbox", name="Name")).to_have_value("shop-frontend")
    expect(dialog).to_contain_text("✓ git repository · branch main")
    dialog.get_by_label("Provider").select_option("fake")
    shot(page, "window")
    page.emulate_media(color_scheme="dark")
    shot(page, "window-dark")
    page.emulate_media(color_scheme="light")

    dialog.get_by_role("button", name="Start in Shop").click()
    expect(page).to_have_url(f"{server['url']}/sessions/shop-frontend/activity")
    expect(dialog).to_have_count(0)
    idle("shop-frontend")
    facts = page.get_by_role("banner").locator(".session-meta > *")
    expect(facts.first).to_have_text("projectShop")
    expect(facts.nth(1)).to_have_text(str(shop / "frontend"))
    shot(page, "started")


def test_another_project_than_the_last_used_gets_the_session(page: Page, shop, server, shot):
    agent_helpers.init_repo(projects.folder("acme") / "crm")
    runtime.start_session(None, None, None, "fake", project="shop", repo_name="frontend")
    idle("shop-frontend")
    runtime.stop_session("shop-frontend")
    page.set_viewport_size({"width": 1440, "height": 900})
    log_in(page, server)
    dialog = new_session(page)
    to_project(dialog)
    project = dialog.get_by_role("combobox", name="Project")
    expect(project).to_have_value("shop")  # the last used, preselected
    expect(dialog.get_by_role("button", name="Start in Shop")).to_be_visible()
    project.select_option("acme")
    expect(repo(dialog, "crm")).to_have_attribute("aria-checked", "true")
    expect(dialog.get_by_role("textbox", name="Name")).to_have_value("acme-crm")
    dialog.get_by_label("Provider").select_option("fake")
    start = dialog.get_by_role("button", name="Start in ACME CRM")
    expect(start).to_be_enabled()
    shot(page, "chosen")
    start.click()
    expect(page).to_have_url(f"{server['url']}/sessions/acme-crm/activity")
    idle("acme-crm")
    facts = page.get_by_role("banner").locator(".session-meta > *")
    expect(facts.first).to_have_text("projectACME CRM")
    assert state.get_session("acme-crm").project == "acme"
    listed = subprocess.run(
        fake_provider.lado_command("ls"), capture_output=True, text=True, timeout=60
    )
    assert listed.returncode == 0, listed.stderr
    row = next(line for line in listed.stdout.splitlines() if "acme-crm" in line)
    assert "project acme" in row, listed.stdout
    assert state.get_session("shop-frontend").stopped_at is not None  # not the preselected


def test_the_last_repository_is_chosen_and_a_taken_name_is_refused(page: Page, shop, server, shot):
    runtime.start_session(None, None, None, "fake", project="shop", repo_name="frontend")
    idle("shop-frontend")
    runtime.stop_session("shop-frontend")
    page.set_viewport_size({"width": 1440, "height": 900})
    log_in(page, server)
    dialog = new_session(page)
    to_project(dialog)
    expect(dialog.get_by_role("combobox", name="Project")).to_have_value("shop")
    expect(repo(dialog, "frontend")).to_have_attribute("aria-checked", "true")
    expect(dialog).to_contain_text("a stopped session shop-frontend exists for this folder")
    expect(dialog.get_by_label("Provider")).to_have_value("fake")  # its last session's
    dialog.get_by_role("button", name="Start in Shop").click()
    alert = dialog.get_by_role("alert")
    expect(alert).to_have_text(
        f'session "shop-frontend" exists already (stopped, in {shop / "frontend"}); resume it, '
        "or give the new session another name"
    )
    expect(
        dialog.locator(".launch-refused").get_by_role("button", name="Resume it")
    ).to_be_visible()
    shot(page, "taken")


def test_folders_refusal_inside_a_project_leads_to_the_project(page: Page, shop, server, shot):
    page.set_viewport_size({"width": 1440, "height": 900})
    log_in(page, server)
    dialog = new_session(page)
    dialog.get_by_role("button", name="Folder", exact=True).click()  # no sessions: From scratch
    where = dialog.get_by_role("combobox", name=re.compile("Where"))
    where.fill(str(shop / "backend"))
    refusal = dialog.locator(".field-note.bad")
    expect(refusal.locator("code")).to_have_text("lado start --project shop --repo backend")
    where.blur()
    shot(page, "refused")
    refusal.get_by_role("button", name="Start in the project Shop").click()
    expect(dialog.get_by_role("button", name="Project", exact=True)).to_have_attribute(
        "aria-pressed", "true"
    )
    expect(dialog.get_by_role("combobox", name="Project")).to_have_value("shop")
    expect(repo(dialog, "backend")).to_have_attribute("aria-checked", "true")
    expect(dialog.get_by_role("textbox", name="Name")).to_have_value("shop-backend")

    # A folder of the project that is no repository: its page.
    (shop / "notes").mkdir()
    dialog.get_by_role("button", name="Folder", exact=True).click()
    where.fill(str(shop / "notes"))
    dialog.get_by_role("button", name="Open the project Shop").click()
    expect(page).to_have_url(f"{server['url']}/projects/shop")
    expect(dialog).to_have_count(0)


def test_the_projects_page_opens_the_window_on_it(page: Page, shop, server, shot):
    page.set_viewport_size({"width": 1440, "height": 900})
    log_in(page, server)
    page.goto(f"{server['url']}/projects/shop")
    view = page.get_by_role("region", name="Project shop", exact=True)
    shot(page, "page")
    view.get_by_role("button", name="New session…").click()
    dialog = page.get_by_role("dialog", name="New session")
    expect(dialog.get_by_role("button", name="Project", exact=True)).to_have_attribute(
        "aria-pressed", "true"
    )
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


def test_on_a_phone_the_switch_is_two_rows_in_the_window(page: Page, shop, server, shot):
    page.set_viewport_size({"width": 390, "height": 844})
    log_in(page, server)
    dialog = new_session(page)
    to_project(dialog)
    dialog.get_by_role("combobox", name="Project").select_option("shop")
    expect(repo(dialog, "backend")).to_be_visible()
    window = dialog.bounding_box()
    boxes = [
        dialog.get_by_role("group", name="Source")
        .get_by_role("button", name=name, exact=True)
        .bounding_box()
        for name in ("From scratch", "Folder", "Clone from URL", "Project")
    ]
    rows = sorted({round(box["y"]) for box in boxes})
    assert len(rows) == 2, boxes
    assert [round(box["y"]) for box in boxes] == [rows[0], rows[0], rows[1], rows[1]]
    for box in boxes:
        assert window["x"] <= box["x"] and box["x"] + box["width"] <= window["x"] + window["width"]
    no_sideways_scroll(page)
    shot(page, "phone", full_page=False)
    page.emulate_media(color_scheme="dark")
    dialog.get_by_role("combobox", name="Project").select_option("acme")
    expect(dialog).to_contain_text("No repositories yet.")
    shot(page, "phone-empty-dark", full_page=False)
