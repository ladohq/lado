"""Artifacts in a browser (docs/design/ui.md, Artifacts): the session's Artifacts tab and an
artifact's page, a gate's chip that opens the attached record in a panel and says when the
artifact changed since, an HTML artifact that runs sandboxed (in its frame and in a tab of
its own), any other record alone in a tab of its own in the UI's theme, and the panel on a
phone's screen."""

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
    page.get_by_role("dialog", name="Artifact ship/x/shot.png").get_by_role(
        "link", name="Open in Artifacts tab"
    ).click()
    expect(page.get_by_role("img", name="The login form")).to_be_visible()
    shot(page, "image")
    page.get_by_role("link", name="← Artifacts").click()
    expect(page).to_have_url(f"{server['url']}/sessions/{session}/artifacts")
    expect(names).to_have_count(4)


def test_the_tab_counts_the_artifacts_and_a_row_opens_one_in_the_panel(
    page: Page, server, repo, tmp_path, shot
):
    session = designed_session(repo, tmp_path)
    log_in(page, server)
    page.goto(f"{server['url']}/sessions/{session}/artifacts")
    page.get_by_role("button", name="Collapse terminals").click()
    tabs = page.get_by_role("navigation", name="Session sections")
    expect(tabs.get_by_role("link", name="Artifacts · 4")).to_be_visible()
    table = page.get_by_role("table", name="Artifacts")
    page.get_by_role("searchbox", name="Find an artifact").fill("login")
    names = table.locator("tbody .full-name")
    expect(names).to_have_text(["ship/x/design", "ship/x/shot.png"])
    shot(page, "count")
    table.get_by_role("row").filter(has_text="ship/x/design").click()
    panel = page.get_by_role("dialog", name="Artifact ship/x/design")
    expect(panel.get_by_role("heading", name="Design v1")).to_be_visible()
    assert page.url.startswith(f"{server['url']}/sessions/{session}/artifacts?view=")
    expect(table).to_be_visible()
    shot(page, "panel")
    page.keyboard.press("Escape")
    expect(panel).to_have_count(0)
    expect(page).to_have_url(f"{server['url']}/sessions/{session}/artifacts")
    expect(names).to_have_text(["ship/x/design", "ship/x/shot.png"])
    expect(table.get_by_role("link", name="ship/x/design")).to_be_focused()
    artifacts.write(session, "supervisor", "notes", content="more", title="More notes")
    expect(tabs.get_by_role("link", name="Artifacts · 5")).to_be_visible()


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


LONG_NAME = "VeryLongFileName" * 4  # no hyphen, no space: no place to break but `anywhere`
TODO = "rename it and check it again " * 4
# A few columns of prose and an unbroken path: it fits its frame, its cells wrapping.
PROSE = "| finding | where | what to do |\n| :--- | :---: | ---: |\n" + "".join(
    f"| finding {i} | web/src/{LONG_NAME}{i}.tsx | {TODO} |\n" for i in range(3)
)
# More columns than fit even wrapped: it scrolls in its own frame.
MANY = (
    "| " + " | ".join(f"column {i}" for i in range(14)) + " |\n"
    "|" + " --- |" * 14 + "\n"
    "| " + " | ".join(f"value of column {i}" for i in range(14)) + " |\n"
)
TABLES = f"# Review\n\n{PROSE}\nAnd the matrix:\n\n{MANY}"

# Per .md-table frame in `root`: its widths, the widest word of its cells against the
# cell's own width (a word that sticks out was not wrapped), and each element between the
# frame and `stop` that scrolls sideways (none may: only the frame does).
MEASURE_TABLES = """(root, stop) => [...root.querySelectorAll(".md-table")].map((frame) => {
  const sideways = [];
  for (let one = frame.parentElement; one && one !== document.body; one = one.parentElement) {
    if (one.scrollWidth > one.clientWidth) sideways.push(one.className || one.tagName);
    if (one.matches(stop)) break;
  }
  const sticking = [...frame.querySelectorAll("th, td")].filter((cell) => {
    const range = document.createRange();
    range.selectNodeContents(cell);
    return [...range.getClientRects()].some(
      (rect) => rect.right > cell.getBoundingClientRect().right + 0.5
    );
  }).length;
  const head = getComputedStyle(frame.querySelector("thead th"));
  // The narrowest column's width, padding included, in ems of its cells.
  const narrowest = Math.min(...[...frame.querySelectorAll("thead th")].map(
    (cell) => cell.getBoundingClientRect().width / parseFloat(getComputedStyle(cell).fontSize)
  ));
  return {
    narrowest,
    scroll: frame.scrollWidth,
    client: frame.clientWidth,
    sideways,
    sticking,
    headWrap: head.whiteSpace,
    headLook: [head.backgroundColor, head.fontWeight, head.padding, head.borderBottomWidth],
  };
})"""


