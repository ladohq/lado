"""The UI server's API of the first-run guide (openspec change first-run-guide):
GET/POST /api/guide, the first record after the first login check, the facts, a missing
marker in the error journal and LADO_GUIDE=0. In process, with FastAPI's test client; the
login check's reads replaced by rows the test gives (provider_check._pass)."""

import json
import threading

import pytest
from fastapi.testclient import TestClient

from lado import guide, providers, state
from lado.providers import base
from lado.server import app as server_app
from lado.server import auth, provider_check

PORT = 8131
OWN = "http://testserver"


@pytest.fixture
def client(lado_home, git_config, monkeypatch):
    monkeypatch.delenv("LADO_GUIDE")
    git_config.write_text("")  # nobody signs commits unless the test says so
    provider_check.reset()
    guide.forget_missing()
    client = TestClient(server_app.create_app(auth.token(), PORT))
    client.cookies.set(auth.cookie_name(PORT), auth.token())
    client.headers["origin"] = OWN
    yield client
    provider_check.reset()
    client.app.state.clones.close()


class Check:
    """The login check's reads: each pass sets `logged_in`'s rows logged in, the others
    not; `hold` keeps a pass from ending until it is set."""

    def __init__(self):
        self.logged_in: set[str] = set()
        self.passes = 0
        self.hold = threading.Event()
        self.hold.set()

    def run(self):
        self.passes += 1
        self.hold.wait(10)
        for name in providers.names():
            provider_check.put(_row(name, name in self.logged_in))


def _row(name, logged_in):
    row = provider_check._not_ready(providers.get(name))
    return row.model_copy(
        update={
            "ready": True,
            "cli": row.cli.model_copy(update={"installed": True}),
            "login": row.login.model_copy(update={"state": "yes" if logged_in else "no"}),
        }
    )


@pytest.fixture
def check(monkeypatch):
    found = Check()
    monkeypatch.setattr(provider_check, "_pass", found.run)
    yield found
    found.hold.set()


def _journal():
    path = state.home() / "errors.jsonl"
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


def test_a_fresh_lado_gets_a_record_not_completed(client, check):
    info = client.get("/api/guide").json()
    assert info == {
        "auto": True,
        "completed": False,
        "shown": [],
        "tips_off": False,
        "telemetry_asked": False,
        "facts": {"model": False, "author": False},
    }
    assert guide.read() == guide.Record(completed=False, shown=(), tips_off=False)
    assert check.passes == 1


def test_a_logged_in_cli_makes_the_record_completed(client, check):
    check.logged_in = {"codex"}
    info = client.get("/api/guide").json()
    assert info["completed"] is True and info["facts"] is None
    assert guide.read() == guide.Record(completed=True, shown=(), tips_off=False)


def test_a_model_on_a_saved_server_makes_it_completed_without_a_check(client, check):
    state.add_model_server("s1", "lms", "http://lms", "LM Studio", (base.CHAT_COMPLETIONS,))
    state.add_model("qwen", "opencode", "qwen3-8b", "s1")
    assert client.get("/api/guide").json()["completed"] is True
    assert check.passes == 0


def test_a_saved_server_without_a_model_is_no_model(client, check):
    """A server saved but no model of it ticked for an agent CLI: no agent has a model."""
    state.add_model_server("s1", "lms", "http://lms", "LM Studio", (base.CHAT_COMPLETIONS,))
    info = client.get("/api/guide").json()
    assert info["completed"] is False and info["facts"]["model"] is False


def test_a_check_that_does_not_end_in_time_writes_nothing(client, check, monkeypatch):
    monkeypatch.setattr(guide, "WAIT", 0.1)
    check.hold.clear()
    first = client.get("/api/guide").json()
    assert first["completed"] is True and first["facts"] is None
    assert guide.read() is None
    second = client.get("/api/guide").json()  # the next page load, the check still runs
    assert second["completed"] is True and guide.read() is None
    check.hold.set()
    provider_check.reset()  # waits for the check's end; its rows are gone with it
    assert check.passes == 1  # two GETs, one check


@pytest.mark.parametrize(
    "body",
    [
        {"action": "shown", "ids": ["tip-session"]},
        {"action": "missing", "ids": ["tip-session"], "marker": "session-tabs"},
        {"action": "tips_off"},
    ],
)
def test_a_mark_before_the_first_record_starts_no_guide(client, check, monkeypatch, body):
    """The first check did not end in time: GET answered `completed` without a record. A
    tip's mark then must not make a record that starts the main guide on a LADO that may be
    set up."""
    monkeypatch.setattr(guide, "WAIT", 0.1)
    check.hold.clear()
    assert client.get("/api/guide").json()["completed"] is True
    answer = client.post("/api/guide", json=body).json()
    assert answer["completed"] is True and answer["facts"] is None
    assert guide.read() is None or guide.read().completed is True
    check.hold.set()


def test_a_check_that_failed_is_no_answer(client, monkeypatch):
    """A login check whose pass raised says nothing of the logins: no record is made."""

    def broken():
        raise RuntimeError("the shell could not be read")

    monkeypatch.setattr(provider_check, "_pass", broken)
    monkeypatch.setattr(guide, "WAIT", 0.5)
    info = client.get("/api/guide").json()
    assert info["completed"] is True and info["facts"] is None
    assert guide.read() is None


