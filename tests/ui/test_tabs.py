"""The UI's tabs in a browser: the session's sections, the terminals and the Kits page show
one look (docs/design/ui.md, Look), in the light and the dark theme; the selected tab
stands on its band's line and covers it, and no band scrolls up and down."""

import agent_helpers
import pytest
from playwright.sync_api import Page, expect
from test_main_screen import log_in, running_session

from lado import runtime, state

pytestmark = pytest.mark.ui

# What the selected tab looks like, its mark (::before) and its band.
LOOK = """(tab) => {
  const style = getComputedStyle(tab);
  const mark = getComputedStyle(tab, "::before");
  const bar = tab.closest(".tab-bar");
  const box = tab.getBoundingClientRect();
  const hit = document.elementFromPoint(box.left + box.width / 2, box.bottom - 1);
  return {
    look: {
      font: [style.fontFamily, style.fontSize, style.fontWeight, style.color],
      padding: style.padding,
      height: box.height,
      ground: style.backgroundColor,
      frame: [style.borderTopColor, style.borderLeftColor, style.borderRightColor],
      mark: [mark.content, mark.backgroundColor, mark.height],
      band: [getComputedStyle(bar).backgroundColor, getComputedStyle(bar).boxShadow],
    },
    onLine: box.bottom === bar.getBoundingClientRect().bottom,
    covers: tab.contains(hit),
    scrolls: bar.scrollHeight !== bar.clientHeight,
  };
}"""

# A tab not selected stands on the band's line too, and leaves it seen: no ground of its
# own, or (the pinned terminal tab, opaque) the line drawn at its bottom.
PLAIN = """(tab) => {
  const style = getComputedStyle(tab);
  const bar = tab.closest(".tab-bar");
  return {
    onLine: tab.getBoundingClientRect().bottom === bar.getBoundingClientRect().bottom,
    lineSeen: style.backgroundColor === "rgba(0, 0, 0, 0)"
      || style.backgroundImage.startsWith("linear-gradient"),
  };
}"""


def looks(page: Page) -> dict:
    return {
        "session": page.locator(".session-tabs .tab-item[aria-current=page]").evaluate(LOOK),
        "terminal": page.locator(".term-tab[data-active]").evaluate(LOOK),
    }


def test_the_session_terminal_and_kits_tabs_look_the_same(page: Page, server, repo, shot):
    session = running_session(repo)
    runtime.spawn_worker(session, "sleep 0", name="w1")
    agent_helpers.wait_for(
        lambda: state.get_agent(session, "w1").status == state.IDLE, "w1 idle", session
    )
    log_in(page, server)
    page.goto(f"{server['url']}/sessions/{session}/agents/w1")
    page.get_by_role("region", name="Agent w1").get_by_role("button", name="Open terminal").click()
    panel = page.get_by_role("complementary", name="Terminals")
    expect(panel.get_by_role("tab", name="w1, idle")).to_have_attribute("aria-selected", "true")
    sections = page.get_by_role("navigation", name="Session sections")
    expect(sections.get_by_role("link", name="Agents · 2")).to_have_attribute(
        "aria-current", "page"
    )

    seen = {}
    for theme in ("light", "dark"):
        page.emulate_media(color_scheme=theme)
        found = looks(page)
        assert found["session"]["look"] == found["terminal"]["look"], theme
        for place, tab in found.items():
            assert tab["onLine"] and tab["covers"] and not tab["scrolls"], (theme, place)
        mark = found["session"]["look"]["mark"]
        assert mark[0] == '""' and mark[2] == "2px", mark
        assert found["session"]["look"]["ground"] != found["session"]["look"]["band"][0]
        assert "inset" in found["session"]["look"]["band"][1]
        for plain in (
            sections.get_by_role("link", name="Activity"),
            panel.locator(".term-tab", has=page.get_by_role("tab", name="supervisor, idle")),
        ):
            assert plain.evaluate(PLAIN) == {"onLine": True, "lineSeen": True}, theme
        bands = page.locator(".terminals-bar").evaluate(
            "(band) => [getComputedStyle(band).boxShadow, band.scrollHeight === band.clientHeight]"
        )
        assert "inset" in bands[0] and bands[1], theme
        seen[theme] = found["session"]["look"]
        shot(page, f"session-{theme}")
    assert seen["light"]["ground"] != seen["dark"]["ground"]

    page.goto(f"{server['url']}/kits/installed")
    kits = page.get_by_role("navigation", name="Kits")
    expect(kits.get_by_role("link", name="Installed 1")).to_have_attribute("aria-current", "page")
    for theme in ("light", "dark"):
        page.emulate_media(color_scheme=theme)
        tab = kits.locator(".tab-item[aria-current=page]").evaluate(LOOK)
        assert tab["look"] == seen[theme], theme
        assert tab["onLine"] and tab["covers"] and not tab["scrolls"], theme
        shot(page, f"kits-{theme}")
