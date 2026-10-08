"""Artifacts in a browser (docs/design/ui.md, Artifacts): the session's Artifacts tab and an
artifact's page, a gate's chip that opens the attached record in a panel and says when the
artifact changed since, an HTML artifact that runs sandboxed (in its frame and in a tab of
its own), and the panel on a phone's screen."""

import base64
import uuid

import agent_helpers
import pytest
from playwright.sync_api import Page, expect
from test_main_screen import log_in

from lado import artifacts, loop, runs, runtime, state

pytestmark = pytest.mark.ui

SHIP = """\
name: ship
description: the supervisor designs it, the human approves it
start: design
states:
  design: {agent: supervisor, do: sleep 0, outcomes: {ready: check}}
  check:
    gate: approval
    ask: Approve the design?
    outcomes: {approved: end, rejected: design}
  end: {end: true}
"""

# A 1x1 PNG.
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)

# A page whose script tries to reach the UI: its parent's document and the API with the
# human's cookie. It writes what it got into itself.
PROBE = """\
<!doctype html><html><body>
<h1>Probe</h1>
<p id="doc">waiting</p><p id="api">waiting</p>
<script>
try { document.getElementById("doc").textContent = "read " + parent.document.title; }
catch (e) { document.getElementById("doc").textContent = "blocked"; }
fetch("/api/sessions", { credentials: "include" })
  .then((answer) => answer.text().then((text) => {
    document.getElementById("api").textContent = "read " + answer.status + " " + text.slice(0, 40);
  }))
  .catch(() => { document.getElementById("api").textContent = "blocked"; });
</script>
</body></html>
"""


@pytest.fixture(autouse=True)
def wide(page: Page):
    page.set_viewport_size({"width": 1280, "height": 900})


def designed_session(repo, tmp_path) -> str:
    """A running session of the fake agent with run ship/x waiting at gate "check": its
    design note carries ship/x/design; the session has a plan, ship/x a screenshot and
    run ship/y a mockup too."""
    kit = repo / ".lado" / "kits" / "uiflow"
    (kit / "flows").mkdir(parents=True, exist_ok=True)
    (kit / "kit.yaml").write_text("name: uiflow\nversion: 1.0.0\n")
    (kit / "flows" / "ship.yaml").write_text(SHIP)
    session = f"ui-{uuid.uuid4().hex[:6]}"
    runtime.start_session(str(repo), session, None, "fake", ["default", "uiflow"])
    agent_helpers.wait_for(
        lambda: state.get_agent(session, "supervisor").status == state.IDLE, "idle", session
    )
    agent_helpers.wait_for(lambda: loop.running(session), "the session loop", session)
    runs.start(session, "ship", "Add a login page", name="x")
    runs.start(session, "ship", "Add a logout page", name="y")
    write = lambda name, **given: artifacts.write(session, "supervisor", name, **given)  # noqa: E731
    write("plan", content="# Plan of the week\n\nLogin, then logout.", title="Plan of the week")
    shot = tmp_path / "shot.png"
    shot.write_bytes(PNG)
    write("ship/x/shot.png", file=str(shot), title="The login form")
    write("ship/y/mockup.html", content="<h1>Logout</h1>", title="Logout mockup")
    write("ship/x/design", content="# Design v1\n\nOne form.", title="Login design")
    runs.advance(session, "supervisor", "ship/x", "ready", "the design", attached=["ship/x/design"])
    return session


def test_the_tab_filters_finds_and_opens_an_artifacts_page(
    page: Page, server, repo, tmp_path, shot
):
    session = designed_session(repo, tmp_path)
    log_in(page, server)
    page.goto(f"{server['url']}/sessions/{session}/artifacts")
    table = page.get_by_role("table", name="Artifacts")
    names = table.locator("tbody .full-name")
    expect(names).to_have_text(["ship/x/design", "ship/y/mockup.html", "ship/x/shot.png", "plan"])
    shot(page, "all")
    page.get_by_role("combobox", name="Scope").select_option("ship/x")
    expect(names).to_have_text(["ship/x/design", "ship/x/shot.png"])
    page.get_by_role("button", name="Images").click()
    expect(names).to_have_text(["ship/x/shot.png"])
    page.get_by_role("combobox", name="Scope").select_option("*")
    page.get_by_role("button", name="All types").click()
    page.get_by_role("searchbox", name="Find an artifact").fill("week")
    expect(names).to_have_text(["plan"])
    shot(page, "found")
    page.get_by_role("searchbox", name="Find an artifact").fill("")
    table.get_by_role("row").filter(has_text="ship/x/shot.png").click()
    expect(page.get_by_role("img", name="The login form")).to_be_visible()
    shot(page, "image")
    page.get_by_role("link", name="← Artifacts").click()
    expect(page).to_have_url(f"{server['url']}/sessions/{session}/artifacts")
    expect(names).to_have_count(4)


