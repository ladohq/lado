"""A lost connection in a browser (docs/design/ui.md, A lost connection): a real server goes
away and comes back on its port. The mark says so after 2 s, the buttons that write wait, and
an action without an answer is settled by what LADO reads once it can."""

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
from playwright.sync_api import Page, Route, expect
from test_gates import gated_session, waiting_card
from test_main_screen import log_in, running_session

from lado import runs, runtime, state
from lado.server import run as server_run

sys.path.insert(0, str(Path(__file__).parent.parent / "integration"))
import fake_provider  # noqa: E402

pytestmark = pytest.mark.ui

RAW = re.compile("TypeError|Failed to fetch")


@pytest.fixture(autouse=True)
def wide(page: Page):
    page.set_viewport_size({"width": 1440, "height": 900})


@pytest.fixture
def again(server, tmp_path):
    """Starts the server again on its port, after `server_run.stop()`; stopped after the test."""
    started = []

    def start():
        with open(tmp_path / "server-again.out", "w") as out:
            started.append(
                subprocess.Popen(
                    [
                        sys.executable,
                        str(fake_provider.LADO),
                        "server",
                        "--port",
                        str(server["port"]),
                    ],
                    stdout=out,
                    stderr=subprocess.STDOUT,
                    env=os.environ,
                )
            )
        server_run.wait_ready()

    yield start
    server_run.stop()
    for process in started:
        process.wait(timeout=10)


def in_chat(page: Page, server, session: str):
    log_in(page, server)
    page.goto(f"{server['url']}/sessions/{session}/activity")
    return waiting_card(page, session)


def button(place, name: str):
    return place.get_by_role("button", name=name, exact=True)


def lost_mark(page: Page):
    return page.locator(".link.reconnecting")


def no_raw_text(page: Page) -> None:
    assert not RAW.search(page.locator("body").inner_text())


def test_the_mark_says_it_after_2_s_and_goes_when_the_server_is_back(
    page: Page, server, again, shot
):
    log_in(page, server)
    bar = page.get_by_role("banner")
    status = bar.get_by_role("status")
    expect(status).to_have_text("live")
    server_run.stop()
    page.wait_for_timeout(1000)
    expect(lost_mark(page)).to_have_count(0)  # a shorter drop shows nothing
    expect(status).to_have_text("live")
    expect(lost_mark(page)).to_have_text("reconnecting…")
    expect(status).to_have_text("reconnecting…")
    colours = lost_mark(page).evaluate(
        "mark => [getComputedStyle(mark).color, getComputedStyle(mark).backgroundColor]"
    )
    assert colours == ["rgb(138, 90, 0)", "rgb(253, 245, 220)"]  # --warn on --warn-ground
    shot(page, "lost")
    page.set_viewport_size({"width": 390, "height": 844})
    expect(lost_mark(page).locator("svg")).to_be_visible()
    expect(lost_mark(page).locator(".link-word")).to_have_css("width", "1px")  # for the ear
    shot(page, "lost-phone")
    page.set_viewport_size({"width": 1440, "height": 900})
    again()
    expect(button(page, "System")).to_have_text("live", timeout=15000)
    expect(lost_mark(page)).to_have_count(0)
    expect(status).to_have_text("live")
    shot(page, "back")


def test_while_lost_the_buttons_wait_everywhere_and_the_fields_stay(
    page: Page, server, again, repo, shot
):
    session = gated_session(repo)
    card = in_chat(page, server, session)
    comment = card.get_by_role("textbox")
    comment.fill("Ship the login page first.")
    draft = page.get_by_role("textbox", name="Write to the supervisor…")
    draft.fill("Check the login form too")
    server_run.stop()
    expect(lost_mark(page)).to_be_visible()
    expect(button(card, "Approve")).to_be_disabled()
    expect(button(card, "Reject")).to_be_disabled()
    expect(card.get_by_text("Waiting for connection")).to_be_visible()
    send = button(page, "Send")
    expect(send).to_be_disabled()
    expect(button(page, "Stop session…")).to_be_disabled()
    send.hover(force=True)
    expect(page.get_by_role("tooltip")).to_have_text("Waiting for connection")
    expect(send.locator("..")).to_have_css("cursor", "not-allowed")
    shot(page, "chat")
    page.emulate_media(color_scheme="dark")
    shot(page, "chat-dark")
    page.emulate_media(color_scheme="light")
    draft.press("Enter")
    expect(draft).to_have_value("Check the login form too")
    comment.fill("Ship the login page first, then the rest.")
    expect(comment).to_have_value("Ship the login page first, then the rest.")


