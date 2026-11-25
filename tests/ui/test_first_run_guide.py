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
    """The guiding card titled `title` shows, its fade ended (for the screenshots)."""
    expect(card(page).get_by_role("heading", level=2)).to_have_text(title, timeout=timeout)
    faded_in(page)


def faded_in(page: Page) -> None:
    page.wait_for_function(
        "() => !document.getAnimations()"
        ".some((a) => a.animationName === 'gd-in' && a.playState === 'running')"
    )


def target(page: Page, marker: str):
    return page.locator(f'[data-guide="{marker}"]:visible').first


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
    shot(page, "open-settings", full_page=False)
    target(page, "rail-settings").click()
    step(page, "Open Agent CLIs")
    shot(page, "open-agent-clis", full_page=False)
    target(page, "agent-clis-link").click()
    step(page, "Claude Pro or Max, or an Anthropic API key?")
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


def add_the_server(page: Page, models, shot) -> None:
    """Add server, a wrong key refused, then the right one."""
    shot(page, "add-server", full_page=False)
    target(page, "model-server-add").click()
    step(page, "Name, address and key")
    form = target(page, "model-server-form")
    form.get_by_label("Name").fill("Lab")
    form.get_by_label("Address").fill(models.url)
    key = form.get_by_label("Key", exact=True)
    expect(form.get_by_text("required by this server")).to_be_visible(timeout=30_000)
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


def set_the_author(page: Page, shot) -> None:
    step(page, "Who signs the work?")
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
        return a is not None and b is not None and abs((a["y"] - 4) - b["y"]) < 2

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
        expect(card(page).get_by_text("✓ Model connected")).to_be_visible()
        expect(card(page).get_by_text("Sign your work · Step 2 of 3")).to_be_visible()
        shot(page, "git-servers-link", full_page=False)
        target(page, "git-servers-link").click()
        set_the_author(page, shot)
        step(page, "Start your first session")
        expect(card(page).get_by_text("✓ Your work will be signed")).to_be_visible()
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
        add_the_server(page, models, shot)
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
