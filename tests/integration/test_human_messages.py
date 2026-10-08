"""The human in LADO's messages, as the UI does it: a real `lado server` process, the human's
text and answers through its API, the fake agent's hooks and MCP server."""

import json
import os
import subprocess
import sys

import httpx
import pytest
from agent_helpers import fake_logs, wait_for
from event_stream import EventStream
from test_images import png

from lado import runtime, state
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


def inputs(agent: str = "supervisor") -> list:
    log = fake_logs(SESSION, agent) / "inputs.jsonl"
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
    wait_for(lambda: "[from human] send human got it" in inputs(), "the human's line", SESSION)
    mine, reply = wait_for(lambda: len(chat(api)) == 2 and chat(api), "the reply", SESSION)
    assert (reply["from"], reply["to"], reply["summary"]) == ("supervisor", "human", "got it")
    assert mine["state"] == "delivered"
    wait_for(lambda: chat(api)[0]["reply_state"] == "replied", "the reply checked", SESSION)


def test_a_turn_without_a_reply_is_flagged_in_the_feed(api, server, session):
    stream = EventStream(f"{server}/api/events", auth.token())
    try:
        stream.next()  # reset
        api.post(f"/api/sessions/{SESSION}/messages", json={"text": "sleep 0.1"})
        flagged = stream.until(
            lambda e: (
                e.event == "change"
                and e.data["kind"] == "messages"
                and (e.data["item"] or {}).get("reply_state") == "missing"
            )
        )[-1]
        assert flagged.data["item"]["summary"] == "sleep 0.1"
    finally:
        stream.close()


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
        f"/api/sessions/{SESSION}/questions/{question['id']}/answer", json={"choice": "yes"}
    )
    assert answered.status_code == 200
    line = f"[from human] Answer to #{question['id']}: yes"
    wait_for(lambda: line in inputs(), "the answer", SESSION)
    assert chat(api)[1]["question_state"] == "answered"


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
    wait_for(lambda: line in inputs(), "the human's line", SESSION)
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
