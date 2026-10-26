"""The Projects section in a browser (openspec change projects-section; docs/design/ui.md,
Projects): New project, a project's variables and secrets, the running line that follows a
session's start, the session head's link back, and the phone's turns. A secret's value
leaves the browser only in the body of its PUT: it is in no address the page asked, in
neither storage of the page, in no line of the server's log, and in no file under LADO_HOME
but the secret's own. Every wait is for a state, never for time."""

import json
import uuid

import agent_helpers
import pytest
from playwright.sync_api import Browser, Page, expect
from test_main_screen import log_in
from test_phone import UPRIGHT, no_sideways_scroll
from test_project_secrets_canary import files_holding

from lado import loop, project_secrets, projects, runtime, state

pytestmark = pytest.mark.ui


def section(page: Page, name: str):
    return page.get_by_role("region", name=name, exact=True)


def masked(page: Page, field):
    """A secret's field is a text field drawn as dots by a font of dots, and the page holds
    no password field and no field styled as one: Chrome and Safari offer to save a password
    field whatever its autocomplete (LAD-149), and Safari a field with -webkit-text-security
    too (LAD-155). Every character, the space too, is one dot of one width."""
    expect(page.locator("input[type=password]")).to_have_count(0)
    expect(field).to_have_attribute("type", "text")
    style = "(field, name) => getComputedStyle(field).getPropertyValue(name)"
    assert field.evaluate(style, "-webkit-text-security") == "none"
    assert field.evaluate(style, "font-family") == "LadoSecretDots"
    assert page.evaluate("document.fonts.load('16px LadoSecretDots').then(f => f.length)") == 1
    assert page.evaluate("document.fonts.check('16px LadoSecretDots')")
    widths = page.evaluate(
        """text => {
            const context = document.createElement('canvas').getContext('2d');
            context.font = '16px LadoSecretDots';
            return [...text].map(one => context.measureText(one).width);
        }""",
        "sk_live Пароль 秘密 🔑",
    )
    assert len(set(widths)) == 1 and widths[0] > 0, widths


def test_new_project_and_its_variables_and_secrets(page: Page, server, tmp_path, lado_home, shot):
    page.set_viewport_size({"width": 1440, "height": 900})
    asked: list[str] = []
    page.on("request", lambda request: asked.append(request.url))
    logged: list[str] = []  # the browser's console and the page's uncaught errors
    page.on("console", lambda message: logged.append(message.text))
    page.on("pageerror", lambda error: logged.append(str(error)))
    first, second = (f"canary-{uuid.uuid4().hex}" for _ in range(2))
    log_in(page, server)
    page.goto(f"{server['url']}/projects")
    expect(page.get_by_role("heading", name="No projects yet")).to_be_visible()
    shot(page, "empty")

    # New project: the id follows the title, with its folder.
    page.get_by_role("button", name="New project…").click()
    dialog = page.get_by_role("dialog", name="New project")
    dialog.get_by_role("textbox", name="Title (optional)").fill("Магазин EU")
    expect(dialog.get_by_role("textbox", name="Id")).to_have_value("magazin-eu")
    folder = projects.folder("magazin-eu")
    expect(dialog).to_contain_text(f"Its folder: {folder}. The id never changes.")
    shot(page, "new-project")
    dialog.get_by_role("button", name="Create project").click()
    expect(page).to_have_url(f"{server['url']}/projects/magazin-eu")
    view = section(page, "Project magazin-eu")
    expect(view.get_by_role("heading", name="Магазин EU")).to_be_visible()
    expect(view).to_contain_text("No session of this project is running.")
    assert folder.is_dir()
    # The page ends with the block that deletes the project.
    expect(
        section(page, "Delete project").get_by_role("button", name="Delete project…")
    ).to_be_visible()

    # A plain variable, edited in place.
    variables, secrets = section(page, "Variables"), section(page, "Secrets")
    variables.get_by_role("button", name="+ Add variable").click()
    variables.get_by_role("textbox", name="Name", exact=True).fill("BOARD_URL")
    variables.get_by_role("textbox", name="Value", exact=True).fill("https://a")
    variables.get_by_role("button", name="Add", exact=True).click()
    expect(variables.get_by_role("button", name="+ Add variable")).to_be_visible()
    expect(variables.get_by_role("cell", name="https://a")).to_be_visible()
    variables.get_by_role("button", name="Edit").click()
    variables.get_by_role("textbox", name="Value of BOARD_URL").fill("https://b")
    variables.get_by_role("button", name="Save").click()
    # Saved: the row shows the value again, the field gone (a field's cell bears its value).
    expect(variables.get_by_role("textbox", name="Value of BOARD_URL")).to_have_count(0)
    expect(variables.get_by_role("cell", name="https://b")).to_be_visible()
    assert state.project_variables("magazin-eu") == {"BOARD_URL": "https://b"}

    # A name that looks like a secret: refused verbatim, offered as a secret.
    variables.get_by_role("button", name="+ Add variable").click()
    variables.get_by_role("textbox", name="Name", exact=True).fill("STRIPE_KEY")
    variables.get_by_role("textbox", name="Value", exact=True).fill("sk_test_1")
    variables.get_by_role("button", name="Add", exact=True).click()
    expect(variables).to_contain_text("STRIPE_KEY looks like a secret (KEY)")
    shot(page, "looks-like-a-secret")
    variables.get_by_role("button", name="Add STRIPE_KEY as a secret instead").click()
    expect(secrets.get_by_role("textbox", name="Name", exact=True)).to_have_value("STRIPE_KEY")
    value = secrets.get_by_role("textbox", name="Value", exact=True)
    expect(value).to_have_value("")
    expect(value).to_have_attribute("autocomplete", "off")
    assert value.evaluate("field => field.closest('form')") is None
    masked(page, value)
    shot(page, "add-secret")  # the placeholder in the UI's font, not in dots

    # The secret: added, then replaced; the field empty after each.
    value.fill(first)
    secrets.get_by_role("button", name="Add", exact=True).click()
    expect(secrets.get_by_role("row", name="STRIPE_KEY")).to_contain_text("set · hidden")
    expect(value).to_have_count(0)
    secrets.get_by_role("row", name="STRIPE_KEY").get_by_role("button", name="Replace").click()
    replaced = secrets.get_by_role("textbox", name="New value of STRIPE_KEY")
    expect(replaced).to_have_attribute("placeholder", "New value (the old one is not shown)")
    masked(page, replaced)
    replaced.fill(second)
    shot(page, "replace")
    replaced.press("Enter")
    expect(replaced).to_have_count(0)
    secret = project_secrets.folder("magazin-eu") / "STRIPE_KEY"
    assert secret.read_text() == second
    shot(page, "variables")
    page.emulate_media(color_scheme="dark")
    shot(page, "variables-dark")
    page.emulate_media(color_scheme="light")

    # Remove asks in the row first.
    variables.get_by_role("button", name="Remove").click()
    expect(variables).to_contain_text("Remove BOARD_URL?")
    variables.get_by_role("button", name="Cancel").click()
    assert state.project_variables("magazin-eu") == {"BOARD_URL": "https://b"}

    # Where a value must not be.
    for canary in (first, second):
        assert [url for url in asked if canary in url] == []
        assert canary not in page.content()
        assert [text for text in logged if canary in text] == []
        stored = page.evaluate(
            "JSON.stringify([Object.entries(localStorage), Object.entries(sessionStorage)])"
        )
        assert canary not in stored
        assert canary not in (tmp_path / "server.out").read_text()
    assert files_holding(lado_home, second.encode(), []) == [secret]
    assert files_holding(lado_home, first.encode(), []) == []
    assert any(url.endswith("/api/projects/magazin-eu/secrets/STRIPE_KEY") for url in asked)


