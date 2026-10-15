"""The system panel in the browser (docs/design/ui.md, System panel): `live` opens it, the
system info is copied for an issue, a newer LADO (here a local index) marks `live` and
gives the panel its Update block, and in a container the panel says so."""

import re

import pytest
from playwright.sync_api import Page, expect
from test_main_screen import log_in

from lado import __version__, state

pytestmark = pytest.mark.ui


def test_live_opens_the_system_panel_and_copies_the_system_info(page: Page, server, shot):
    log_in(page, server)
    page.context.grant_permissions(["clipboard-read", "clipboard-write"], origin=server["url"])
    live = page.get_by_role("button", name="System")
    expect(live).to_have_text("live")
    live.click()
    panel = page.get_by_role("dialog", name="System")
    expect(panel.get_by_text(f"LADO {__version__}")).to_be_visible()
    expect(panel.get_by_text("Running")).to_be_visible()
    expect(panel.get_by_role("region", name="Providers")).to_contain_text("Claude Code")
    expect(panel.locator(".system-check")).to_contain_text("No update check")
    panel.get_by_role("button", name="Copy system info").click()
    expect(panel.get_by_text("System info copied")).to_be_visible()
    copied = page.evaluate("navigator.clipboard.readText()")
    assert copied.startswith("### LADO system info\n")
    assert re.search(r"^- Browser: Chrome \d+ on \w+$", copied, re.MULTILINE)
    for secret in (str(state.home()), server["token"], server["url"].split("//")[1]):
        assert secret not in copied
    shot(page)


def test_an_up_to_date_final_release_shows_no_update(page: Page, published, server, shot):
    # The server runs the working copy's version, a final release or a release candidate:
    # with only that one published it is up to date either way, and its answers are changed
    # to a final release's. Which releases a final one is offered is the server's rule,
    # tested in test_server_system.py.
    published(**{__version__: "2026-10-04"})  # before the server's first look

    def system_of_final_release(route):
        route.fulfill(json={**route.fetch().json(), "version": "99.0.0"})

    def as_final_release(route):
        info = route.fetch().json()
        info.update(current="99.0.0", prerelease=False, latest="99.0.0")
        route.fulfill(json=info)

    page.route(f"{server['url']}/api/update", as_final_release)
    page.route(f"{server['url']}/api/system", system_of_final_release)
    log_in(page, server)
    live = page.get_by_role("button", name="System")
    expect(live).to_have_text("live")
    live.click()
    panel = page.get_by_role("dialog", name="System")
    expect(panel.locator(".system-head")).to_contain_text("LADO 99.0.0")
    expect(panel.locator(".system-check")).to_contain_text("Up to date")
    expect(panel.get_by_role("region", name="Update")).to_have_count(0)
    expect(panel.locator(".pill")).to_have_count(0)
    expect(panel.get_by_text("Running")).to_be_visible()
    shot(page)


def test_a_release_candidate_and_a_newer_one_on_offer_are_marked(page: Page, server, shot):
    # The server runs the working copy's version, whatever its kind: its answers are changed
    # to a release candidate's, as the server gives them there (test_server_system.py).
    def system_of_release_candidate(route):
        route.fulfill(json={**route.fetch().json(), "version": "99.0.0rc1"})

    def as_release_candidate(route):
        info = route.fetch().json()
        info.update(
            current="99.0.0rc1",
            prerelease=True,
            latest="99.0.0rc2",
            available="99.0.0rc2",
            available_prerelease=True,
            released="2026-10-14",
        )
        route.fulfill(json=info)

    page.route(f"{server['url']}/api/update", as_release_candidate)
    page.route(f"{server['url']}/api/system", system_of_release_candidate)
    log_in(page, server)
    live = page.get_by_role("button", name="System: LADO 99.0.0rc2 is available")
    live.click()
    panel = page.get_by_role("dialog", name="System")
    expect(panel.locator(".system-head")).to_contain_text("LADO 99.0.0rc1")
    expect(panel.locator(".system-head .pill")).to_have_text("pre-release")
    update_block = panel.get_by_role("region", name="Update")
    expect(update_block).to_contain_text("99.0.0rc2 is out")
    expect(update_block.locator(".pill")).to_have_text("pre-release")
    expect(panel.get_by_text("Running")).to_be_visible()
    shot(page)


def test_a_newer_lado_marks_live_and_the_panel_offers_the_update(
    page: Page, published, server, shot
):
    published(**{"99.0.0": "2026-10-04"})  # before the server's first look
    page.set_viewport_size({"width": 1280, "height": 720})  # a laptop's window
    log_in(page, server)
    live = page.get_by_role("button", name="System: LADO 99.0.0 is available")
    expect(live).to_have_text("live↑ 99.0.0")
    expect(page.get_by_text("is available")).to_have_count(0)  # no line under the top bar
    expect(page.get_by_role("alert")).to_have_count(0)  # no version banner: same version
    live.click()
    update = page.get_by_role("dialog", name="System").get_by_role("region", name="Update")
    expect(update).to_contain_text("99.0.0 is out")
    # A working copy is no uv tool or pipx install: the commands by hand, no button.
    expect(update).to_contain_text("not a uv tool or pipx install")
    expect(update.get_by_role("button", name="Update…")).to_have_count(0)
    expect(update.locator("pre")).to_contain_text("install lado==99.0.0")
    panel = page.get_by_role("dialog", name="System")
    expect(panel.get_by_text("Running")).to_be_visible()
    shot(page)
    # Taller than the window with the Update block: the panel ends inside the window and
    # scrolls, so its last line, the check with ↻, is reached.
    box = panel.bounding_box()
    assert box["y"] + box["height"] <= 720, box
    check = panel.get_by_role("button", name="Check for a newer LADO now")
    check.scroll_into_view_if_needed()
    expect(check).to_be_in_viewport()
    shot(page, "scrolled")


@pytest.fixture
def container_server(monkeypatch, published, request):
    """The server of LADO's image: started with LADO_CONTAINER, and PyPI has 99.0.0 before
    its first look."""
    monkeypatch.setenv("LADO_CONTAINER", "1")
    published(**{"99.0.0": "2026-10-04"})
    return request.getfixturevalue("server")


def test_in_a_container_the_panel_says_so_and_names_the_hosts_command(
    page: Page, container_server, shot
):
    page.set_viewport_size({"width": 1280, "height": 720})
    log_in(page, container_server)
    page.get_by_role("button", name="System: LADO 99.0.0 is available").click()
    panel = page.get_by_role("dialog", name="System")
    pill = panel.locator(".system-head .pill")
    expect(pill).to_have_text("container")
    expect(pill).to_have_attribute(
        "title", "LADO runs in a Docker container (LADO_CONTAINER): a new image updates it"
    )
    update = panel.get_by_role("region", name="Update")
    expect(update).to_contain_text("99.0.0 is out")
    expect(update).to_contain_text("LADO runs in a container: a new image updates it")
    expect(update.get_by_role("button", name="Update…")).to_have_count(0)
    expect(update.get_by_text("On the host:")).to_be_visible()
    expect(update.locator("pre")).to_have_text(
        'docker tag "$(docker compose images -q lado)" lado:previous && '
        "docker compose pull && docker compose up -d"
    )
    expect(update.get_by_role("button", name="Copy commands")).to_be_visible()
    expect(panel.get_by_text("Running")).to_be_visible()
    shot(page)