def test_a_gate_on_needs_you_waits_with_its_comment_and_wakes(
    page: Page, server, again, repo, shot
):
    session = gated_session(repo)
    log_in(page, server)
    page.goto(f"{server['url']}/needs-you")  # loaded before the loss: away, it cannot load
    needs = page.get_by_role("region", name=f"What waits for you in {session}")
    expect(button(needs, "Approve")).to_be_enabled()
    comment = needs.get_by_role("textbox")
    comment.fill("Ship the login page first.")
    server_run.stop()
    expect(lost_mark(page)).to_be_visible()
    expect(button(needs, "Approve")).to_be_disabled()
    note = needs.get_by_text("Waiting for connection")
    expect(note).to_be_visible()
    expect(note).to_have_css("font-size", "13px")
    expect(comment).to_have_value("Ship the login page first.")
    shot(page, "needs-you")
    page.emulate_media(color_scheme="dark")
    shot(page, "needs-you-dark")
    again()
    expect(button(needs, "Approve")).to_be_enabled(timeout=15000)
    expect(note).to_have_count(0)
    expect(comment).to_have_value("Ship the login page first.")


def test_needs_you_opened_while_away_says_no_connection_and_loads_when_back(
    page: Page, server, again, repo, shot
):
    session = gated_session(repo)
    log_in(page, server)
    page.goto(f"{server['url']}/sessions/{session}/activity")
    expect(button(waiting_card(page, session), "Approve")).to_be_enabled()
    server_run.stop()
    expect(lost_mark(page)).to_be_visible()
    page.get_by_role("navigation", name="Sections").get_by_role("link", name="Needs you").click()
    expect(page.get_by_text("No connection")).to_be_visible()
    no_raw_text(page)
    shot(page, "no-connection")
    again()
    expect(button(waiting_card(page, session), "Approve")).to_be_enabled(timeout=15000)
    expect(page.get_by_text("No connection")).to_have_count(0)


def test_a_gate_on_its_runs_page_waits_too(page: Page, server, again, repo, shot):
    session = gated_session(repo)
    log_in(page, server)
    page.goto(f"{server['url']}/sessions/{session}/flows/ship%2Fx")
    run = page.get_by_role("region", name="Run ship/x")
    expect(button(run, "Approve")).to_be_enabled()
    server_run.stop()
    expect(button(run, "Approve")).to_be_disabled()
    note = run.get_by_text("Waiting for connection")
    expect(note).to_be_visible()
    expect(note).to_have_css("font-size", "13px")
    expect(note).to_have_css("align-self", "center")
    shot(page, "run-page")


def test_what_waits_for_the_human_looks_as_ever_with_the_connection_fine(page: Page, server, repo):
    """The wrapper of a button that waits has a class of its own: `waits` marks what waits for
    the human, and is no forbidden cursor."""
    session = gated_session(repo)
    log_in(page, server)
    page.goto(f"{server['url']}/sessions/{session}/flows/ship%2Fx")
    pill = page.locator(".pill.waits").first
    expect(pill).to_have_css("cursor", "auto")
    expect(pill).to_have_css("display", "block")  # in its row of flex, not a flex of its own
    expect(page.locator(".run-now.waits")).to_have_css("cursor", "auto")


