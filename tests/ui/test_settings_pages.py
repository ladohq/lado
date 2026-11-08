"""Settings' pages in a browser (openspec change settings-pages; docs/design/ui.md, Settings):
General, Agent CLIs, Model servers and Statistics beside the list of sections at 1440 and 768,
the list alone then a page at 390, in the light and the dark theme; no page scrolls sideways,
a phone's controls are 44 px high and no picked model's name is cut. The old addresses land on
their pages in place of the history entry, and Help's menu opens beside the rail and in the
phone's drawer. The arrival at a CLI's row: test_providers_section.py, test_launch.py."""

import re

import pytest
import test_models_section as models
from playwright.sync_api import Browser, Page, expect
from test_main_screen import log_in

from lado import state

pytestmark = pytest.mark.ui

# The model settings' fixtures: the four CLIs on the server's PATH, the fake LM Studio.
clis = models.clis
lms = models.lms

PAGES = {
    "general": "General",
    "agent-clis": "Agent CLIs",
    "model-servers": "Model servers",
    "statistics": "Statistics",
}
SIZES = {"computer": (1440, 900), "tablet": (768, 1024), "phone": (390, 844)}


@pytest.fixture
def saved(lms):
    """A server, a model on it, and that model as OpenCode's default: each page has its rows."""
    state.add_model_server("s1", "lmstudio", lms.url, "LM Studio", [models.CHAT])
    model = state.add_model("qwen3-8b · lmstudio", "opencode", "qwen3-8b", "s1")
    state.set_cli_default(state.ModelRef("opencode", model.id, None))


def no_sideways_scroll(page: Page) -> None:
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), page.url


def no_name_cut(page: Page) -> None:
    cut = page.evaluate(
        "[...document.querySelectorAll('.model-pick .mp-title')]"
        ".filter((e) => e.scrollWidth > e.clientWidth + 1).map((e) => e.textContent)"
    )
    assert cut == [], cut


def dot_on_first_line(page: Page) -> None:
    """A CLI's login dot stands on the first line of its state, also when the state wraps (a
    long one, as Codex's `Logged in · ChatGPT plan · Codex's login file` at 768)."""
    states = page.evaluate(
        """() => [...document.querySelectorAll('.pv-state')].map((state) => {
          const nodes = [...state.childNodes];
          const text = nodes.find((n) => n.nodeType === 3 || n.tagName === 'STRONG');
          state.append(' · a state long enough to wrap onto a second line at 768 px wide');
          const range = document.createRange();
          range.selectNodeContents(text);
          const first = range.getClientRects()[0];
          const dot = state.querySelector('.dot').getBoundingClientRect();
          const middle = dot.top + dot.height / 2;
          const wraps = state.getBoundingClientRect().height > first.height * 1.5;
          const on = middle >= first.top && middle <= first.bottom;
          return { text: state.textContent, on, wraps };
        })"""
    )
    assert [one for one in states if not one["on"]] == [], states
    if page.viewport_size["width"] <= 900:
        assert any(one["wraps"] for one in states), states  # the case was there to see
    page.reload()  # the rows as the page draws them
    expect(page.locator(".pv-refresh.spinning")).to_have_count(0, timeout=30_000)


# A phone's controls, 44 px high; inline text links are exempt.
TARGETS = (
    ".settings button, .settings .snav-item, .settings .back-link, .settings .sw-hit,"
    " .settings .choice label, .settings .model-pick"
)


def phone_targets(page: Page) -> None:
    small = page.evaluate(
        f"[...document.querySelectorAll({TARGETS!r})]"
        ".filter((e) => e.getClientRects().length && e.offsetParent !== null)"
        ".map((e) => [e.textContent.trim() || e.getAttribute('aria-label'),"
        " e.getBoundingClientRect().height])"
        ".filter(([, h]) => h < 44)"
    )
    assert small == [], small