@pytest.mark.parametrize("width", [1280, 390])
def test_a_table_wraps_its_cells_and_one_too_wide_scrolls_in_its_frame(
    page: Page, server, repo, tmp_path, shot, width
):
    session = designed_session(repo, tmp_path)
    artifacts.write(session, "supervisor", "ship/x/design", content=TABLES, summary="tables")
    page.set_viewport_size({"width": width, "height": 900})
    log_in(page, server)
    page.goto(f"{server['url']}/sessions/{session}")
    page.get_by_role("button", name="Open artifact ship/x/design").click()
    panel = page.get_by_role("dialog", name="Artifact ship/x/design")
    panel.get_by_role("button", name="Open latest").click()
    frames = panel.locator(".md-table")
    expect(frames.first.get_by_role("columnheader")).to_have_text(
        ["finding", "where", "what to do"]
    )
    expect(frames.first.get_by_role("row")).to_have_count(4)
    prose, many = panel.evaluate(MEASURE_TABLES, "[role=dialog]")
    assert prose["scroll"] <= prose["client"], prose  # it fits: no sideways scroll
    assert prose["sticking"] == 0, prose  # every cell's text, the path too, wraps inside it
    assert prose["headWrap"] != "nowrap", prose  # the head wraps by words too
    background, weight, padding, border = prose["headLook"]  # and keeps its look
    assert (weight, padding, border) == ("600", "6px 10px", "1px"), prose
    assert background != "rgba(0, 0, 0, 0)", prose
    assert many["scroll"] > many["client"], many  # too many columns: it scrolls in its frame,
    assert many["narrowest"] >= 6.95, many  # each column kept at its minimum, 7em
    assert prose["sideways"] == many["sideways"] == [], (prose, many)  # and nothing around
    for theme in ("light", "dark"):
        page.emulate_media(color_scheme=theme)
        frames.first.scroll_into_view_if_needed()
        shot(page, f"{theme}-prose")
        frames.last.scroll_into_view_if_needed()
        shot(page, f"{theme}-many")
    page.emulate_media(color_scheme="light")


def test_copy_link_copies_without_the_clipboard_api(page: Page, server, repo, tmp_path, shot):
    # Over http from another machine there is no Clipboard API: the legacy copy copies.
    session = designed_session(repo, tmp_path)
    log_in(page, server)
    page.goto(f"{server['url']}/sessions/{session}")
    page.context.grant_permissions(["clipboard-read", "clipboard-write"], origin=server["url"])
    page.evaluate("navigator.clipboard.writeText('stale')")
    page.evaluate(
        "Object.defineProperty(navigator, 'clipboard', {value: undefined, configurable: true})"
    )
    page.get_by_role("button", name="Open artifact ship/x/design").click()
    panel = page.get_by_role("dialog", name="Artifact ship/x/design")
    copy = panel.get_by_role("button", name="Copy link")
    copy.click()
    expect(panel.get_by_role("status")).to_have_text("Link copied")
    expect(page.get_by_role("dialog", name="Link to ship/x/design")).to_have_count(0)
    expect(copy).to_be_focused()
    assert page.evaluate("document.querySelectorAll('body > textarea').length") == 0
    shot(page)
    page.evaluate("delete navigator.clipboard")  # the API again, to read what was copied
    design = artifacts.find(session, "ship/x/design")[0].id
    assert page.evaluate("navigator.clipboard.readText()") == (
        f"{server['url']}/sessions/{session}/artifacts/{design}"
    )