@pytest.fixture
def shop(git_config):
    """The project shop titled Shop with its repository frontend."""
    projects.create("shop", "Shop")
    agent_helpers.init_repo(projects.folder("shop") / "frontend")


def test_the_running_line_follows_a_session_and_its_head_links_back(page: Page, server, shop, shot):
    page.set_viewport_size({"width": 1440, "height": 900})
    log_in(page, server)
    page.goto(f"{server['url']}/projects/shop")
    view = section(page, "Project shop")
    expect(view).to_contain_text("No session of this project is running.")
    row = page.get_by_role("navigation", name="Projects").get_by_role("link", name="Shop")
    expect(row).to_contain_text("shop · 1 repository · no sessions running")

    runtime.start_session(None, None, None, "fake", project="shop", repo_name="frontend")
    agent_helpers.wait_for(lambda: loop.running("shop-frontend"), "the loop", "shop-frontend")
    line = view.locator(".project-notes")  # the running line; the Sessions block links it too
    running = line.get_by_role("link", name="shop-frontend")
    expect(running).to_be_visible()  # no reload: the sessions' feed reads the page anew
    expect(view).to_contain_text("Running now: shop-frontend — restart a session")
    expect(row).to_contain_text("1 running")
    shot(page, "running")

    running.click()
    head = page.get_by_role("banner")
    link = head.get_by_role("link", name="Shop")
    expect(link).to_have_attribute("href", "/projects/shop")
    link.click()
    expect(page).to_have_url(f"{server['url']}/projects/shop")

    runtime.stop_session("shop-frontend")
    expect(view).to_contain_text("No session of this project is running.")


@pytest.fixture
def phone(browser: Browser):
    """A page of a touch screen upright, a phone (test_phone.py)."""
    width, height = UPRIGHT
    context = browser.new_context(
        viewport={"width": width, "height": height}, is_mobile=True, has_touch=True
    )
    yield context.new_page()
    context.close()


def test_on_a_phone_the_list_and_a_project_in_turns(phone: Page, server, shop, shot):
    projects.set_variable("shop", "BOARD_URL", "https://board.example/shop-team")
    projects.set_secret("shop", "GH_TOKEN", "canary-phone")
    page = phone
    log_in(page, server)
    page.goto(f"{server['url']}/projects")
    page.get_by_role("navigation", name="Projects").get_by_role("link", name="Shop").click()
    view = section(page, "Project shop")
    expect(view.get_by_role("heading", name="Shop")).to_be_visible()
    expect(page.get_by_role("navigation", name="Projects")).to_have_count(0)
    no_sideways_scroll(page)
    shot(page, "project", full_page=False)
    page.emulate_media(color_scheme="dark")
    shot(page, "project-dark", full_page=False)
    page.get_by_role("link", name="← All projects").click()
    expect(page.get_by_role("navigation", name="Projects")).to_be_visible()
    expect(page.get_by_text("Select a project")).to_have_count(0)
    shot(page, "list", full_page=False)
    assert "canary-phone" not in json.dumps(page.content())
