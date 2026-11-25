"""The first-run guide in a browser (openspec change first-run-guide): its main path on a
fresh LADO, from the welcome to the New session window, with the guide on (no LADO_GUIDE=0,
which every other test has), against a real `lado server`; then a reload (nothing), and Help
→ Getting started (the welcome again, Show me straight to New session). On a computer and on
a phone. Claude Code and Codex CLI are stand-ins on the server's PATH, installed and not
logged in, so the path is the same on every machine: their rows, passed with "I have neither",
then Model servers against the fake model server of tests/fake_model_server.py, whose key the
form first gets wrong, then Git servers' author, as git knows none. The login windows' steps
are vitest's (web/src/guide/Guide.login.test.tsx)."""

import os
import stat

import fake_model_server as fake
import pytest
from playwright.sync_api import Browser, Page, expect
from test_main_screen import log_in

pytestmark = pytest.mark.ui

KEY = "good-key"


@pytest.fixture
def fresh(tmp_path, monkeypatch, git_config, logins):
    """A LADO the guide starts on, taken before `server`: the guide on, Claude Code and Codex
    CLI installed and logged out, no key or login in the environment (`logins`: no CLI's own
    login files), a git that knows no author."""
    monkeypatch.delenv("LADO_GUIDE")
    # Any model provider's key (OpenCode and Kilo log in by OPENROUTER_API_KEY and the like).
    tokens = ["CLAUDE_CODE_OAUTH_TOKEN", "CODEX_ACCESS_TOKEN"]
    for name in [n for n in os.environ if n.endswith("_API_KEY")] + tokens:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codex-home"))
    git_config.write_text("")
    folder = tmp_path / "clis"
    folder.mkdir()
    # Each prints its version, and says it is not logged in to its status command.
    scripts = {
        "claude": 'if [ "$1" = auth ]; then echo \'{"loggedIn": false}\'; exit 1; fi\necho 2.1.0\n',
        "codex": 'if [ "$1" = login ]; then echo "Not logged in" >&2; exit 1; fi\n'
        "echo codex-cli 0.162.0\n",
        # The CLI that runs the fake model server's model (Codex CLI cannot: its MCP tools).
        "opencode": 'if [ "$1" = auth ]; then\n'
        '  printf "┌ Credentials %s\\n└ 0 credentials\\n" "$HOME"; exit 0\nfi\n'
        'if [ "$1" = models ]; then exit 0; fi\necho 1.18.35\n',
    }
    for name, body in scripts.items():
        script = folder / name
        script.write_text("#!/bin/sh\n" + body)
        script.chmod(script.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("PATH", f"{folder}{os.pathsep}{os.environ['PATH']}")


@pytest.fixture
def models():
    server = fake.Server("lmstudio", key=KEY)
    yield server
    server.close()


def card(page: Page):
    return page.locator(".gd-card")


def step(page: Page, title: str, timeout: float = 30_000) -> None:
    """The guiding card titled `title` shows, its fade ended (for the screenshots), and it
    names what it highlights shortly, not by all of its words."""
    expect(card(page).get_by_role("heading", level=2)).to_have_text(title, timeout=timeout)
    faded_in(page)
    named = card(page).get_by_text("Highlighted: ")
    if named.count():
        name = named.text_content() or ""
        assert len(name) <= len("Highlighted: ") + 40, f"{title}: {name}"


def ring_clear(page: Page, marker: str) -> None:
    """The step's dashed ring stands off its target: its line 4 px or more outside it."""
    ring, box = page.locator(".gd-ring").bounding_box(), target(page, marker).bounding_box()
    assert ring and box
    # The line is 2 px wide, drawn inside the ring's box.
    assert ring["x"] <= box["x"] - 6 and ring["y"] <= box["y"] - 6, (ring, box)
    assert ring["x"] + ring["width"] >= box["x"] + box["width"] + 6, (ring, box)


def faded_in(page: Page) -> None:
    page.wait_for_function(
        "() => !document.getAnimations()"
        ".some((a) => a.animationName === 'gd-in' && a.playState === 'running')"
    )


def target(page: Page, marker: str):
    return page.locator(f'[data-guide="{marker}"]:visible').first


def apart(a, b) -> bool:
    """The two elements' boxes do not overlap."""
    x, y = a.bounding_box(), b.bounding_box()
    assert x is not None and y is not None
    return not (
        x["x"] < y["x"] + y["width"]
        and y["x"] < x["x"] + x["width"]
        and x["y"] < y["y"] + y["height"]
        and y["y"] < x["y"] + x["height"]
    )


def looks(page: Page) -> None:
    """The step's ring is dashed, never the solid focus ring; the card draws no ring of its
    own while it has the focus; Not now is one line."""
    ring = page.locator(".gd-ring")
    assert ring.evaluate("(e) => getComputedStyle(e).outlineStyle") == "dashed"
    focused = page.evaluate("() => document.activeElement?.classList.contains('gd-card')")
    assert focused, "the card has the focus"
    assert card(page).evaluate("(e) => getComputedStyle(e).outlineStyle") == "none"
    lines = (
        card(page)
        .get_by_role("button", name="Not now")
        .evaluate(
            "(e) => { const r = document.createRange(); r.selectNodeContents(e);"
            " return new Set([...r.getClientRects()].map((b) => Math.round(b.top))).size }"
        )
    )
    assert lines == 1, f"Not now takes {lines} lines"


def walk_to_model_servers(page: Page, shot, phone: bool = False) -> None:
    """From the welcome to Model servers' Add server, passing both CLI rows."""
    expect(page.get_by_role("dialog", name="Welcome to LADO")).to_be_visible(timeout=30_000)
    faded_in(page)
    shot(page, "welcome", full_page=False)
    page.get_by_role("button", name="Show me").click()
    if phone:
        step(page, "Open the menu")
        shot(page, "open-menu", full_page=False)
        target(page, "rail-menu").click()
    step(page, "Open Settings")
    looks(page)
    shot(page, "open-settings", full_page=False)
    target(page, "rail-settings").click()
    step(page, "Open Agent CLIs")
    shot(page, "open-agent-clis", full_page=False)
    target(page, "agent-clis-link").click()
    step(page, "Claude Pro or Max, or an Anthropic API key?")
    ring_clear(page, "cli-row-claude")
    shot(page, "claude-row", full_page=False)
    card(page).get_by_role("button", name="I have neither").click()
    step(page, "A ChatGPT plan, or an OpenAI API key?")
    if phone:
        ring_follows_the_scroll(page, "cli-row-codex")
    card(page).get_by_role("button", name="I have neither").click()
    step(page, "An OpenRouter key, or a model on your computer?")
    shot(page, "model-servers-link", full_page=False)
    card(page).get_by_role("button", name="I have none of these — what should I choose?").click()
    none = page.get_by_role("dialog", name="Don't have any of these yet?")
    expect(none.get_by_role("link", name="Qwen (Alibaba Cloud) keys ↗")).to_have_attribute(
        "target", "_blank"
    )
    faded_in(page)
    shot(page, "none-of-these", full_page=False)
    none.get_by_role("button", name="Back").click()
    step(page, "An OpenRouter key, or a model on your computer?")
    target(page, "model-servers-link").click()
    step(page, "Add your server")
    assert apart(card(page), target(page, "model-servers-lead")), (
        "the card covers which servers fit"
    )


def add_the_server(page: Page, models, shot, phone: bool = False) -> None:
    """Add server, a wrong key refused, then the right one."""
    shot(page, "add-server", full_page=False)
    target(page, "model-server-add").click()
    step(page, "Name, address and key")
    form = target(page, "model-server-form")
    form.get_by_label("Name").fill("Lab")
    form.get_by_label("Address").fill(models.url)
    key = form.get_by_label("Key", exact=True)
    expect(form.get_by_text("required by this server")).to_be_visible(timeout=30_000)
    if phone:
        # A phone's card keeps short (in CI the line under Not now made it cover Add server).
        expect(card(page).locator(".gd-again")).to_be_hidden()
        # The form grew under the card, with no scroll by the person: Key and Add show.
        add = form.get_by_role("button", name="Add server", exact=True)
        for _ in range(40):
            if apart(card(page), add) and apart(card(page), key):
                break
            page.wait_for_timeout(50)
        shot(page, "server-form", full_page=False)
        assert apart(card(page), add), (card(page).bounding_box(), add.bounding_box())
        assert apart(card(page), key), "the card covers Key"
        expect(form.get_by_label("Address")).to_be_in_viewport()
    key.fill("wrong-key")
    form.get_by_role("button", name="Check key").click()
    step(page, "The key wasn't accepted")
    shot(page, "key-refused", full_page=False)
    key.fill(KEY)
    form.get_by_role("button", name="Check key").click()
    step(page, "Name, address and key")
    add = form.get_by_role("button", name="Add server", exact=True)
    expect(add).to_be_enabled(timeout=30_000)
    add.click()
    # A server saved is no model yet: its model, ticked for an agent CLI, is.
    step(page, "Choose a model")
    expect(card(page).locator(".gd-done")).to_have_count(0)
    shot(page, "model-pick", full_page=False)
    target(page, "model-list").get_by_role("button", name="qwen3-8b").click()
    step(page, "Tick the agent CLIs that run it")
    # The ring stays on what shows of the ticks, inside the list that scrolls them.
    ring, models = (
        page.locator(".gd-ring").bounding_box(),
        target(page, "model-list").bounding_box(),
    )
    assert ring and models and ring["y"] + ring["height"] <= models["y"] + models["height"] + 8
    shot(page, "model-clis", full_page=False)
    tick = target(page, "model-clis").get_by_role("checkbox", name="qwen3-8b on OpenCode")
    tick.click()  # saved by the server, then ticked
    expect(tick).to_be_checked(timeout=30_000)


def set_the_author(page: Page, shot) -> None:
    step(page, "Who signs the work?")
    ring_clear(page, "author-row")
    shot(page, "author-set", full_page=False)
    target(page, "author-row").get_by_role("button", name="Set LADO's author").click()
    step(page, "Your name and email")
    form = target(page, "author-form")
    form.get_by_label("Name").fill("Ann Lee")
    form.get_by_label("Email").fill("ann@example.com")
    form.get_by_role("button", name="Save author").click()


def ring_follows_the_scroll(page: Page, marker: str) -> None:
    """The ring stays on its target when what holds it scrolls."""
    page.evaluate(
        """(marker) => {
            const row = document.querySelector(`[data-guide="${marker}"]`);
            for (let box = row.parentElement; box; box = box.parentElement)
                if (box.scrollHeight > box.clientHeight + 40) { box.scrollTop += 40; break; }
            window.scrollBy(0, 40);
        }""",
        marker,
    )
    row, ring = target(page, marker), page.locator(".gd-ring")
    expect(ring).to_be_visible()

    def lined_up() -> bool:
        a, b = row.bounding_box(), ring.bounding_box()
        return a is not None and b is not None and abs((a["y"] - 6) - b["y"]) < 2

    page.wait_for_function("() => true")  # one frame for the guide's refresh
    for _ in range(50):
        if lined_up():
            break
        page.wait_for_timeout(50)
    assert lined_up(), (row.bounding_box(), ring.bounding_box())


def test_the_main_path_on_a_fresh_lado(browser: Browser, fresh, models, server, shot):
    context = browser.new_context(viewport={"width": 1440, "height": 900})
    try:
        page = context.new_page()
        log_in(page, server)
        walk_to_model_servers(page, shot)
        add_the_server(page, models, shot)
        step(page, "Sign the agents' work")
        expect(
            card(page).get_by_text("✓ Model saved — agents check it when they start")
        ).to_be_visible()
        expect(card(page).get_by_text("Sign your work · Step 2 of 3")).to_be_visible()
        shot(page, "git-servers-link", full_page=False)
        target(page, "git-servers-link").click()
        set_the_author(page, shot)
        step(page, "Start your first session")
        expect(card(page).get_by_text("✓ Your work will be signed")).to_be_visible()
        assert apart(card(page), target(page, "author-row")), "the card covers the author"
        shot(page, "new-session", full_page=False)
        target(page, "rail-new-session").click()
        tip = page.get_by_role("region", name="Tip")
        expect(tip).to_contain_text("Describe the task here in your own words.")
        expect(page.locator(".gd-card:not(.tip)")).to_have_count(0)
        faded_in(page)
        shot(page, "tip-launch", full_page=False)
        tip.get_by_role("button", name="Got it").click()
        expect(tip).to_have_count(0)
        page.keyboard.press("Escape")  # the New session window

        page.reload()
        expect(page.get_by_role("navigation", name="Sections", exact=True)).to_be_visible()
        page.wait_for_timeout(1500)
        expect(card(page)).to_have_count(0)

        page.get_by_role("button", name="Help", exact=True).click()
        page.get_by_role("menuitem", name="Getting started").click()
        expect(page.get_by_role("dialog", name="Welcome to LADO")).to_be_visible()
        page.get_by_role("button", name="Show me").click()
        step(page, "Start your first session")
        shot(page, "restarted", full_page=False)
        # Closed on a LADO with a model and an author: it comes back on no later page load.
        page.keyboard.press("Escape")
        expect(card(page)).to_have_count(0)
        page.reload()
        expect(page.get_by_role("navigation", name="Sections", exact=True)).to_be_visible()
        page.wait_for_timeout(1500)
        expect(card(page)).to_have_count(0)
    finally:
        context.close()


def test_by_keyboard_esc_closes_the_step_after_its_target_is_pressed(
    browser: Browser, fresh, server
):
    """A step done with the keyboard (Tab to the rail's Settings, Enter) leaves the focus
    where Esc still reaches the next card: Not now, the focus not lost to the page."""
    context = browser.new_context(viewport={"width": 1440, "height": 900})
    try:
        page = context.new_page()
        log_in(page, server)
        expect(page.get_by_role("dialog", name="Welcome to LADO")).to_be_visible(timeout=30_000)
        page.keyboard.press("Enter")  # Show me has the focus
        step(page, "Open Settings")
        settings = target(page, "rail-settings")
        for _ in range(10):
            if settings.evaluate("(link) => link === document.activeElement"):
                break
            page.keyboard.press("Tab")
        expect(settings).to_be_focused()
        page.keyboard.press("Enter")
        step(page, "Open Agent CLIs")
        looks(page)  # the focus came by keyboard: the card still draws no second ring
        page.keyboard.press("Escape")
        expect(card(page)).to_have_count(0)
        assert page.evaluate("() => document.activeElement !== document.body")
        # Closed for good, though no model is connected: only Getting started brings it back.
        page.reload()
        expect(page.get_by_role("navigation", name="Sections", exact=True)).to_be_visible()
        page.wait_for_timeout(1500)
        expect(card(page)).to_have_count(0)
        page.get_by_role("button", name="Help", exact=True).click()
        page.get_by_role("menuitem", name="Getting started").click()
        expect(page.get_by_role("dialog", name="Welcome to LADO")).to_be_visible()
    finally:
        context.close()


def test_the_main_path_on_a_phone(browser: Browser, fresh, models, server, shot):
    context = browser.new_context(
        viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True
    )
    try:
        page = context.new_page()
        log_in(page, server)
        walk_to_model_servers(page, shot, phone=True)
        add_the_server(page, models, shot, phone=True)
        step(page, "Back to Settings")
        shot(page, "settings-back", full_page=False)
        target(page, "settings-back").click()
        step(page, "Sign the agents' work")
        target(page, "git-servers-link").click()
        set_the_author(page, shot)
        step(page, "Open the menu")
        target(page, "rail-menu").click()
        step(page, "Start your first session")
        shot(page, "new-session", full_page=False)
        target(page, "rail-new-session").click()
        expect(page.get_by_role("region", name="Tip")).to_be_visible()
        faded_in(page)
        shot(page, "tip-launch", full_page=False)
    finally:
        context.close()
