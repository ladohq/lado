"""An agent's status marks in a browser: busy and background (its turn ended, work it started
still runs) on the team chips and the Agents page, in the light and the dark theme, and their
pulse, which reduced motion stops."""

import agent_helpers
import pytest
from playwright.sync_api import Page, expect
from test_layout import with_worker
from test_main_screen import log_in

from lado import runtime, state

pytestmark = pytest.mark.ui

GREEN = {"light": "rgb(30, 122, 70)", "dark": "rgb(92, 201, 138)"}  # --done


def dot_style(chip, *names: str) -> list[str]:
    return [chip.locator(".dot").evaluate(f"d => getComputedStyle(d).{n}") for n in names]


def test_busy_and_background_are_green_and_pulse_and_background_is_half_filled(
    page: Page, server, repo, shot
):
    page.set_viewport_size({"width": 1440, "height": 900})
    session = with_worker(repo)
    runtime.send_message(session, "human", "w1", "background")
    agent_helpers.wait_for(
        lambda: state.get_agent(session, "w1").status == state.BACKGROUND, "w1 background", session
    )
    runtime.send_message(session, "human", "supervisor", "pause")  # busy until released
    agent_helpers.wait_for(
        lambda: agent_helpers.paused(session, "supervisor", 1), "supervisor paused", session
    )
    try:
        log_in(page, server)
        page.goto(f"{server['url']}/sessions/{session}")
        page.get_by_role("button", name="Collapse terminals").click()
        team = page.get_by_role("group", name="Team")
        supervisor, w1 = team.get_by_role("button").all()
        expect(supervisor).to_have_accessible_name("supervisor, supervisor, busy")
        expect(w1).to_have_accessible_name("w1, worker, background")
        for theme in ("light", "dark"):
            page.emulate_media(color_scheme=theme)
            green = GREEN[theme]
            assert dot_style(supervisor, "backgroundColor", "animationName") == [
                green,
                "activity-pulse",
            ]
            image, border, animation = dot_style(
                w1, "backgroundImage", "borderTopColor", "animationName"
            )
            assert image == f"linear-gradient(90deg, {green} 50%, rgba(0, 0, 0, 0) 50%)"
            assert (border, animation) == (green, "activity-pulse")
            shot(page, f"team-{theme}")
        page.emulate_media(reduced_motion="reduce")
        assert dot_style(w1, "animationName") == ["none"]
        assert dot_style(supervisor, "animationName") == ["none"]
        page.emulate_media(reduced_motion="no-preference")

        page.get_by_role("link", name="Agents · 2").click()
        agents = page.get_by_role("navigation", name="Agents")
        row = agents.get_by_role("link", name="w1")
        expect(row).to_contain_text("background")
        for theme in ("light", "dark"):
            page.emulate_media(color_scheme=theme)
            shot(page, f"agents-{theme}")
    finally:
        agent_helpers.release(session, "supervisor", 1)