def test_facts_are_answered_while_not_completed(client, check, git_config):
    guide.write(guide.Record(completed=False, shown=("welcome",), tips_off=False))
    git_config.write_text("[user]\n\tname = Alex Home\n\temail = alex@home.example\n")
    info = client.get("/api/guide").json()
    assert info["facts"] == {"model": False, "author": True}
    assert info["shown"] == ["welcome"]


def test_a_restarted_guide_on_a_set_up_lado_does_not_come_back_by_itself(client, check):
    """Help → Getting started, then Not now, on a LADO with a model and an author: the next
    page load's answer completes the guide, so nothing starts by itself."""
    check.logged_in = {"codex"}
    state.set_commit_author("Ann Lee", "ann@example.com")
    guide.write(guide.Record(completed=True, shown=("welcome",), tips_off=False))
    restarted = client.post("/api/guide", json={"action": "restart"}).json()
    assert restarted["completed"] is False  # this page load shows it
    again = client.get("/api/guide").json()
    assert again["completed"] is True and again["facts"] is None
    assert guide.read() == guide.Record(completed=True, shown=("welcome",), tips_off=False)


def test_a_guide_with_the_author_left_comes_back_by_itself(client, check):
    check.logged_in = {"codex"}
    guide.write(guide.Record(completed=False, shown=(), tips_off=False))
    info = client.get("/api/guide").json()
    assert info["completed"] is False and info["facts"] == {"model": True, "author": False}


def test_ladOs_own_author_is_an_author(client, check):
    guide.write(guide.Record(completed=False, shown=(), tips_off=False))
    state.set_commit_author("Ann Lee", "ann@example.com")
    assert client.get("/api/guide").json()["facts"]["author"] is True


def test_a_completed_guide_answers_no_facts_and_runs_no_check(client, check):
    guide.write(guide.Record(completed=True, shown=(), tips_off=False))
    assert client.get("/api/guide").json()["facts"] is None
    assert check.passes == 0


def test_the_actions(client, check):
    guide.write(guide.Record(completed=False, shown=(), tips_off=False))
    ok = client.post("/api/guide", json={"action": "shown", "ids": ["welcome"]})
    assert ok.status_code == 200 and ok.json()["shown"] == ["welcome"]
    client.post("/api/guide", json={"action": "shown", "ids": ["tip-launch", "welcome"]})
    assert guide.read().shown == ("welcome", "tip-launch")
    assert client.post("/api/guide", json={"action": "tips_off"}).json()["tips_off"] is True
    done = client.post("/api/guide", json={"action": "complete"}).json()
    assert done["completed"] is True and done["facts"] is None
    again = client.post("/api/guide", json={"action": "restart"}).json()
    assert (again["completed"], again["tips_off"]) == (False, False)
    assert again["shown"] == ["welcome", "tip-launch"]
    assert again["facts"] == {"model": False, "author": False}


@pytest.mark.parametrize(
    "body",
    [
        {"action": "forget"},
        {"action": "shown", "ids": ["Not An Id"]},
        {"action": "shown", "ids": ["x" * 65]},
        {"action": "missing", "ids": ["welcome"], "marker": "a b"},
    ],
)
def test_a_bad_action_or_id_is_refused(client, check, body):
    assert client.post("/api/guide", json=body).status_code == 422
    assert guide.read() is None


def test_a_missing_marker_is_journaled_once_per_id(client, check):
    body = {"action": "missing", "ids": ["model-server-add"], "marker": "model-server-add"}
    assert client.post("/api/guide", json=body).status_code == 200
    assert client.post("/api/guide", json=body).status_code == 200
    lines = _journal()
    assert [line["where"] for line in lines] == ["ui:guide"]
    assert lines[0]["type"] == "lado.guide.GuideMarkerMissing"
    assert "model-server-add: model-server-add" in lines[0]["message"]
    other = {"action": "missing", "ids": ["author-set"], "marker": "author-row"}
    client.post("/api/guide", json=other)
    assert len(_journal()) == 2


def test_telemetry_asked_follows_the_banner(client, check, monkeypatch):
    monkeypatch.delenv("LADO_TELEMETRY")
    monkeypatch.setenv("LADO_TELEMETRY_URL", "http://127.0.0.1:9/batch/")
    assert client.get("/api/guide").json()["telemetry_asked"] is True
    client.post("/api/telemetry", json={"choice": "off"})
    assert client.get("/api/guide").json()["telemetry_asked"] is False


def test_lado_guide_0_starts_nothing(client, check, monkeypatch):
    monkeypatch.setenv("LADO_GUIDE", "0")
    info = client.get("/api/guide").json()
    assert info["auto"] is False and info["facts"] is None
    assert guide.read() is None and check.passes == 0
    again = client.post("/api/guide", json={"action": "restart"}).json()
    assert again["auto"] is False and again["completed"] is False
    assert again["facts"] == {"model": False, "author": False}
    assert guide.read() == guide.Record(completed=False, shown=(), tips_off=False)
