"""Selected text and copy buttons in a browser (docs/design/ui.md, Selected text and copy
buttons): the selection bar over text selected in a readable area, its Copy and its Quote
in reply into the page's composer or the session's chat; no bar in a field, an HTML
artifact or across two messages; below the selection on a touch screen."""

import pytest
from playwright.sync_api import Browser, Page, expect
from test_agents_tab import session_with_worker
from test_gates import gated_session
from test_main_screen import log_in, running_session

from lado import artifacts, runtime

pytestmark = pytest.mark.ui

# Select from `start` (a text, its first character) to the end of `end` (a text), both
# looked up in the element's text nodes; returns the selection's string.
SELECT = """(element, [start, end]) => {
  const nodes = [];
  const walk = document.createTreeWalker(element, NodeFilter.SHOW_TEXT);
  while (walk.nextNode()) nodes.push(walk.currentNode);
  const first = nodes.find((node) => node.data.includes(start));
  const last = nodes.find((node) => node.data.includes(end) && (node !== first || node.data.indexOf(end) >= node.data.indexOf(start)));
  if (!first || !last) throw new Error(`no text ${start} … ${end}`);
  const range = document.createRange();
  range.setStart(first, first.data.indexOf(start));
  range.setEnd(last, last.data.indexOf(end) + end.length);
  const selection = document.getSelection();
  selection.removeAllRanges();
  selection.addRange(range);
  return selection.toString();
}"""

BODY = "Run make lint before the push.\n\nThe bar hides on Esc."


@pytest.fixture(autouse=True)
def wide(page: Page):
    page.set_viewport_size({"width": 1280, "height": 900})


def select(locator, start: str, end: str | None = None) -> str:
    return locator.evaluate(SELECT, [start, end or start])


def bar(page: Page):
    return page.get_by_role("toolbar", name="Selection")


def talked_session(repo) -> str:
    """A running session whose supervisor wrote to the human: a summary and a body of two
    paragraphs, then a second message."""
    session = running_session(repo)
    runtime.send_message(session, "supervisor", "human", "merged w1", BODY)
    runtime.send_message(session, "supervisor", "human", "next: the docs")
    return session


def chat_page(page: Page, server, session: str):
    log_in(page, server)
    page.goto(f"{server['url']}/sessions/{session}")
    chat = page.get_by_role("log", name="Chat with the session")
    expect(chat).to_contain_text("The bar hides on Esc.")
    return chat


def test_the_bar_shows_over_a_message_and_esc_hides_it(page: Page, server, repo, shot):
    session = talked_session(repo)
    chat = chat_page(page, server, session)
    select(chat, "The bar hides on Esc")
    toolbar = bar(page)
    expect(toolbar).to_be_visible()
    expect(toolbar.get_by_role("button")).to_have_count(2)
    quote = toolbar.get_by_role("button", name="Quote in reply")
    expect(toolbar.get_by_role("button", name="Copy", exact=True)).to_be_visible()
    # Above the selection.
    selected = page.evaluate("document.getSelection().getRangeAt(0).getBoundingClientRect().top")
    box = toolbar.bounding_box()
    assert box is not None and box["y"] + box["height"] <= selected, (box, selected)
    quote.hover()
    expect(page.get_by_role("tooltip")).to_have_text("Quote in reply")
    shot(page)
    page.keyboard.press("Escape")
    expect(toolbar).to_have_count(0)


def test_copy_copies_the_selection_and_keeps_it(page: Page, server, repo, shot):
    session = talked_session(repo)
    chat = chat_page(page, server, session)
    page.context.grant_permissions(["clipboard-read", "clipboard-write"], origin=server["url"])
    page.evaluate("navigator.clipboard.writeText('stale')")
    assert select(chat, "make lint") == "make lint"
    bar(page).get_by_role("button", name="Copy", exact=True).click()
    expect(bar(page).get_by_role("status")).to_have_text("Copied")
    shot(page)
    assert page.evaluate("navigator.clipboard.readText()") == "make lint"
    assert page.evaluate("document.getSelection().toString()") == "make lint"


def test_quote_appends_to_the_chat_composer(page: Page, server, repo, shot):
    session = talked_session(repo)
    chat = chat_page(page, server, session)
    field = page.get_by_role("textbox", name="Write to the supervisor…")
    field.fill("Почему?")
    select(chat, "Run make lint", "hides on Esc.")
    bar(page).get_by_role("button", name="Quote in reply").click()
    expect(field).to_have_value(
        "Почему?\n\n> Run make lint before the push.\n>\n> The bar hides on Esc.\n"
    )
    expect(field).to_be_focused()
    assert field.evaluate("f => f.selectionStart === f.value.length")
    expect(page.locator(".composer-name")).to_have_text("supervisor")
    expect(bar(page)).to_have_count(0)
    shot(page)


