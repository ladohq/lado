"""The human in LADO's messages, as the UI does it: a real `lado server` process, the human's
text and answers through its API, the fake agent's hooks and MCP server."""

import json
import os
import re
import subprocess
import sys

import httpx
import pytest
from agent_helpers import cut_off, end_loop, fake_logs, wait_for
from event_stream import EventStream
from test_images import png

from lado import runtime, state, tmux
from lado.server import auth
from lado.server import run as server_run

pytestmark = pytest.mark.integration

SESSION = "chat"


@pytest.fixture
def server():
    process = subprocess.Popen(
        [sys.executable, "-m", "lado.cli", "server", "--port", "0"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=os.environ,
    )
    try:
        yield server_run.wait_ready()["url"]
    finally:
        subprocess.run(
            [sys.executable, "-m", "lado.cli", "server", "stop"],
            capture_output=True,
            env=os.environ,
            timeout=30,
            check=False,
        )
        process.wait(timeout=10)


@pytest.fixture
def api(server):
    with httpx.Client(
        base_url=server, headers={"Authorization": f"Bearer {auth.token()}"}, timeout=10
    ) as client:
        yield client


@pytest.fixture
def session(repo):
    runtime.start_session(str(repo), SESSION, None, "fake")
    wait_for(lambda: state.get_agent(SESSION, "supervisor").status == state.IDLE, "idle", SESSION)
    yield SESSION
    runtime.stop_session(SESSION)


def inputs(agent: str = "supervisor", session: str = SESSION) -> list:
    log = fake_logs(session, agent) / "inputs.jsonl"
    return [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []


def seen(agent: str = "supervisor") -> dict:
    path = fake_logs(SESSION, agent) / "seen.json"
    return json.loads(path.read_text()) if path.exists() else {}


def chat(api) -> list[dict]:
    answer = api.get(f"/api/sessions/{SESSION}/messages", params={"with": "human"})
    assert answer.status_code == 200
    return answer.json()["items"]


def test_the_humans_message_reaches_the_agent_and_its_reply_the_human(api, session):
    sent = api.post(f"/api/sessions/{SESSION}/messages", json={"text": "send human got it"})
    assert sent.status_code == 200
    line = "[from human] send human got it" + runtime.HUMAN_REPLY_HINT
    wait_for(lambda: line in inputs(), "the human's line", SESSION)
    mine, reply = wait_for(lambda: len(chat(api)) == 2 and chat(api), "the reply", SESSION)
    assert (reply["from"], reply["to"], reply["summary"]) == ("supervisor", "human", "got it")
    assert mine["state"] == "delivered"
    wait_for(lambda: chat(api)[0]["reply_state"] == "replied", "the reply checked", SESSION)
    assert reminders() == []


def reminders() -> list[state.Message]:
    """LADO's reminders to the supervisor of a message from the human it did not answer."""
    return [
        m
        for m in state.list_messages(SESSION)
        if (m.sender, m.recipient) == (state.LADO, "supervisor")
        and m.summary.startswith("your answer to the human's message #")
    ]


def reply_states(stream: EventStream, message: int) -> list:
    """The reply states the feed brought for `message` until it was decided."""
    changes = stream.until(
        lambda e: (
            e.event == "change"
            and e.data["kind"] == "messages"
            and (e.data["item"] or {}).get("id") == message
            and e.data["item"]["reply_state"] is not None
        ),
        timeout=30,
    )
    return [
        e.data["item"]["reply_state"]
        for e in changes
        if e.event == "change"
        and e.data["kind"] == "messages"
        and (e.data["item"] or {}).get("id") == message
        and e.data["item"]["reply_state"] is not None
    ]


def test_an_answer_left_in_the_terminal_gets_one_reminder_then_the_flag(api, server, session):
    """LAD-274: the agent learns of it once; the feed flags it only after the reminder's
    turn, and the reminder makes no loop."""
    stream = EventStream(f"{server}/api/events", auth.token())
    try:
        stream.next()  # reset
        api.post(f"/api/sessions/{SESSION}/messages", json={"text": "sleep 0.1"})
        [mine] = [m for m in state.list_messages(SESSION) if m.sender == state.HUMAN]
        assert reply_states(stream, mine.id)[-1] == "missing"
        [reminder] = reminders()
        assert f"#{mine.id} went only to your terminal" in reminder.summary
        assert f"[from lado] {reminder.summary}" in "\n".join(inputs())
        wait_for(
            lambda: state.get_agent(SESSION, "supervisor").status == state.IDLE, "idle", SESSION
        )
        assert len(reminders()) == 1  # nothing more after the verdict
        assert state.get_message(SESSION, mine.id).reply_state == state.MISSING
    finally:
        stream.close()


def test_an_answer_after_the_reminder_is_a_reply(api, server, session):
    stream = EventStream(f"{server}/api/events", auth.token())
    try:
        stream.next()  # reset
        api.post(f"/api/sessions/{SESSION}/messages", json={"text": "next send human hello"})
        [mine] = [m for m in state.list_messages(SESSION) if m.sender == state.HUMAN]
        assert reply_states(stream, mine.id) == ["replied"]  # never flagged on the way
        assert len(reminders()) == 1
        [reply] = [m for m in chat(api) if m["from"] == "supervisor"]
        assert reply["summary"] == "hello"
    finally:
        stream.close()


def test_a_turn_that_ended_on_an_error_reminds_of_nothing(api, session):
    api.post(f"/api/sessions/{SESSION}/messages", json={"text": "fail APIError: it broke"})
    wait_for(
        lambda: [e for e in state.list_events(SESSION) if e.kind == state.TURN_ERROR],
        "the failed turn",
        SESSION,
    )
    [mine] = [m for m in state.list_messages(SESSION) if m.sender == state.HUMAN]
    assert state.get_message(SESSION, mine.id).reply_state is None
    assert reminders() == []


def test_the_agents_question_is_answered_through_the_api(api, session):
    api.post(f"/api/sessions/{SESSION}/messages", json={"text": "askhuman Ship it? | yes, no"})
    [_, question] = wait_for(lambda: len(chat(api)) == 2 and chat(api), "the question", SESSION)
    assert (question["kind"], question["choices"], question["question_state"]) == (
        "question",
        ["yes", "no"],
        "open",
    )
    wait_for(lambda: state.get_agent(SESSION, "supervisor").status == state.IDLE, "idle", SESSION)
    answered = api.post(
        f"/api/sessions/{SESSION}/answers",
        json={"answers": [{"question": question["id"], "choice": "yes"}]},
    )
    assert answered.status_code == 200
    line = f"[from human] Answer to #{question['id']}: yes"
    wait_for(lambda: line in inputs(), "the answer", SESSION)
    assert chat(api)[1]["question_state"] == "answered"


def test_a_question_a_stop_closed_reaches_the_new_supervisor_and_takes_no_answer(
    api, session, repo
):
    api.post(f"/api/sessions/{SESSION}/messages", json={"text": "askhuman Ship it? | yes, no"})
    [_, question] = wait_for(lambda: len(chat(api)) == 2 and chat(api), "the question", SESSION)
    wait_for(lambda: state.get_agent(SESSION, "supervisor").status == state.IDLE, "idle", SESSION)
    preview = api.get(f"/api/sessions/{SESSION}/stop-preview").json()
    assert preview["questions"] == 1
    runtime.stop_session(SESSION)
    runtime.start_session(str(repo), SESSION, None)
    wait_for(lambda: "first_read" in seen(), "the new supervisor reads its first input", SESSION)
    [notice] = [m for m in seen()["first_read"] if "closed unanswered" in m["summary"]]
    assert notice["summary"] == "1 question to the human closed unanswered by the stop"
    assert f"#{question['id']} from supervisor: Ship it?" in notice["body"]
    assert "Choices: yes, no" in notice["body"]
    [stopped] = [m for m in chat(api) if m["kind"] == "question"]
    assert stopped["question_state"] == "stopped"
    assert stopped["answered_by"] == notice["id"]
    assert notice["id"] not in [m["id"] for m in chat(api)]  # it is the supervisor's alone
    refused = api.post(
        f"/api/sessions/{SESSION}/answers",
        json={"answers": [{"question": question["id"], "choice": "yes"}]},
    )
    assert refused.status_code == 400
    assert refused.json()["detail"] == f"question #{question['id']} is stopped"


def stop_as_it_types(monkeypatch) -> None:
    """The session stops between the hand-over and the typing, which then meets real tmux."""
    typing = tmux.send_text

    def stopped_first(session: str, window: str, text: str) -> None:
        if session == SESSION:
            runtime.stop_session(session)
        typing(session, window, text)

    monkeypatch.setattr(tmux, "send_text", stopped_first)


def refused_by_the_stop(repo) -> str:
    """Write as the stop comes, check the refusal, resume; returns what tmux said."""
    # The session loop would otherwise hand the message over in its own process, typing it
    # past the patched send_text: then no stop comes and the write is "sent".
    end_loop(SESSION)
    with pytest.raises(runtime.LadoError) as refused:
        runtime.write_as_human(SESSION, "merge it")
    assert str(refused.value) == cut_off("supervisor")
    assert state.get_session(SESSION).stopped_at is not None
    [message] = [m for m in state.list_messages(SESSION) if m.summary == "merge it"]
    assert message.state == state.DROPPED
    runtime.start_session(str(repo), SESSION, None)
    wait_for(lambda: state.get_agent(SESSION, "supervisor").status == state.IDLE, "idle", SESSION)
    return str(refused.value.__cause__)


def test_a_stop_as_the_message_is_typed_refuses_it_on_a_tmux_server_left_empty(
    session, repo, monkeypatch
):
    stop_as_it_types(monkeypatch)
    assert re.search("no server running|error connecting", refused_by_the_stop(repo))


def test_a_stop_as_the_message_is_typed_refuses_it_and_spares_a_session_of_a_longer_name(
    session, repo, monkeypatch
):
    other = f"{SESSION}-two"
    runtime.start_session(str(repo), other, None, "fake")
    wait_for(lambda: state.get_agent(other, "supervisor").status == state.IDLE, "idle", other)
    try:
        stop_as_it_types(monkeypatch)
        assert "can't find session" in refused_by_the_stop(repo)
        runtime.write_as_human(other, "for you")
        line = "[from human] for you" + runtime.HUMAN_REPLY_HINT
        wait_for(lambda: line in inputs(session=other), "the line", other)
        assert not [i for i in inputs(session=other) if "[from human] merge it" in i]
    finally:
        runtime.stop_session(other)


def test_an_answer_of_files_only_reaches_the_agent_which_reads_the_file(api, session):
    """The waiting card's path: an upload, then an own answer with its name and no text."""
    api.post(f"/api/sessions/{SESSION}/messages", json={"text": "askhuman Which log?"})
    [_, question] = wait_for(lambda: len(chat(api)) == 2 and chat(api), "the question", SESSION)
    wait_for(lambda: state.get_agent(SESSION, "supervisor").status == state.IDLE, "idle", SESSION)
    upload = api.post(
        f"/api/sessions/{SESSION}/artifacts",
        params={"file_name": "server.log"},
        content=b"boom at line 3\n",
    )
    name = upload.json()["full_name"]
    answered = api.post(
        f"/api/sessions/{SESSION}/answers",
        json={"answers": [{"question": question["id"], "text": "", "artifacts": [name]}]},
    )
    assert answered.status_code == 200
    answer = next(m for m in chat(api) if m["reply_to"] == question["id"])
    assert [a["full_name"] for a in answer["attachments"]] == [name]
    line = (
        f"[from human] Answer to #{question['id']}: 1 file: {name}"
        f" (#{answer['id']}, 1 artifact: call read_messages)"
    )
    wait_for(lambda: line in inputs(), "the answer's line", SESSION)
    wait_for(lambda: state.get_agent(SESSION, "supervisor").status == state.IDLE, "idle", SESSION)
    api.post(f"/api/sessions/{SESSION}/messages", json={"text": "read"})
    read = wait_for(lambda: seen().get("read"), "read_messages", SESSION)
    [given] = [m for m in read if m["id"] == answer["id"]]
    assert [a["name"] for a in given["artifacts"]] == [name]
    api.post(f"/api/sessions/{SESSION}/messages", json={"text": f"artifact_read {name}"})
    got = wait_for(lambda: seen().get("artifact_read"), "read_artifact", SESSION)
    assert got["content"] == "boom at line 3\n"


def test_two_answers_reach_the_agent_in_one_input(api, session):
    """A tab of the waiting card: the agent's two open questions answered in one request
    reach it in one hand-over, so they start one turn."""
    idle = lambda: state.get_agent(SESSION, "supervisor").status == state.IDLE  # noqa: E731
    for asked, ask in enumerate(["askhuman Ship it? | yes, no", "askhuman Which port?"], 1):
        api.post(f"/api/sessions/{SESSION}/messages", json={"text": ask})
        wait_for(lambda n=asked: len(chat(api)) == 2 * n and idle(), "the question", SESSION)
    ship, port = [m for m in chat(api) if m["kind"] == "question"]
    answered = api.post(
        f"/api/sessions/{SESSION}/answers",
        json={
            "answers": [
                {"question": ship["id"], "choice": "yes"},
                {"question": port["id"], "text": "8123"},
            ]
        },
    )
    assert answered.status_code == 200
    both = f"[from human] Answer to #{ship['id']}: yes\n[from human] Answer to #{port['id']}: 8123"
    wait_for(lambda: both in inputs(), "both answers in one input", SESSION)
    assert not any(f"Answer to #{port['id']}" in i for i in inputs() if i != both)
    states = {m["id"]: m["question_state"] for m in chat(api)}
    assert (states[ship["id"]], states[port["id"]]) == ("answered", "answered")


def test_a_workers_question_asks_the_lead_whose_recommendation_reaches_the_card(api, session):
    runtime.spawn_worker(SESSION, "sleep 0", name="w1")
    wait_for(lambda: state.get_agent(SESSION, "w1").status == state.IDLE, "w1 idle", SESSION)
    runtime.send_message(SESSION, "human", "w1", "askhuman Ship it? | yes, later")
    question = wait_for(
        lambda: next((m for m in chat(api) if m["kind"] == "question"), None),
        "the question",
        SESSION,
    )
    line = f"[from lado] recommend on question #{question['id']} of w1"
    wait_for(lambda: any(line in text for text in inputs()), "the request", SESSION)
    wait_for(lambda: state.get_agent(SESSION, "supervisor").status == state.IDLE, "idle", SESSION)
    api.post(
        f"/api/sessions/{SESSION}/messages",
        json={"text": f"give_recommendation question {question['id']} later"},
    )
    rec = wait_for(
        lambda: (lambda r: r if r and r["state"] == "given" else None)(
            next(m for m in chat(api) if m["id"] == question["id"])["recommendation"]
        ),
        "the recommendation",
        SESSION,
    )
    assert (rec["choice"], rec["disagrees"], rec["by"], rec["text"]) == (
        "later",
        True,
        "w1",
        "my own view",
    )


def test_the_humans_image_reaches_the_agent_which_reads_it_as_an_image(api, session):
    """The composer's path: an upload, then a message with its name; the agent's line counts
    it, read_messages names it and read_artifact gives the image itself."""
    data = png(3, 2)
    upload = api.post(
        f"/api/sessions/{SESSION}/artifacts", params={"file_name": "Shot.png"}, content=data
    )
    assert upload.status_code == 200
    name = upload.json()["full_name"]
    sent = api.post(f"/api/sessions/{SESSION}/messages", json={"text": "read", "artifacts": [name]})
    assert sent.status_code == 200
    [message] = [m for m in chat(api) if m["from"] == "human"]
    line = f"[from human] read (#{message['id']}, 1 artifact: call read_messages)"
    wait_for(lambda: line + runtime.HUMAN_REPLY_HINT in inputs(), "the human's line", SESSION)
    [read] = wait_for(lambda: seen().get("read"), "read_messages", SESSION)
    assert read["artifacts"] == [
        {
            "name": name,
            "title": "Shot.png",
            "media_type": "image/png",
            "size": len(data),
            "changed": False,
        }
    ]
    api.post(f"/api/sessions/{SESSION}/messages", json={"text": f"artifact_read {name}"})
    blocks = wait_for(lambda: seen().get("artifact_read_blocks"), "read_artifact", SESSION)
    assert blocks == [
        {"type": "text", "mimeType": None},
        {"type": "image", "mimeType": "image/png"},
    ]
    assert (seen()["artifact_read"]["width"], seen()["artifact_read"]["height"]) == (3, 2)