@pytest.mark.parametrize("theme", ["light", "dark"])
@pytest.mark.parametrize("size", ["computer", "tablet"])
def test_each_page_beside_the_list(browser: Browser, clis, saved, server, shot, size, theme):
    width, height = SIZES[size]
    context = browser.new_context(viewport={"width": width, "height": height}, color_scheme=theme)
    try:
        page = context.new_page()
        log_in(page, server)
        page.goto(f"{server['url']}/settings")
        expect(page).to_have_url(f"{server['url']}/settings/general")  # a computer opens General
        sections = page.get_by_role("navigation", name="Settings sections")
        expect(sections.get_by_role("link")).to_have_text(list(PAGES.values()))
        tops = {}
        for slug, name in PAGES.items():
            sections.get_by_role("link", name=name).click()
            expect(page).to_have_url(f"{server['url']}/settings/{slug}")
            heading = page.get_by_role("heading", name=name, exact=True, level=2)
            if slug != "general":  # General is already open: no change, no focus moved
                expect(heading).to_be_focused()
            expect(sections.get_by_role("link", name=name)).to_have_attribute(
                "aria-current", "page"
            )
            if slug == "agent-clis":
                expect(page.locator(".pv-refresh.spinning")).to_have_count(0, timeout=30_000)
                expect(
                    page.get_by_role("combobox", name="Default model of OpenCode")
                ).to_contain_text("qwen3-8b · lmstudio")
                no_name_cut(page)
                dot_on_first_line(page)
            if slug == "model-servers":
                expect(page.get_by_role("table", name="Your models")).to_contain_text(
                    "OpenCode · default"
                )
            no_sideways_scroll(page)
            box = sections.bounding_box()
            assert box and box["width"] == (232 if size == "computer" else 196), box
            tops[slug] = box["y"]
            shot(page, f"{slug}-{size}-{theme}")
        # The list stands still whichever page is open, a short one too (LAD-244).
        assert len(set(tops.values())) == 1, tops
    finally:
        context.close()


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_a_phone_shows_the_list_then_a_page(browser: Browser, clis, saved, server, shot, theme):
    context = browser.new_context(
        viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True, color_scheme=theme
    )
    try:
        page = context.new_page()
        log_in(page, server)
        page.goto(f"{server['url']}/settings")
        expect(page).to_have_url(f"{server['url']}/settings")
        sections = page.get_by_role("navigation", name="Settings sections")
        expect(sections.get_by_role("link")).to_have_text(list(PAGES.values()))
        expect(page.get_by_role("heading", level=2)).to_have_count(0)  # the list alone
        phone_targets(page)
        assert all(
            box["height"] >= 52
            for box in (a.bounding_box() for a in sections.get_by_role("link").all())
        )
        shot(page, f"list-phone-{theme}", full_page=False)
        for slug, name in PAGES.items():
            sections.get_by_role("link", name=name).click()
            expect(page).to_have_url(f"{server['url']}/settings/{slug}")
            expect(page.get_by_role("heading", name=name, exact=True, level=2)).to_be_focused()
            expect(sections).to_have_count(0)  # the page alone
            if slug == "agent-clis":
                expect(page.locator(".pv-refresh.spinning")).to_have_count(0, timeout=30_000)
                expect(
                    page.get_by_role("combobox", name="Default model of OpenCode")
                ).to_be_visible()
                no_name_cut(page)
            no_sideways_scroll(page)
            phone_targets(page)
            shot(page, f"{slug}-phone-{theme}")
            page.get_by_role("link", name="Settings", exact=True).filter(has_text="‹").click()
            expect(page).to_have_url(f"{server['url']}/settings")
    finally:
        context.close()


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("/settings#providers-and-environment", "/settings/agent-clis"),
        ("/settings#models", "/settings/model-servers"),
        ("/settings#statistics", "/settings/statistics"),
        ("/settings#notifications", "/settings/general#notifications"),
        ("/settings#appearance", "/settings/general"),
        ("/settings/agent-clis-and-environment", "/settings/agent-clis"),
        ("/settings/models", "/settings/model-servers"),
        ("/settings/usage-statistics", "/settings/statistics"),
        ("/settings/kits", "/settings/general"),  # /settings, which a computer opens as General
    ],
)
def test_an_old_address_lands_on_its_page_in_place_of_its_entry(page: Page, server, old, new):
    page.set_viewport_size({"width": 1440, "height": 900})
    log_in(page, server)
    page.goto(f"{server['url']}/sessions")
    before = page.evaluate("history.length")
    page.evaluate(
        f"history.pushState(null, '', {old!r}); dispatchEvent(new PopStateEvent('popstate'))"
    )
    expect(page).to_have_url(f"{server['url']}{new}")
    assert page.evaluate("history.length") == before + 1  # the old address's entry, replaced
    if new.endswith("#notifications"):
        expect(page.locator("#notifications")).to_be_in_viewport()
    page.go_back()
    expect(page).to_have_url(f"{server['url']}/sessions")  # Back does not loop


def test_help_beside_the_rail_and_in_the_phone_s_drawer(browser: Browser, server, shot):
    context = browser.new_context(viewport={"width": 1440, "height": 900})
    try:
        page = context.new_page()
        log_in(page, server)
        page.goto(f"{server['url']}/settings/general")
        rail = page.get_by_role("navigation", name="Sections")
        settings = rail.get_by_role("link", name="Settings")
        help_ = rail.get_by_role("button", name="Help")
        assert help_.bounding_box()["y"] < settings.bounding_box()["y"]  # above Settings
        help_.click()
        menu = page.get_by_role("menu", name="Help")
        expect(menu).to_be_in_viewport(ratio=1)
        docs = menu.get_by_role("menuitem", name="Documentation")
        expect(docs).to_have_attribute("href", "https://github.com/ladohq/lado#readme")
        expect(menu.get_by_role("menuitem", name="GitHub")).to_have_attribute(
            "href", "https://github.com/ladohq/lado"
        )
        shot(page, "help-computer", full_page=False)
        page.mouse.click(900, 450)  # a press outside closes it
        expect(menu).to_have_count(0)
    finally:
        context.close()
    phone = browser.new_context(
        viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True
    )
    try:
        page = phone.new_page()
        log_in(page, server)
        page.get_by_role("button", name=re.compile("^Menu")).click()
        drawer = page.get_by_role("navigation", name="Sections")
        drawer.get_by_role("button", name="Help").click()
        menu = drawer.get_by_role("menu", name="Help")
        items = menu.get_by_role("menuitem")
        expect(items).to_have_count(3)
        for item in items.all():
            assert item.bounding_box()["height"] >= 44
        box, rail = menu.bounding_box(), drawer.bounding_box()
        assert box["x"] >= rail["x"] and box["x"] + box["width"] <= rail["x"] + rail["width"]
        shot(page, "help-phone", full_page=False)
        menu.get_by_role("menuitem", name="Report a bug").click()
        expect(page).to_have_url(f"{server['url']}/report")
        expect(drawer).to_be_hidden()
    finally:
        phone.close()