def test_quote_on_an_agent_page_goes_to_its_composer(page: Page, server, repo, shot):
    session, _ = session_with_worker(repo)
    log_in(page, server)
    page.goto(f"{server['url']}/sessions/{session}/agents/w1")
    messages = page.get_by_role("region", name="Messages")
    expect(messages).to_contain_text("your task")
    select(messages, "your task")
    bar(page).get_by_role("button", name="Quote in reply").click()
    field = page.get_by_role("textbox", name="Write to w1…")
    expect(field).to_have_value("> your task\n")
    expect(field).to_be_focused()
    shot(page)


def test_quote_from_flows_opens_the_chat(page: Page, server, repo, shot):
    session = gated_session(repo)
    log_in(page, server)
    page.goto(f"{server['url']}/sessions/{session}/flows/{'ship%2Fx'}")
    note = page.locator(".feed-detail")  # the latest note with a body is open
    expect(note).to_contain_text("Split it in two, then ship.")
    note.scroll_into_view_if_needed()
    select(note, "Split it in two")
    expect(bar(page)).to_be_visible()
    shot(page, "selected")
    bar(page).get_by_role("button", name="Quote in reply").click()
    expect(page).to_have_url(f"{server['url']}/sessions/{session}/activity")
    field = page.get_by_role("textbox", name="Write to the supervisor…")
    expect(field).to_have_value("> Split it in two\n")
    expect(field).to_be_focused()
    shot(page)


PYTHON = "def quote(text):\n    lines = text.splitlines()\n    return '```'.join(lines)\n"


def test_quote_from_a_text_artifact_names_its_lines(page: Page, server, repo, shot):
    session = running_session(repo)
    artifacts.write(session, "supervisor", "notes.py", PYTHON)
    log_in(page, server)
    page.goto(f"{server['url']}/sessions/{session}/artifacts/{artifacts.find(session, 'notes.py')[0].id}")
    table = page.get_by_role("table", name="notes.py")
    expect(table).to_contain_text("splitlines")
    select(table, "lines =", "join(")
    expect(bar(page)).to_be_visible()
    shot(page, "selected")
    bar(page).get_by_role("button", name="Quote in reply").click()
    field = page.get_by_role("textbox", name="Write to the supervisor…")
    expect(field).to_have_value(
        "In notes.py (lines 2–3):\n````\nlines = text.splitlines()\n    return '```'.join(\n````\n"
    )
    shot(page)


def test_quote_from_a_markdown_artifact_in_the_panel(page: Page, server, repo, shot):
    session = running_session(repo)
    artifacts.write(session, "supervisor", "design", "# Design\n\nAC-2. Quote puts the selection.")
    record = artifacts.find(session, "design")[1].id
    log_in(page, server)
    page.goto(f"{server['url']}/sessions/{session}/activity?view={record}")
    panel = page.get_by_role("dialog", name="Artifact design")
    expect(panel).to_contain_text("AC-2.")
    select(panel.locator("article"), "AC-2. Quote puts")
    bar(page).get_by_role("button", name="Quote in reply").click()
    field = page.get_by_role("textbox", name="Write to the supervisor…")
    expect(field).to_have_value("In design:\n> AC-2. Quote puts\n")
    expect(panel).to_be_visible()  # the panel over a page with a composer stays
    shot(page)


HTML = "<!doctype html><html><body><p id='p'>inside the frame</p></body></html>"


def test_no_bar_in_the_composer_html_or_across_two_messages(page: Page, server, repo, shot):
    session = talked_session(repo)
    artifacts.write(session, "supervisor", "page.html", HTML)
    chat = chat_page(page, server, session)
    select(chat, "The bar hides", "the docs")
    page.wait_for_timeout(200)  # a frame for the bar's look
    expect(bar(page)).to_have_count(0)
    field = page.get_by_role("textbox", name="Write to the supervisor…")
    field.fill("my own words")
    field.evaluate("f => { f.focus(); f.setSelectionRange(0, 6); }")
    page.wait_for_timeout(200)
    expect(bar(page)).to_have_count(0)
    record = artifacts.find(session, "page.html")[1].id
    page.goto(f"{server['url']}/sessions/{session}/activity?view={record}")
    frame = page.frame_locator("iframe[title='page.html']")
    expect(frame.locator("#p")).to_have_text("inside the frame")
    frame.locator("#p").evaluate(SELECT, ["inside", "frame"])
    page.wait_for_timeout(200)
    expect(bar(page)).to_have_count(0)
    shot(page)