def test_approve_as_the_server_goes_then_not_delivered_and_retry(
    page: Page, server, again, repo, shot
):
    session = gated_session(repo)
    [gate] = state.open_gates(session)
    card = in_chat(page, server, session)
    expect(button(card, "Approve")).to_be_enabled()
    server_run.stop()
    button(card, "Approve").click()
    alert = card.get_by_role("alert")
    expect(alert).to_contain_text("Approval not confirmed")
    expect(button(alert, "Retry")).to_be_disabled()
    no_raw_text(page)
    expect(lost_mark(page)).to_be_visible()
    shot(page, "not-confirmed")
    page.emulate_media(color_scheme="dark")
    shot(page, "not-confirmed-dark")
    page.set_viewport_size({"width": 390, "height": 844})
    expect(alert).to_contain_text("Approval not confirmed")
    shot(page, "not-confirmed-phone-dark")
    page.emulate_media(color_scheme="light")
    shot(page, "not-confirmed-phone")
    page.set_viewport_size({"width": 1440, "height": 900})

    again()
    expect(alert).to_contain_text("Approval not delivered", timeout=15000)
    expect(button(alert, "Retry")).to_be_enabled()
    expect(button(card, "Approve")).to_be_enabled()
    expect(button(card, "Reject")).to_be_enabled()
    shot(page, "not-delivered")
    page.emulate_media(color_scheme="dark")
    shot(page, "not-delivered-dark")
    button(alert, "Retry").click()
    expect(card).to_have_count(0)
    assert state.get_gate(gate.id).answer == "approve"


def test_approve_that_someone_else_gave_while_away_ends_with_no_error(
    page: Page, server, again, repo, shot
):
    session = gated_session(repo)
    card = in_chat(page, server, session)
    expect(button(card, "Approve")).to_be_enabled()
    server_run.stop()
    button(card, "Reject").click()
    expect(card.get_by_role("alert")).to_contain_text("Rejection not confirmed")
    runs.answer(session, "ship/x", "approve")
    again()
    expect(card).to_have_count(0, timeout=15000)
    expect(page.get_by_role("alert")).to_have_count(0)
    shot(page, "closed")


def lose(page: Page, path: str) -> None:
    """The server gets no request of `path`: the browser's fetch fails, the feed stays."""
    page.route(
        path, lambda route: route.abort() if route.request.method == "POST" else route.continue_()
    )


def test_the_same_error_on_the_gates_run_page_and_another_decision(page: Page, server, repo, shot):
    session = gated_session(repo)
    [gate] = state.open_gates(session)
    card = in_chat(page, server, session)
    lose(page, "**/gates/*/answer")
    button(card, "Approve").click()
    alert = card.get_by_role("alert")
    expect(alert).to_contain_text("Approval not delivered")
    page.get_by_role("navigation", name="Session sections").get_by_role(
        "link", name="Flows"
    ).click()
    page.get_by_role("link", name="ship/x").first.click()
    run = page.get_by_role("region", name="Run ship/x")
    expect(run.get_by_role("alert")).to_contain_text("Approval not delivered")
    shot(page, "run-page")
    page.unroute("**/gates/*/answer")
    button(run, "Reject").click()
    expect(run.get_by_role("alert")).to_have_count(0)
    expect(button(run, "Reject")).to_have_count(0)
    assert state.get_gate(gate.id).answer == "reject"


def test_a_retry_on_a_gate_closed_meanwhile_shows_no_error(page: Page, server, repo, shot):
    session = gated_session(repo)
    card = in_chat(page, server, session)
    lose(page, "**/gates/*/answer")
    button(card, "Approve").click()
    alert = card.get_by_role("alert")
    expect(alert).to_contain_text("Approval not delivered")
    page.unroute("**/gates/*/answer")

    def closed_first(route: Route) -> None:
        runs.answer(session, "ship/x", "approve")
        route.continue_()  # the server refuses it: closed already

    page.route("**/gates/*/answer", closed_first)
    button(alert, "Retry").click()
    expect(card).to_have_count(0)
    expect(page.get_by_role("alert")).to_have_count(0)


def test_send_answered_with_its_answer_lost_makes_no_duplicate(page: Page, server, repo, shot):
    session = running_session(repo)
    log_in(page, server)
    page.goto(f"{server['url']}/sessions/{session}/activity")
    field = page.get_by_role("textbox", name="Write to the supervisor…")
    expect(field).to_be_enabled()

    def taken_then_lost(route: Route) -> None:
        if route.request.method != "POST":
            route.continue_()
            return
        route.fetch()
        route.abort()

    page.route("**/messages", taken_then_lost)
    field.fill("reach the server once")
    field.press("Enter")
    expect(field).to_have_value("")
    expect(page.get_by_role("alert")).to_have_count(0)
    mine = page.get_by_role("article", name="Message from you")
    expect(mine).to_have_count(1)
    shot(page, "one-message")