def test_a_gates_chip_opens_the_attached_record_and_says_when_it_changed(
    page: Page, server, repo, tmp_path, shot
):
    session = designed_session(repo, tmp_path)
    log_in(page, server)
    page.goto(f"{server['url']}/sessions/{session}")
    card = page.get_by_role("article", name="Gate #1", exact=True)
    chip = card.get_by_role("button", name="Open artifact ship/x/design")
    expect(chip).to_contain_text("design")
    chip.click()
    panel = page.get_by_role("dialog", name="Artifact ship/x/design")
    expect(panel.get_by_role("heading", name="Design v1")).to_be_visible()
    shot(page, "panel")
    artifacts.write(
        session, "supervisor", "ship/x/design", content="# Design v2", summary="two forms"
    )
    expect(panel.get_by_role("status").filter(has_text="changed since")).to_contain_text(
        "two forms"
    )
    expect(card.get_by_role("button", name="Open latest ship/x/design")).to_be_visible()
    shot(page, "changed")
    panel.get_by_role("button", name="Open latest").click()
    expect(panel.get_by_role("heading", name="Design v2")).to_be_visible()
    page.keyboard.press("Escape")
    expect(panel).to_have_count(0)


def test_an_html_artifact_runs_sandboxed_and_never_reaches_the_ui(
    page: Page, server, repo, tmp_path, shot
):
    session = designed_session(repo, tmp_path)
    probe = artifacts.write(session, "supervisor", "probe.html", content=PROBE)
    log_in(page, server)
    page.goto(f"{server['url']}/sessions/{session}/artifacts/{probe.artifact.id}")
    frame = page.frame_locator("iframe[title='probe.html']")
    expect(frame.get_by_role("heading", name="Probe")).to_be_visible()  # its script ran
    expect(frame.locator("#doc")).to_have_text("blocked")
    expect(frame.locator("#api")).not_to_have_text("waiting")
    expect(frame.locator("#api")).not_to_contain_text("read 200")
    shot(page, "frame")
    # A tab of its own: only the server's sandbox keeps it from the human's cookie.
    content = f"{server['url']}/api/sessions/{session}/records/{probe.record.id}/content"
    tab = page.context.new_page()
    tab.goto(content)
    expect(tab.locator("#api")).not_to_have_text("waiting")
    expect(tab.locator("#api")).not_to_contain_text("read 200")
    shot(tab, "tab")
    # The same request from the UI itself is read: the cookie is good.
    status = page.evaluate("fetch('/api/sessions').then((answer) => answer.status)")
    assert status == 200


def test_on_a_phone_the_panel_takes_the_screen(page: Page, server, repo, tmp_path, shot):
    session = designed_session(repo, tmp_path)
    page.set_viewport_size({"width": 390, "height": 844})
    log_in(page, server)
    page.goto(f"{server['url']}/sessions/{session}")
    page.get_by_role("button", name="Open artifact ship/x/design").click()
    panel = page.get_by_role("dialog", name="Artifact ship/x/design")
    expect(panel.get_by_role("heading", name="Design v1")).to_be_visible()
    box = panel.bounding_box()
    assert box is not None and (box["x"], box["width"]) == (0, 390)
    shot(page, "phone")
    panel.get_by_role("link", name="Open in Artifacts tab").click()
    expect(page).to_have_url(
        f"{server['url']}/sessions/{session}/artifacts/"
        f"{artifacts.find(session, 'ship/x/design')[0].id}"
        f"?record={artifacts.find(session, 'ship/x/design')[1].id}"
    )


LONG_NAME = "very-long-file-name-" * 3
TODO = "rename it and check it again " * 4
WIDE = "# Review\n\n| finding | where | what to do |\n| :--- | :---: | ---: |\n" + "".join(
    f"| finding {i} | web/src/{LONG_NAME}{i}.tsx | {TODO} |\n" for i in range(3)
)


def test_a_wide_table_scrolls_in_its_frame_and_the_panel_does_not(
    page: Page, server, repo, tmp_path, shot
):
    session = designed_session(repo, tmp_path)
    artifacts.write(session, "supervisor", "ship/x/design", content=WIDE, summary="a table")
    log_in(page, server)
    page.goto(f"{server['url']}/sessions/{session}")
    page.get_by_role("button", name="Open artifact ship/x/design").click()
    panel = page.get_by_role("dialog", name="Artifact ship/x/design")
    panel.get_by_role("button", name="Open latest").click()
    frame = panel.locator(".md-table")
    expect(frame.get_by_role("columnheader")).to_have_text(["finding", "where", "what to do"])
    expect(frame.get_by_role("row")).to_have_count(4)
    widths = frame.evaluate(
        """(frame) => {
          const sideways = [];
          for (let one = frame.parentElement; one; one = one.parentElement) {
            if (one.scrollWidth > one.clientWidth) sideways.push(one.className || one.tagName);
            if (one.getAttribute("role") === "dialog") break;
          }
          return { scroll: frame.scrollWidth, client: frame.clientWidth, sideways };
        }"""
    )
    assert widths["scroll"] > widths["client"], widths  # the table scrolls in its frame
    assert widths["sideways"] == [], widths  # and nothing around it does
    shot(page, "wide-table")