@pytest.mark.parametrize("width", [1280, 390])
def test_the_link_to_copy_by_hand_stays_inside_the_window(
    page: Page, server, repo, tmp_path, shot, width
):
    # Copy link sits at the panel's right edge; when no copy works (no Clipboard API and a
    # refused legacy copy) its field opens below it, kept 8px inside the window.
    session = designed_session(repo, tmp_path)
    page.set_viewport_size({"width": width, "height": 844})
    log_in(page, server)
    page.goto(f"{server['url']}/sessions/{session}")
    page.evaluate(
        """() => {
          Object.defineProperty(navigator, 'clipboard', {value: undefined});
          document.execCommand = () => false;
        }"""
    )
    page.get_by_role("button", name="Open artifact ship/x/design").click()
    panel = page.get_by_role("dialog", name="Artifact ship/x/design")
    panel.get_by_role("button", name="Copy link").click()
    field = page.get_by_role("dialog", name="Link to ship/x/design")
    expect(field.get_by_role("textbox", name="Link")).to_be_focused()
    expect(field.get_by_text("Press ⌘C / Ctrl+C to copy")).to_be_visible()
    box = field.bounding_box()
    assert box is not None
    assert box["x"] >= 8 and box["x"] + box["width"] <= width - 8, box
    shot(page, f"copy-field-{width}")


def test_open_in_new_tab_shows_the_record_alone_in_the_uis_theme(
    page: Page, server, repo, tmp_path, shot
):
    session = designed_session(repo, tmp_path)
    log_in(page, server)
    page.goto(f"{server['url']}/sessions/{session}")
    page.get_by_role("button", name="Open artifact ship/x/design").click()
    panel = page.get_by_role("dialog", name="Artifact ship/x/design")
    expect(panel.get_by_role("heading", name="Design v1")).to_be_visible()
    with page.context.expect_page() as opened:
        panel.get_by_role("link", name="Open in new tab").click()
    tab = opened.value
    record = artifacts.find(session, "ship/x/design")[1].id
    expect(tab).to_have_url(f"{server['url']}/view/{session}/{record}")
    expect(tab.get_by_role("heading", name="Design v1")).to_be_visible()
    expect(tab).to_have_title("ship/x/design")
    for chrome in [".rail", ".topbar", ".artifact-head", ".artifact-meta"]:
        expect(tab.locator(chrome)).to_have_count(0)
    expect(tab.get_by_text("supervisor")).to_have_count(0)
    assert tab.evaluate("document.documentElement.dataset.theme") is None
    light = tab.evaluate("getComputedStyle(document.body).backgroundColor")
    shot(tab, "markdown-light")

    # The UI's stored theme reaches the tab.
    tab.evaluate("localStorage.setItem('lado.theme', 'dark')")
    tab.reload()
    expect(tab.get_by_role("heading", name="Design v1")).to_be_visible()
    assert tab.evaluate("document.documentElement.dataset.theme") == "dark"
    assert tab.evaluate("getComputedStyle(document.body).backgroundColor") not in (light, "")
    shot(tab, "markdown-dark")

    # An image alone, fitted to the tab.
    image = artifacts.find(session, "ship/x/shot.png")[1].id
    tab.goto(f"{server['url']}/view/{session}/{image}")
    expect(tab.get_by_role("img", name="The login form")).to_be_visible()
    expect(tab).to_have_title("ship/x/shot.png")
    expect(tab.locator(".rail")).to_have_count(0)
    shot(tab, "image-dark")

    # Text with its line numbers over the tab's width, and a Markdown table in light.
    tool = artifacts.write(session, "supervisor", "ship/x/tool.py", content="a = 1\nb = 2\n")
    tab.goto(f"{server['url']}/view/{session}/{tool.record.id}")
    code = tab.get_by_role("table", name="ship/x/tool.py")
    expect(code.locator(".line-number")).to_have_text(["1", "2"])
    shot(tab, "text-dark")
    tab.evaluate("localStorage.setItem('lado.theme', 'light')")
    table = artifacts.write(session, "supervisor", "review", content=WIDE)
    tab.goto(f"{server['url']}/view/{session}/{table.record.id}")
    expect(tab.get_by_role("columnheader")).to_have_text(["finding", "where", "what to do"])
    expect(tab.locator(".artifact-head")).to_have_count(0)
    shot(tab, "table-light")