def test_send_that_never_arrived_says_so_and_retry_sends_it(page: Page, server, repo, shot):
    session = running_session(repo)
    log_in(page, server)
    page.goto(f"{server['url']}/sessions/{session}/activity")
    field = page.get_by_role("textbox", name="Write to the supervisor…")
    lose(page, "**/messages")
    field.fill("say it")
    field.press("Enter")
    alert = page.get_by_role("alert")
    expect(alert).to_contain_text("Message not delivered")
    expect(field).to_have_value("say it")
    shot(page, "message")
    page.emulate_media(color_scheme="dark")
    shot(page, "message-dark")
    page.unroute("**/messages")
    button(alert, "Retry").click()
    expect(field).to_have_value("")
    expect(page.get_by_role("article", name="Message from you")).to_have_count(1)


def test_send_answer_without_an_answer(page: Page, server, repo, shot):
    session = running_session(repo)
    runtime.ask_human(session, "supervisor", "Merge w1 now?", "Tests pass.", ["yes", "later"])
    card = in_chat(page, server, session)
    button(card, "yes").click()
    lose(page, "**/answers")
    button(card, "Send answer to supervisor").click()
    alert = card.get_by_role("alert")
    expect(alert).to_contain_text("Answer not delivered")
    shot(page, "answer")
    page.unroute("**/answers")
    button(alert, "Retry").click()
    expect(card).to_have_count(0)


def test_stop_without_an_answer(page: Page, server, repo, shot):
    session = running_session(repo)
    log_in(page, server)
    page.goto(f"{server['url']}/sessions/{session}/activity")
    button(page, "Stop session…").click()
    popover = page.get_by_role("dialog", name=f'Stop session "{session}"?')
    stop = button(popover, f"Stop {session}")
    expect(stop).to_be_enabled()
    lose(page, "**/stop")
    stop.click()
    alert = popover.get_by_role("alert")
    expect(alert).to_contain_text("Stop not delivered")
    shot(page, "stop")
    page.emulate_media(color_scheme="dark")
    shot(page, "stop-dark")
    page.unroute("**/stop")
    button(alert, "Retry").click()
    expect(popover).to_have_count(0)
    assert state.get_session(session).stopped_at


def test_resume_without_an_answer(page: Page, server, repo, shot):
    session = running_session(repo)
    runtime.stop_session(session)
    log_in(page, server)
    page.goto(f"{server['url']}/sessions/{session}/activity")
    button(page, "Resume…").click()
    window = page.get_by_role("dialog", name="Resume session")
    resume = button(window, "Resume session")
    expect(resume).to_be_enabled()
    lose(page, "**/resume")
    resume.click()
    alert = window.get_by_role("alert")
    expect(alert).to_contain_text("Resume not delivered")
    shot(page, "resume")
    page.emulate_media(color_scheme="dark")
    shot(page, "resume-dark")
    page.unroute("**/resume")
    button(alert, "Retry").click()
    expect(window).to_have_count(0)
    expect(page).to_have_url(f"{server['url']}/sessions/{session}/activity")


def test_a_page_opened_while_away_says_no_connection_and_loads_when_back(
    page: Page, server, again, repo, shot
):
    session = running_session(repo)
    log_in(page, server)
    page.goto(f"{server['url']}/sessions/{session}/activity")
    expect(page.get_by_role("textbox", name="Write to the supervisor…")).to_be_visible()
    server_run.stop()
    expect(lost_mark(page)).to_be_visible()
    page.get_by_role("navigation", name="Session sections").get_by_role(
        "link", name="Flows"
    ).click()
    expect(page.get_by_text("No connection").first).to_be_visible()
    no_raw_text(page)
    shot(page, "no-connection")
    again()
    expect(page.get_by_text("No active runs")).to_be_visible(timeout=15000)
    expect(page.get_by_text("No connection")).to_have_count(0)
