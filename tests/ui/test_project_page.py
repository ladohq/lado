"""The project's page in a browser (openspec change project-page; docs/design/ui.md,
Projects): its repositories with Start session and Delete, Add repository by a clone (with
progress and Cancel clone) or from scratch, Delete repository after its preview, the
project's sessions from the feed, Rename in place, Delete project (openspec change
project-delete), and the leftovers of earlier steps: New
project's title without an id, a narrow window, New session for a project that is gone, and
Clone into a project's folder. The server is `lado` with the fake providers. Every wait is
for a state, never for time."""

import re
import subprocess

import agent_helpers
import pytest
from playwright.sync_api import Browser, Page, expect
from test_launch import idle, log_in
from test_phone import UPRIGHT, no_sideways_scroll

from lado import loop, project_secrets, projects, runtime, state

pytestmark = pytest.mark.ui

CLONE = 30_000  # ms a clone of a local bare repository may take on a loaded machine


@pytest.fixture
def shop(tmp_path, monkeypatch, git_config):
    """LADO_REPOS=<tmp>/ws with the project shop titled Shop: frontend, a clone of a bare
    remote (pushed, clean), and backend, a repository whose main is on no remote; and the
    project acme titled ACME CRM with none. A test takes it before `server`. The folder of
    shop."""
    monkeypatch.setenv("LADO_REPOS", str(tmp_path / "ws"))
    projects.create("shop", "Shop")
    folder = projects.folder("shop")
    url = agent_helpers.bare_remote(tmp_path / "remote")
    subprocess.run(["git", "clone", "-q", url, str(folder / "frontend")], check=True)
    agent_helpers.init_repo(folder / "backend")
    projects.create("acme", "ACME CRM")
    return folder


def project_page(page: Page, server, id: str = "shop"):
    page.set_viewport_size({"width": 1440, "height": 900})
    log_in(page, server, f"/projects/{id}")
    return page.get_by_role("region", name=f"Project {id}", exact=True)


def block(view, name: str):
    return view.get_by_role("region", name=name, exact=True)


def row(view, name: str):
    return (
        block(view, "Repositories")
        .get_by_role("row")
        .filter(has=view.page.locator(".repo-name", has_text=re.compile(f"^{name}$")))
    )


def add_dialog(view):
    block(view, "Repositories").get_by_role("button", name="+ Add repository").click()
    return view.page.get_by_role("dialog", name="Add a repository to Shop")