def test_no_bar_for_an_own_answer_typed_in_the_waiting_card(page: Page, server, repo, shot):
    session = running_session(repo)
    runtime.ask_human(session, "supervisor", "Which port?", "Pick one.")
    log_in(page, server)
    page.goto(f"{server['url']}/sessions/{session}")
    card = page.get_by_role("region", name=f"What waits for you in {session}")
    card.get_by_role("button", name="Other…").click()
    own = card.get_by_role("textbox", name="Your own answer")
    own.fill("8123 for now")
    own.evaluate("f => { f.focus(); f.setSelectionRange(0, 4); }")
    page.wait_for_timeout(200)
    expect(bar(page)).to_have_count(0)
    select(card.get_by_role("listitem").first, "Pick one")
    expect(bar(page)).to_be_visible()
    shot(page)


def test_quote_folds_an_expanded_card(page: Page, server, repo, shot):
    session = gated_session(repo)
    log_in(page, server)
    page.goto(f"{server['url']}/sessions/{session}")
    card = page.get_by_role("region", name=f"What waits for you in {session}")
    card.get_by_role("button", name="Expand the card").click()
    expect(card).to_have_class("waiting-card expanded")
    select(card.get_by_role("tabpanel"), "Build it as planned?")
    expect(bar(page)).to_be_visible()
    shot(page, "selected")
    bar(page).get_by_role("button", name="Quote in reply").click()
    expect(card).to_have_class("waiting-card")
    field = page.get_by_role("textbox", name="Write to the supervisor…")
    expect(field).to_have_value("> Build it as planned?\n")
    expect(field).to_be_focused()
    shot(page)


def test_the_bar_stands_below_on_a_touch_screen(browser: Browser, server, repo, shot):
    session = talked_session(repo)
    context = browser.new_context(
        viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True
    )
    try:
        phone = context.new_page()
        chat = chat_page(phone, server, session)
        select(chat, "The bar hides on Esc")
        toolbar = bar(phone)
        expect(toolbar).to_be_visible()
        selected = phone.evaluate(
            "document.getSelection().getRangeAt(0).getBoundingClientRect().bottom"
        )
        box = toolbar.bounding_box()
        assert box is not None and box["y"] >= selected, (box, selected)
        assert box["x"] >= 8 and box["x"] + box["width"] <= 390 - 8, box
        shot(phone, full_page=False)
    finally:
        context.close()


CODE = "Run it:\n\n```sh\nuv run pytest -m ui\n  --tb=short\n```"


def coded_session(repo) -> str:
    """A running session whose supervisor wrote to the human a message with a code block,
    then one of a summary and a body."""
    session = running_session(repo)
    runtime.send_message(session, "supervisor", "human", "the command", CODE)
    runtime.send_message(session, "supervisor", "human", "Раунд 1", "1. Какие действия?")
    return session


def test_copy_buttons_show_on_hover(page: Page, server, repo, shot):
    session = coded_session(repo)
    log_in(page, server)
    page.goto(f"{server['url']}/sessions/{session}")
    chat = page.get_by_role("log", name="Chat with the session")
    first = chat.get_by_role("article").filter(has_text="the command")
    second = chat.get_by_role("article").filter(has_text="Раунд 1")
    expect(second).to_be_visible()
    page.mouse.move(5, 5)
    copy_code = first.get_by_role("button", name="Copy code")
    copy_message = second.get_by_role("button", name="Copy message")
    # The button with its note: what the hover rule shows and hides.
    code_box = first.locator(".code-block > .copy-icon-button")
    message_box = second.locator(".copy-icon-button")
    expect(code_box).to_have_css("opacity", "0")
    expect(message_box).to_have_css("opacity", "0")
    shot(page, "hidden")
    page.context.grant_permissions(["clipboard-read", "clipboard-write"], origin=server["url"])
    first.locator(".code-block").hover()
    expect(code_box).to_have_css("opacity", "1")
    copy_code.click()
    expect(first.locator(".code-block").get_by_role("status")).to_have_text("Copied")
    assert page.evaluate("navigator.clipboard.readText()") == "uv run pytest -m ui\n  --tb=short"
    second.hover()
    expect(message_box).to_have_css("opacity", "1")
    shot(page, "shown")
    copy_message.click()
    expect(message_box.get_by_role("status")).to_have_text("Copied")  # a continued row's
    assert page.evaluate("navigator.clipboard.readText()") == "Раунд 1\n\n1. Какие действия?"


def test_copy_buttons_always_show_on_a_touch_screen(browser: Browser, server, repo, shot):
    session = coded_session(repo)
    context = browser.new_context(
        viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True
    )
    try:
        phone = context.new_page()
        log_in(phone, server)
        phone.goto(f"{server['url']}/sessions/{session}")
        chat = phone.get_by_role("log", name="Chat with the session")
        expect(chat.get_by_role("button", name="Copy code")).to_be_visible()
        boxes = chat.locator(".copy-icon-button")
        expect(boxes).to_have_count(3)  # Copy code, and Copy message of each message
        for box in boxes.all():
            expect(box).to_have_css("opacity", "1")
        shot(phone, full_page=False)
    finally:
        context.close()
