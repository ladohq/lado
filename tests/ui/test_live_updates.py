"""Live updates in a browser: the pages follow the change feed (GET /api/events) without a
reload, whatever process writes the change."""

import os
import subprocess
import sys

import pytest
from playwright.sync_api import Page, expect
from test_main_screen import log_in, running_session

from lado.server import run as server_run

pytestmark = pytest.mark.ui


def lado_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "lado.cli", *args],
        capture_output=True,
        text=True,
        env=os.environ,
        check=False,
        timeout=30,
    )


def test_a_new_session_and_lado_stop_show_without_a_reload(page: Page, server, repo, shot):
    first = running_session(repo)
    log_in(page, server)
    page.goto(f"{server['url']}/sessions/{first}")
    view = page.get_by_role("region", name=f"Session {first}")
    expect(view).to_contain_text("running")
    page.evaluate("window.notReloaded = true")
    shot(page)

    second = running_session(repo)
    sessions = page.get_by_role("navigation", name="Sessions")
    expect(sessions.get_by_role("link", name=second)).to_be_visible()
    shot(page, "new-session")

    assert lado_cli("stop", first).returncode == 0  # another process
    expect(view).to_contain_text("stopped")
    # Stopped is folded at first, but the open session is seen in it.
    expect(sessions.get_by_role("button", name="Stopped 1")).to_have_attribute(
        "aria-expanded", "false"
    )
    stopped = sessions.get_by_role("region", name="Stopped")
    expect(stopped.get_by_role("link", name=first)).to_contain_text("stopped")
    assert page.evaluate("window.notReloaded") is True
    shot(page, "stopped")


def test_the_top_bar_says_reconnecting_while_the_server_is_away(page: Page, server, shot):
    log_in(page, server)
    bar = page.get_by_role("banner")
    expect(bar.get_by_role("heading")).to_have_text("Home")
    expect(bar.get_by_role("status")).to_have_text("live")
    server_run.stop()
    expect(bar.get_by_role("status")).to_contain_text("reconnecting")
    shot(page, "reconnecting")
