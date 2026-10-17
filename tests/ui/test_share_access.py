"""Open LADO on another device in the browser (docs/design/ui.md, Open on another device):
the system panel's QR-code icon opens the dialog with the link and its QR code, Copy link
copies it whole, New link… logs another browser out and keeps this page live, and without a
link the dialog says what makes one. On macOS with its firewall on, a server on 0.0.0.0 may
ask to accept incoming connections; the tests do not need them."""

import os
import subprocess
import sys

import fake_provider
import pytest
from playwright.sync_api import Browser, Page, expect
from test_main_screen import log_in
from test_phone import NARROWEST, box, device, no_sideways_scroll  # noqa: F401 (a fixture)

from lado.server import auth
from lado.server import run as server_run

pytestmark = pytest.mark.ui

TITLE = "Open LADO on another device"


@pytest.fixture
def serve(tmp_path, monkeypatch):
    """`serve(host, **env)`: a real `lado server` on `host` and a free port with `env` in
    its environment; its server.json with the token. Stopped after the test."""
    started = []

    def start(host: str, **env: str) -> dict:
        for name, value in env.items():
            monkeypatch.setenv(name, value)
        with open(tmp_path / "server.out", "w") as out:
            started.append(
                subprocess.Popen(
                    [
                        sys.executable,
                        str(fake_provider.LADO),
                        "server",
                        "--host",
                        host,
                        "--port",
                        "0",
                    ],
                    stdout=out,
                    stderr=subprocess.STDOUT,
                    env=os.environ,
                )
            )
        return {**server_run.wait_ready(), "token": auth.token()}

    yield start
    if started:
        server_run.stop()
        started[0].wait(timeout=10)


def open_dialog(page: Page):
    page.get_by_role("button", name="System").click()
    page.get_by_role("dialog", name="System").get_by_role(
        "button", name="Open on another device"
    ).click()
    return page.get_by_role("dialog", name=TITLE)


def test_the_panels_header_has_three_icons(page: Page, serve, shot):
    server = serve("127.0.0.1")
    log_in(page, server)
    page.get_by_role("button", name="System").click()
    head = page.get_by_role("dialog", name="System").locator(".system-head")
    expect(head.locator(".icon-button")).to_have_count(3)
    labels = [icon.get_attribute("aria-label") for icon in head.locator(".icon-button").all()]
    assert labels == ["Open on another device", "Copy system info", "LADO on GitHub"]
    expect(head.get_by_role("link", name="LADO on GitHub")).to_have_attribute("target", "_blank")
    expect(head).not_to_contain_text("GitHub ↗")
    shot(page, "share-panel")


def test_the_link_its_qr_code_and_copy_link(page: Page, serve, shot):
    server = serve("0.0.0.0", LADO_PUBLIC_HOST="lado-ui.test")
    log_in(page, server)
    page.context.grant_permissions(["clipboard-read", "clipboard-write"], origin=server["url"])
    dialog = open_dialog(page)
    expect(dialog.get_by_role("img", name="QR code of the link")).to_be_visible()
    token = server["token"]
    cut = f"http://lado-ui.test:{server['port']}/?token={token[:4]}…{token[-4:]}"
    expect(dialog.get_by_text(cut)).to_be_visible()
    expect(dialog).to_contain_text("full access")
    expect(dialog).not_to_contain_text(token)
    dialog.get_by_role("button", name="Copy link").click()
    expect(dialog.get_by_text("Link copied")).to_be_visible()
    copied = page.evaluate("navigator.clipboard.readText()")
    assert copied == f"http://lado-ui.test:{server['port']}/?token={token}"
    expect(page.get_by_role("dialog", name="System")).to_be_visible()  # behind the dialog
    shot(page, "share-link")


def test_a_new_link_logs_another_browser_out_and_keeps_this_page(
    page: Page, browser: Browser, serve, shot
):
    server = serve("0.0.0.0", LADO_PUBLIC_HOST="lado-ui.test")
    other = browser.new_context().new_page()
    log_in(other, server)
    expect(other.get_by_role("button", name="System")).to_have_text("live")
    log_in(page, server)
    expect(page.get_by_role("button", name="System")).to_have_text("live")
    dialog = open_dialog(page)
    expect(dialog.get_by_role("img", name="QR code of the link")).to_be_visible()
    dialog.get_by_role("button", name="New link…").click()
    expect(dialog.get_by_role("heading", name="Make a new link?")).to_be_visible()
    shot(page, "share-confirm")
    old = server["token"]
    dialog.get_by_role("button", name="Make a new link").click()
    expect(dialog.get_by_role("heading", name=TITLE)).to_be_visible()
    new = auth.token()
    assert new != old
    expect(dialog.get_by_text(f"?token={new[:4]}…{new[-4:]}")).to_be_visible()
    shot(page, "share-new-link")
    dialog.get_by_role("button", name="Close").click()
    expect(page.get_by_role("button", name="System")).to_have_text("live")
    assert page.request.get(f"{server['url']}/api/sessions").status == 200  # the new cookie
    expect(other.get_by_role("alert")).to_have_text(
        "no valid token: open the link `lado ui` prints"
    )
    shot(other, "share-logged-out")
    other.context.close()


def test_on_loopback_the_dialog_gives_the_command(page: Page, serve, shot):
    server = serve("127.0.0.1")
    log_in(page, server)
    dialog = open_dialog(page)
    expect(dialog.get_by_text("lado server stop && lado ui --host 0.0.0.0")).to_be_visible()
    expect(dialog.get_by_role("button", name="Copy command")).to_be_visible()
    expect(dialog.get_by_role("img")).to_have_count(0)
    shot(page, "share-loopback")


def test_in_a_container_without_a_name_the_dialog_names_lado_public_host(page: Page, serve, shot):
    server = serve("0.0.0.0", LADO_CONTAINER="1", LADO_LISTEN="0.0.0.0")
    log_in(page, server)
    dialog = open_dialog(page)
    expect(dialog).to_contain_text("LADO is open to your network (LADO_LISTEN=0.0.0.0)")
    expect(dialog.get_by_text("LADO_PUBLIC_HOST=<this computer's name>")).to_be_visible()
    expect(dialog.get_by_role("img")).to_have_count(0)
    shot(page, "share-no-address")


def test_on_a_phone_the_dialog_fits_the_screen(device, serve, shot):  # noqa: F811
    """The phone layout (LAD-95): the panel's three icons and the dialog with its QR code
    within the narrowest screen, nothing scrolled sideways."""
    server = serve("0.0.0.0", LADO_PUBLIC_HOST="lado-ui.test")
    page = device(NARROWEST)
    log_in(page, server)
    page.get_by_role("button", name="System").click()
    head = page.get_by_role("dialog", name="System").locator(".system-head")
    expect(head.locator(".icon-button")).to_have_count(3)
    for icon in head.locator(".icon-button").all():
        assert box(icon)["x"] + box(icon)["width"] <= NARROWEST[0]
    shot(page, "share-phone-panel", full_page=False)
    head.get_by_role("button", name="Open on another device").click()
    dialog = page.get_by_role("dialog", name=TITLE)
    qr = dialog.get_by_role("img", name="QR code of the link")
    expect(qr).to_be_visible()
    for part in (dialog, qr, dialog.get_by_role("button", name="Copy link")):
        found = box(part)
        assert found["x"] >= 0 and found["x"] + found["width"] <= NARROWEST[0], found
    no_sideways_scroll(page)
    shot(page, "share-phone-dialog", full_page=False)
