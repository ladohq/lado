"""A newer LADO in the browser: the server's daily check (here a local index) finds it, and
the shell names it with `lado update`."""

import pytest
from playwright.sync_api import Page, expect
from test_main_screen import log_in

pytestmark = pytest.mark.ui


def test_the_shell_names_a_newer_lado_and_the_command_that_installs_it(
    page: Page, published, server, shot
):
    published(**{"99.0.0": "2026-10-04"})  # before the server's first look
    log_in(page, server)
    line = page.get_by_text("is available")
    expect(line).to_have_text("LADO 99.0.0 is available: run lado update")
    expect(line.locator("code")).to_have_text("lado update")
    expect(page.get_by_role("alert")).to_have_count(0)  # no version banner: same version
    shot(page)
