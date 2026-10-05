"""The human's messages in the UI server's API: the chat's list, the composer, answering and
dismissing questions. In process, with FastAPI's test client."""

import json
from pathlib import Path

import pytest
from agent_helpers import previous_schema
from fastapi.testclient import TestClient

from lado import runtime, state
from lado.server import app as server_app
from lado.server import auth

PORT = 8123
OWN = "http://testserver"  # the test client's Host
MESSAGES = "/api/sessions/s/messages"


@pytest.fixture
def client():
    client = TestClient(server_app.create_app(auth.token(), PORT))
    client.cookies.set(auth.cookie_name(PORT), auth.token())
    client.headers["origin"] = OWN
    return client


@pytest.fixture
def session(repo, fake_tmux):
    runtime.start_session(str(repo), "s", None, provider="claude")
    runtime.spawn_worker("s", "task", name="w1")
    return "s"


def test_the_chat_lists_the_messages_with_the_human(client, session):
    runtime.send_message("s", "w1", "supervisor", "between agents")
    runtime.send_message("s", "supervisor", "human", "merged w1", "details")
    runtime.ask_human("s", "w1", "Ship?", None, ["yes", "no"], False)
    runtime.write_as_human("s", "thanks")
    answer = client.get(MESSAGES, params={"with": "human"})
    assert answer.status_code == 200
    told, asked, thanks = answer.json()["items"]
    assert told["created_at"].endswith("Z") and "T" in told["created_at"]
    del told["created_at"], asked["created_at"], thanks["created_at"]
    assert told == {
        "id": 2,
        "from": "supervisor",
        "to": "human",
        "kind": "message",
        "summary": "merged w1",
        "body": "details",
        "state": "delivered",
        "choices": None,
        "free_answer": False,
        "question_state": None,
        "answered_by": None,
        "reply_to": None,
        "choice": None,
        "reply_state": None,
    }
    assert (asked["kind"], asked["from"], asked["choices"], asked["question_state"]) == (
        "question",
        "w1",
        ["yes", "no"],
        "open",
    )
    assert (thanks["from"], thanks["to"], thanks["summary"]) == ("human", "supervisor", "thanks")


def test_the_chat_of_an_unknown_session_is_404(client, session):
    assert client.get("/api/sessions/x/messages", params={"with": "human"}).status_code == 404


def test_the_human_writes_to_the_supervisor_by_default(client, session):
    answer = client.post(MESSAGES, json={"text": "merge w1, please"})
    assert answer.status_code == 200
    assert answer.json()["result"].startswith("queued")  # the supervisor is starting
    [message] = state.list_messages("s")
    assert (message.sender, message.recipient, message.summary) == (
        "human",
        "supervisor",
        "merge w1, please",
    )
    client.post(MESSAGES, json={"to": "w1", "text": "and you?"})
    mine, copy = state.list_messages("s")[-2:]
    assert (mine.sender, mine.recipient) == ("human", "w1")
    assert (copy.sender, copy.recipient) == ("lado", "supervisor")


@pytest.mark.parametrize(
    ("payload", "status", "detail"),
    [
        ({"text": " "}, 400, "the message is empty"),
        ({"text": "hi", "to": "w9"}, 400, 'no running agent "w9"'),
        ({"text": "x" * 8001}, 400, "the limit is 8000"),
    ],
)
def test_a_message_the_core_refuses_says_why(client, session, payload, status, detail):
    answer = client.post(MESSAGES, json=payload)
    assert answer.status_code == status
    assert detail in answer.json()["detail"]
    assert state.list_messages("s") == []


def test_a_message_to_a_stopped_or_unknown_session_is_refused(client, session):
    assert client.post("/api/sessions/x/messages", json={"text": "hi"}).status_code == 404
    runtime.stop_session("s")
    answer = client.post(MESSAGES, json={"text": "hi"})
    assert answer.status_code == 400
    assert 'session "s" is stopped' in answer.json()["detail"]


def test_the_human_answers_and_dismisses_questions(client, session):
    runtime.ask_human("s", "w1", "Ship?", None, ["yes", "no"])
    runtime.ask_human("s", "w1", "Port?")
    ship, port = state.list_messages("s")
    answered = client.post(f"/api/sessions/s/questions/{ship.id}/answer", json={"choice": "yes"})
    assert answered.status_code == 200
    assert client.post(f"/api/sessions/s/questions/{port.id}/dismiss").status_code == 200
    _, _, answer, dismissal = state.list_messages("s")
    assert (answer.summary, answer.reply_to) == (f"Answer to #{ship.id}: yes", ship.id)
    assert (dismissal.summary, dismissal.reply_to) == (f"Dismissed #{port.id}", port.id)
    again = client.post(f"/api/sessions/s/questions/{ship.id}/answer", json={"text": "no"})
    assert again.status_code == 400
    assert again.json()["detail"] == f"question #{ship.id} is answered"