def test_the_repositories_and_one_added_from_scratch(page: Page, shop, server, shot):
    view = project_page(page, server)
    expect(row(view, "backend")).to_contain_text("branch main · no remote")
    expect(row(view, "frontend")).to_contain_text("branch main ·")
    expect(row(view, "frontend").locator("code")).to_be_visible()  # its remote
    for name in ("backend", "frontend"):
        expect(row(view, name).get_by_role("button", name="Start session")).to_be_visible()
        expect(row(view, name).get_by_role("button", name="Delete")).to_be_visible()
    shot(page, "page")
    page.emulate_media(color_scheme="dark")
    shot(page, "page-dark")
    page.emulate_media(color_scheme="light")

    dialog = add_dialog(view)
    dialog.get_by_role("button", name="From scratch").click()
    name = dialog.get_by_role("textbox", name="Name")
    name.fill("frontend")
    dialog.get_by_role("button", name="Create").click()
    expect(dialog.get_by_role("alert")).to_contain_text("already exists in project shop")
    shot(page, "scratch-refused")
    name.fill("web")
    expect(dialog).to_contain_text(f"Its folder: {shop / 'web'}")
    dialog.get_by_role("button", name="Create").click()
    expect(dialog).to_have_count(0)
    expect(row(view, "web")).to_contain_text("branch main · no remote")
    commits = subprocess.run(
        ["git", "-C", str(shop / "web"), "rev-list", "--count", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert commits.stdout.strip() == "1"


def test_a_repository_added_by_a_clone(page: Page, shop, server, tmp_path, shot):
    url = agent_helpers.bare_remote(tmp_path / "admin-remote")
    view = project_page(page, server)
    dialog = add_dialog(view)
    expect(dialog.get_by_role("button", name="Clone from URL")).to_have_attribute(
        "aria-pressed", "true"
    )
    dialog.get_by_role("textbox", name="Git URL").fill(url)
    expect(dialog).to_contain_text("✓ repository found · 3 branches")
    expect(dialog.get_by_role("textbox", name="Name")).to_have_value("app")  # the URL's name
    expect(dialog.get_by_label("Branch")).to_have_value("main")
    dialog.get_by_label("Branch").select_option("develop")
    shot(page, "clone")
    dialog.get_by_role("button", name="Clone", exact=True).click()
    expect(dialog).to_have_count(0, timeout=CLONE)
    expect(row(view, "app")).to_contain_text("branch develop")
    assert runtime.branch(str(shop / "app")) == "develop"


def test_cancel_clone_leaves_no_folder(page: Page, shop, slow_clone, server, shot):
    view = project_page(page, server)
    dialog = add_dialog(view)
    dialog.get_by_role("textbox", name="Git URL").fill(slow_clone)
    expect(dialog.get_by_role("textbox", name="Name")).to_have_value("app")
    dialog.get_by_role("button", name="Clone", exact=True).click()
    expect(dialog.get_by_role("progressbar", name="Clone")).to_be_visible()
    expect(dialog).to_contain_text("Receiving objects")
    expect(dialog.get_by_role("textbox", name="Name")).to_be_disabled()
    expect(dialog.get_by_role("button", name="Cancel", exact=True)).to_have_count(0)
    page.keyboard.press("Escape")
    expect(dialog).to_be_visible()
    shot(page, "progress")

    dialog.get_by_role("button", name="Cancel clone").click()
    expect(dialog).to_contain_text("the clone was cancelled", timeout=15_000)
    expect(dialog.get_by_role("textbox", name="Name")).to_be_enabled()
    assert not (shop / "app").exists()
    assert [p.name for p in shop.iterdir() if ".clone-" in p.name] == []
    shot(page, "cancelled")


def test_start_session_and_the_sessions_block(page: Page, shop, server, shot):
    view = project_page(page, server)
    sessions = block(view, "Sessions")
    expect(sessions).to_contain_text("No sessions in this project yet.")
    row(view, "frontend").get_by_role("button", name="Start session").click()
    dialog = page.get_by_role("dialog", name="New session")
    expect(dialog.get_by_role("combobox", name="Project")).to_have_value("shop")
    frontend = dialog.get_by_role("radiogroup", name="Repository").get_by_role(
        "radio", name=re.compile("^frontend")
    )
    expect(frontend).to_have_attribute("aria-checked", "true")
    dialog.get_by_label("Provider").select_option("fake")
    dialog.get_by_role("button", name="Start in Shop").click()
    expect(page).to_have_url(f"{server['url']}/sessions/shop-frontend/activity")
    idle("shop-frontend")
    assert state.get_session("shop-frontend").project == "shop"

    page.goto(f"{server['url']}/projects/shop")
    link = sessions.get_by_role("link", name="shop-frontend")
    expect(link).to_have_attribute("href", "/sessions/shop-frontend")
    item = sessions.get_by_role("listitem").filter(
        has=page.get_by_role("link", name="shop-frontend")
    )
    expect(item).to_contain_text("frontend")
    expect(item).to_contain_text("running")
    shot(page, "sessions")
    runtime.stop_session("shop-frontend")
    expect(item).to_contain_text(re.compile(r"stopped .+ ago"))  # the feed, no reload


def test_delete_a_repository_with_work_not_on_the_remote(page: Page, shop, server, shot):
    view = project_page(page, server)
    row(view, "backend").get_by_role("button", name="Delete").click()
    dialog = page.get_by_role("dialog", name="Delete repository backend?")
    expect(dialog).to_contain_text("Work that is not on the remote")
    expect(dialog).to_contain_text("backend: branch main not pushed")
    expect(dialog).to_contain_text(f"Its folder {shop / 'backend'} is deleted with everything")
    remove = dialog.get_by_role("button", name="Delete repository")
    expect(remove).to_be_disabled()
    typed = dialog.get_by_role("textbox", name="Type backend to delete it")
    typed.fill("Backend")
    expect(remove).to_be_disabled()
    shot(page, "typed-wrong")
    page.emulate_media(color_scheme="dark")
    shot(page, "dialog-dark")
    page.emulate_media(color_scheme="light")
    typed.fill("backend")
    expect(remove).to_be_enabled()
    remove.click()
    expect(dialog).to_have_count(0)
    expect(row(view, "backend")).to_have_count(0)
    assert not (shop / "backend").exists()


def test_delete_a_clean_repository_asks_no_name(page: Page, shop, server, shot):
    view = project_page(page, server)
    row(view, "frontend").get_by_role("button", name="Delete").click()
    dialog = page.get_by_role("dialog", name="Delete repository frontend?")
    expect(dialog).to_contain_text("All its work is on the remote. No session is forgotten.")
    expect(dialog.get_by_role("textbox")).to_have_count(0)
    shot(page, "clean")
    dialog.get_by_role("button", name="Delete repository").click()
    expect(row(view, "frontend")).to_have_count(0)
    assert not (shop / "frontend").exists()


def test_delete_is_refused_while_a_session_runs_there(page: Page, shop, server, shot):
    runtime.start_session(None, None, None, "fake", project="shop", repo_name="frontend")
    agent_helpers.wait_for(lambda: loop.running("shop-frontend"), "the loop", "shop-frontend")
    view = project_page(page, server)
    row(view, "frontend").get_by_role("button", name="Delete").click()
    dialog = page.get_by_role("dialog", name="Delete repository frontend?")
    expect(dialog.get_by_role("alert")).to_have_text(
        "repository frontend of project shop has sessions not stopped: shop-frontend; stop them "
        "first with lado stop <name>"
    )
    expect(dialog.get_by_role("button")).to_have_text(["Close"])
    shot(page, "refused")
    dialog.get_by_role("button", name="Close").click()
    expect(dialog).to_have_count(0)
    assert (shop / "frontend").is_dir()


def test_rename_in_place(page: Page, shop, server, shot):
    runtime.start_session(None, None, None, "fake", project="shop", repo_name="frontend")
    idle("shop-frontend")
    view = project_page(page, server)
    view.get_by_role("button", name="Rename").click()
    field = view.get_by_role("textbox", name="Project title")
    expect(field).to_have_value("Shop")
    field.fill("Shop EU")
    shot(page, "renaming")
    field.press("Enter")
    expect(view.get_by_role("heading", name="Shop EU")).to_be_visible()
    listed = page.get_by_role("navigation", name="Projects").get_by_role("link", name="Shop EU")
    expect(listed).to_be_visible()
    assert projects.get("shop").title == "Shop EU"
    page.goto(f"{server['url']}/sessions/shop-frontend/activity")
    facts = page.get_by_role("banner").locator(".session-meta > *")
    expect(facts.first).to_have_text("projectShop EU")

    # An untitled project: Tab takes the id.
    page.goto(f"{server['url']}/projects/acme")
    acme = page.get_by_role("region", name="Project acme", exact=True)
    projects.rename("acme", None)
    page.reload()
    expect(acme.get_by_role("heading", name="acme")).to_be_visible()
    acme.get_by_role("button", name="Rename").click()
    field = acme.get_by_role("textbox", name="Project title")
    field.press_sequentially("ac")
    expect(acme).to_contain_text("Tab takes the id · Enter to save · Esc to cancel")
    shot(page, "suggestion")
    field.press("Tab")
    expect(field).to_have_value("acme")
    expect(field).to_be_focused()
    field.press("Escape")
    assert projects.get("acme").title is None


def test_new_project_says_when_the_title_gives_no_id(page: Page, shop, server, shot):
    page.set_viewport_size({"width": 1440, "height": 900})
    log_in(page, server, "/projects")
    page.get_by_role("button", name="New project").click()
    dialog = page.get_by_role("dialog", name="New project")
    dialog.get_by_role("textbox", name="Title (optional)").fill("!!!")
    expect(dialog).to_contain_text("The title gives no id: type one.")
    expect(dialog.get_by_role("button", name="Create project")).to_be_disabled()
    shot(page, "no-id")


def test_a_narrow_desktop_window_stacks_the_section(page: Page, shop, server, shot):
    page.set_viewport_size({"width": 390, "height": 800})  # no touch: not a phone
    log_in(page, server, "/projects")
    projects_list = page.get_by_role("navigation", name="Projects")
    expect(projects_list.get_by_role("link", name="Shop")).to_be_visible()
    expect(page.get_by_text("Select a project")).to_have_count(0)
    no_sideways_scroll(page)
    shot(page, "list")
    projects_list.get_by_role("link", name="Shop").click()
    view = page.get_by_role("region", name="Project shop", exact=True)
    expect(block(view, "Repositories")).to_be_visible()
    box = view.bounding_box()
    assert box["x"] < 100 and box["width"] > 300, box  # under the list, not beside it
    no_sideways_scroll(page)
    shot(page, "project")


def test_new_session_for_a_project_that_is_gone_says_so(page: Page, shop, server, shot):
    view = project_page(page, server)
    expect(block(view, "Repositories")).to_be_visible()
    projects.delete("shop", True)
    view.get_by_role("button", name="New session…").click()
    dialog = page.get_by_role("dialog", name="New session")
    expect(dialog).to_contain_text("⚠ No project shop any more: choose one.")
    expect(dialog.get_by_role("combobox", name="Project")).to_have_value("acme")
    shot(page, "gone")


def test_clone_into_a_projects_folder_opens_the_project(page: Page, shop, server, tmp_path, shot):
    url = agent_helpers.bare_remote(tmp_path / "admin-remote")
    page.set_viewport_size({"width": 1440, "height": 900})
    log_in(page, server)
    page.get_by_role("button", name="New session").click()
    dialog = page.get_by_role("dialog", name="New session")
    dialog.get_by_role("button", name="Clone from URL").click()
    dialog.get_by_role("textbox", name=re.compile("Where")).fill(url)
    dialog.get_by_role("textbox", name="Clone into").fill(str(shop / "admin"))
    button = dialog.get_by_role("button", name="Open the project Shop")
    expect(button).to_be_visible()
    shot(page, "refused")
    button.click()
    expect(page).to_have_url(f"{server['url']}/projects/shop")
    expect(dialog).to_have_count(0)


def delete_dialog(view, title: str = "Shop"):
    block(view, "Delete project").get_by_role("button", name="Delete project…").click()
    return view.page.get_by_role("dialog", name=f"Delete project {title}?")


def test_delete_the_project_refused_while_a_session_runs_then_deleted(
    page: Page, shop, server, shot
):
    projects.set_variable("shop", "BOARD_URL", "https://board.example/shop")
    projects.set_secret("shop", "GH_TOKEN", "canary-ui-secret")
    runtime.start_session(None, None, None, "fake", project="shop", repo_name="frontend")
    agent_helpers.wait_for(lambda: loop.running("shop-frontend"), "the loop", "shop-frontend")
    view = project_page(page, server)
    expect(block(view, "Delete project")).to_contain_text(
        "Deletes its folder with every repository in it, its sessions, variables and secrets. "
        "Refused while a session of the project runs."
    )
    shot(page, "delete-block")
    dialog = delete_dialog(view)
    expect(dialog.get_by_role("alert")).to_have_text(
        "project shop has sessions not stopped: shop-frontend; stop them first with lado stop "
        "<name>"
    )
    expect(dialog.get_by_role("button")).to_have_text(["Close"])
    shot(page, "delete-refused")
    dialog.get_by_role("button", name="Close").click()
    expect(dialog).to_have_count(0)
    assert shop.is_dir() and state.get_project("shop")

    runtime.stop_session("shop-frontend")
    dialog = delete_dialog(view)
    expect(dialog).to_contain_text(
        f"Its folder {shop} is deleted with everything in it, and so are its sessions, "
        "variables and secrets. This cannot be undone."
    )
    expect(dialog.get_by_role("listitem")).to_have_text(
        ["backend: branch main not pushed", "shop-frontend", "BOARD_URL", "GH_TOKEN — secret"]
    )
    expect(dialog).not_to_contain_text("canary-ui-secret")
    remove = dialog.get_by_role("button", name="Delete project")
    expect(remove).to_be_disabled()
    typed = dialog.get_by_role("textbox", name="Type shop to delete it")
    typed.fill("Shop")
    expect(remove).to_be_disabled()
    typed.fill("shop")
    expect(remove).to_be_enabled()
    shot(page, "delete-dialog")
    page.emulate_media(color_scheme="dark")
    shot(page, "delete-dialog-dark")
    page.emulate_media(color_scheme="light")
    remove.click()
    expect(page).to_have_url(f"{server['url']}/projects")
    listed = page.get_by_role("navigation", name="Projects")
    expect(listed.get_by_role("link", name="ACME CRM")).to_be_visible()
    expect(listed.get_by_role("link", name="Shop")).to_have_count(0)
    shot(page, "deleted")
    assert not shop.exists()
    assert not project_secrets.data_folder("shop").exists()
    assert state.get_project("shop") is None and state.get_session("shop-frontend") is None


def test_a_project_folder_that_is_a_repository_does_not_count_its_repositories(
    page: Page, shop, server, shot
):
    subprocess.run(["git", "-C", str(shop), "init", "-q", "-b", "main"], check=True)
    subprocess.run(["git", "-C", str(shop), "commit", "-q", "--allow-empty", "-m", "i"], check=True)
    view = project_page(page, server)
    dialog = delete_dialog(view)
    expect(dialog.get_by_role("listitem").first).to_have_text(
        "the project's folder: branch main not pushed"
    )
    expect(dialog).not_to_contain_text("the project's folder: uncommitted changes")
    shot(page, "delete-rooted")


@pytest.fixture
def phone(browser: Browser):
    """A page of a touch screen upright, a phone (test_phone.py)."""
    width, height = UPRIGHT
    context = browser.new_context(
        viewport={"width": width, "height": height}, is_mobile=True, has_touch=True
    )
    yield context.new_page()
    context.close()


def test_on_a_phone_the_rows_buttons_go_under_the_name(phone: Page, shop, server, shot):
    page = phone
    log_in(page, server, "/projects/shop")
    view = page.get_by_role("region", name="Project shop", exact=True)
    name = row(view, "frontend").locator(".repo-name")
    start = row(view, "frontend").get_by_role("button", name="Start session")
    expect(start).to_be_visible()
    assert start.bounding_box()["y"] > name.bounding_box()["y"] + name.bounding_box()["height"]
    no_sideways_scroll(page)
    shot(page, "phone", full_page=False)
    page.emulate_media(color_scheme="dark")
    shot(page, "phone-dark", full_page=False)


def test_on_a_phone_the_delete_block_and_dialog_fit(phone: Page, shop, server, shot):
    page = phone
    log_in(page, server, "/projects/shop")
    view = page.get_by_role("region", name="Project shop", exact=True)
    deleting = block(view, "Delete project")
    deleting.scroll_into_view_if_needed()
    expect(deleting.get_by_role("button", name="Delete project…")).to_be_visible()
    no_sideways_scroll(page)
    shot(page, "phone-delete-block", full_page=False)
    dialog = delete_dialog(view)
    expect(dialog.get_by_role("textbox", name="Type shop to delete it")).to_be_visible()
    no_sideways_scroll(page)
    shot(page, "phone-delete-dialog", full_page=False)
    page.emulate_media(color_scheme="dark")
    shot(page, "phone-delete-dialog-dark", full_page=False)