@pytest.mark.parametrize(
    "path",
    [MESSAGES, "/api/sessions/s/questions/1/answer", "/api/sessions/s/questions/1/dismiss"],
)
def test_a_change_needs_the_servers_own_origin(client, session, path):
    runtime.ask_human("s", "w1", "Ship?")
    payload = {"text": "hi"}
    del client.headers["origin"]
    assert client.post(path, json=payload).status_code == 403
    client.headers["origin"] = "http://evil.example"
    assert client.post(path, json=payload).status_code == 403
    assert [m.kind for m in state.list_messages("s")] == ["question"]


@pytest.mark.parametrize(
    "path",
    [MESSAGES, "/api/sessions/s/questions/1/answer", "/api/sessions/s/questions/1/dismiss"],
)
def test_a_change_under_another_schema_is_503_and_migrates_nothing(client, session, path):
    runtime.ask_human("s", "w1", "Ship?")
    previous_schema()
    answer = client.post(path, json={"text": "hi"})
    assert answer.status_code == 503
    assert state.schema_version() == state.SCHEMA_VERSION - 1


CASES = json.loads(
    (Path(__file__).parent.parent / "web" / "src" / "messageFilter.cases.json").read_text()
)


@pytest.fixture
def table(session) -> dict[int, int]:
    """The case table's messages in session "s", with their times: case id -> real id."""
    ids = {}
    for one in CASES["messages"]:
        real = state.queue_message("s", one["from"], one["to"], f"m{one['id']}")
        stored = one["created_at"].replace("T", " ").removesuffix("Z")
        with state.connect() as db:
            db.execute("UPDATE messages SET created_at = ? WHERE id = ?", (stored, real))
        ids[one["id"]] = real
    return ids


@pytest.mark.parametrize("case", CASES["cases"], ids=lambda case: json.dumps(case["filter"]))
def test_a_filter_takes_the_messages_of_the_case_table(client, table, case):
    params = {
        key: table[value] if key in ("before", "after") else value
        for key, value in case["filter"].items()
    }
    answer = client.get(MESSAGES, params=params)
    assert answer.status_code == 200
    by_real = {real: mine for mine, real in table.items()}
    assert [by_real[m["id"]] for m in answer.json()["items"]] == case["ids"]


def summaries(page: dict) -> list[str]:
    return [m["summary"] for m in page["items"]]


def test_limit_gives_the_latest_oldest_first_and_whether_there_are_earlier(client, table):
    page = client.get(MESSAGES, params={"limit": 2}).json()
    assert (summaries(page), page["earlier"]) == (["m5", "m6"], True)
    page = client.get(MESSAGES, params={"limit": 2, "before": table[5]}).json()
    assert (summaries(page), page["earlier"]) == (["m3", "m4"], True)
    page = client.get(MESSAGES, params={"limit": 3, "with": "human"}).json()  # exactly 3
    assert (summaries(page), page["earlier"]) == (["m3", "m4", "m6"], False)
    page = client.get(MESSAGES, params={"limit": 5, "with": "human"}).json()  # fewer than 5
    assert (summaries(page), page["earlier"]) == (["m3", "m4", "m6"], False)
    page = client.get(MESSAGES, params={"limit": 5, "before": table[1]}).json()  # none
    assert (summaries(page), page["earlier"]) == ([], False)


def test_earlier_counts_the_kind_and_the_times_not_the_cursors(client, table):
    # A range up to the window (after, before) still says what lies before it.
    page = client.get(MESSAGES, params={"after": table[3], "before": table[6]}).json()
    assert (summaries(page), page["earlier"]) == (["m4", "m5"], True)
    page = client.get(MESSAGES, params={"with": "human", "after": table[3]}).json()
    assert (summaries(page), page["earlier"]) == (["m4", "m6"], True)
    since = "2026-10-04T15:05:00Z"
    page = client.get(MESSAGES, params={"since": since, "limit": 2}).json()
    assert (summaries(page), page["earlier"]) == (["m5", "m6"], True)
    page = client.get(MESSAGES, params={"since": since, "limit": 3}).json()
    assert (summaries(page), page["earlier"]) == (["m4", "m5", "m6"], False)


def test_without_limit_every_message_that_matches(client, table):
    page = client.get(MESSAGES).json()
    assert (summaries(page), page["earlier"]) == ([f"m{n}" for n in range(1, 7)], False)


@pytest.mark.parametrize(
    "params", [{"since": "yesterday"}, {"until": "2026-13-01"}, {"limit": 0}, {"with": "w1"}]
)
def test_a_wrong_parameter_is_422(client, table, params):
    assert client.get(MESSAGES, params=params).status_code == 422


def test_the_messages_are_for_the_token_holder_only(table):
    client = TestClient(server_app.create_app(auth.token(), PORT))
    assert client.get(MESSAGES).status_code == 401
