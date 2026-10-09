"""The system panel's API: /api/system and its report, /api/health's start, the update check
on demand, the update's plan and its start (docs/design/ui.md, System panel). In process,
with FastAPI's test client; the update as a process is in
tests/integration/test_update_process.py."""

import datetime
import fcntl
import json

import pytest
from fastapi.testclient import TestClient

from lado import __version__, doctor, runtime, self_update, state, update
from lado.server import app as server_app
from lado.server import auth
from lado.server import run as server_run

PORT = 8123
OWN = "http://testserver"  # the test client's Host
NEW = "99.0.0"


@pytest.fixture
def client(lado_home):
    client = TestClient(server_app.create_app(auth.token(), PORT))
    client.cookies.set(auth.cookie_name(PORT), auth.token())
    client.headers["origin"] = OWN
    return client


@pytest.fixture
def installed(tmp_path, monkeypatch, published):
    """This LADO as an install the tests' installer updates; PyPI has NEW."""
    published(**{NEW: "2026-10-04", __version__: "2026-10-01"})
    monkeypatch.setenv("LADO_UPDATE_PREFIX", str(tmp_path / "prefix"))
    monkeypatch.setenv("LADO_UPDATE_INSTALLER", "/bin/false")


@pytest.fixture
def spawned(monkeypatch):
    """The detached `lado update` the server would start: its arguments."""
    calls = []
    monkeypatch.setattr(self_update, "start_detached", lambda to, id: calls.append((to, id)))
    return calls


def ok(answer):
    assert answer.status_code == 200, answer.text
    return answer.json()


def test_health_says_when_the_server_started(client):
    said = client.get("/api/health").json()
    started = datetime.datetime.fromisoformat(said["started_at"])
    assert (datetime.datetime.now(datetime.timezone.utc) - started).total_seconds() < 60
    assert client.get("/api/health").json() == said  # the same server: the same start
    later = TestClient(server_app.create_app(auth.token(), PORT)).get("/api/health").json()
    assert later["started_at"] >= said["started_at"]


def test_system_names_the_version_tmux_providers_kits_and_sessions(client, repo, fake_tmux):
    runtime.start_session(str(repo), "s", None, provider="claude")
    runtime.start_session(str(repo), "t", None, provider="claude")
    runtime.stop_session("t")
    info = ok(client.get("/api/system"))
    assert info["version"] == __version__
    assert info["python"] and info["os"] and info["machine"]
    assert info["home"] == str(state.home()) and info["home_set"] is True
    assert info["schema"] == state.SCHEMA_VERSION
    assert info["open_to_network"] is False
    assert info["started_at"] == client.get("/api/health").json()["started_at"]
    assert {p["name"] for p in info["providers"]} >= {"claude", "kilo", "opencode"}
    assert {"name": "default", "version": info["kits"][0]["version"], "origin": "built-in"} in (
        info["kits"]
    )
    assert (info["sessions"]["running"], info["sessions"]["stopped"]) == (1, 1)
    assert info["tmux"]["socket"] == runtime.tmux.socket()
    assert info["report"].startswith("### LADO system info\n")


def test_the_report_has_no_address_home_repo_session_or_token(
    client, repo, fake_tmux, published, monkeypatch
):
    monkeypatch.setattr(server_run, "running", lambda: {"url": "http://10.1.2.3:8123"})
    published(**{NEW: "2026-10-04"})
    runtime.start_session(str(repo), "secret-session", None, provider="claude")
    update.write_result(
        update.Result(
            "partial",
            __version__,
            NEW,
            "2026-10-09T10:00:00+00:00",
            sessions_failed=[{"name": "secret-session", "command": f"lado start {repo}"}],
            reason=f"a reason that names {repo}",
            tail=[f"{repo}"],
        )
    )
    report = ok(client.get("/api/system"))["report"]
    for secret in (
        str(state.home()),
        str(repo),
        "secret-session",
        auth.token(),
        "10.1.2.3",
        "127.0.0.1",
        str(PORT),
    ):
        assert secret not in report
    assert "- Home: LADO_HOME set\n" in report
    assert "loopback only" in report
    assert f"- Update: {NEW} available" in report
    assert f"- Last update: {__version__} → {NEW}, partial" in report


def test_a_server_open_to_the_network_says_so_and_no_more(lado_home):
    app = server_app.create_app(auth.token(), PORT, host="0.0.0.0")
    client = TestClient(app)
    client.cookies.set(auth.cookie_name(PORT), auth.token())
    info = ok(client.get("/api/system"))
    assert info["open_to_network"] is True
    assert "- Server: open to the network," in info["report"]


def test_the_check_now_looks_at_the_index_although_the_daily_one_is_fresh(client, published):
    published(**{"98.0.0": "2026-10-01"})
    assert ok(client.get("/api/update"))["available"] == "98.0.0"
    published(**{"98.0.0": "2026-10-01", NEW: "2026-10-04"})
    assert ok(client.get("/api/update"))["available"] == "98.0.0"  # the day's cache
    checked = ok(client.post("/api/update/check"))
    assert (checked["available"], checked["released"]) == (NEW, "2026-10-04")
    assert ok(client.get("/api/update"))["available"] == NEW


def test_a_failed_check_now_says_why(client, published, tmp_path, monkeypatch):
    monkeypatch.setenv("LADO_UPDATE_INDEX", str(tmp_path / "missing.json"))
    checked = ok(client.post("/api/update/check"))
    assert checked["error"].startswith("cannot look up LADO's latest version:")


def test_update_says_whether_this_lado_can_update_itself(client, installed, monkeypatch):
    info = ok(client.get("/api/update"))
    assert (info["can_update"], info["why_not"], info["running"]) == (True, None, False)
    assert info["last"] is None
    monkeypatch.delenv("LADO_UPDATE_INSTALLER")
    info = ok(client.get("/api/update"))
    assert info["can_update"] is False
    assert "not a uv tool or pipx install" in info["why_not"]
    assert info["by_hand"][-1] == f"{update.prefix() / 'bin' / 'pip'} install lado=={NEW}"


def test_update_says_an_update_runs_and_the_last_result(client, installed):
    update.write_result(update.Result("running", __version__, NEW, "2026-10-09T10:00:00+00:00"))
    with open(state.home() / "update.lock", "a") as held:
        fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
        held.write("4242")
        held.flush()
        info = ok(client.get("/api/update"))
    assert (info["running"], info["can_update"]) == (True, False)
    assert info["why_not"] == "an update is running, pid 4242"
    assert info["last"]["outcome"] == "running"
    assert info["last"]["from"] == __version__


def test_a_result_of_a_newer_lado_is_named(client, installed):
    update.result_path().write_text(json.dumps({"format": 2}))
    assert ok(client.get("/api/update"))["last"]["problem"] == "written by a newer LADO (format 2)"


def test_the_plan_is_the_one_lado_update_prints(client, installed, repo, fake_tmux):
    runtime.start_session(str(repo), "s", None, provider="claude")
    plan = ok(client.get("/api/update/plan"))
    assert (plan["from"], plan["to"], plan["released"]) == (__version__, NEW, "2026-10-04")
    assert plan["installer"] == "test installer"
    assert plan["command"] == f"/bin/false {NEW}"
    (sess,) = plan["sessions"]
    assert (sess["name"], sess["repo"], sess["open_runs"]) == ("s", str(repo), 0)
    assert sess["agents"] == [{"name": "supervisor", "status": "starting"}]
    assert (plan["server"], plan["gone"], plan["socket"]) == (None, [], runtime.tmux.socket())


def test_no_plan_without_a_newer_version(client, published):
    published(**{__version__: "2026-10-01"})
    assert client.get("/api/update/plan").status_code == 409


def test_the_update_starts_lado_update_detached_and_answers_202(client, installed, spawned):
    answer = client.post("/api/update", json={"to": NEW})
    assert answer.status_code == 202, answer.text
    started = answer.json()
    assert spawned == [(NEW, started["id"])]
    assert started["requested_at"]
    assert started["log"] == str(state.home() / "update.log")


def test_the_update_refuses_another_version_than_the_plans(client, installed, spawned):
    answer = client.post("/api/update", json={"to": "98.0.0"})
    assert answer.status_code == 409
    assert spawned == []


def test_a_second_update_is_refused_while_one_runs(client, installed, spawned):
    with open(state.home() / "update.lock", "a") as held:
        fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
        answer = client.post("/api/update", json={"to": NEW})
    assert answer.status_code == 409
    assert answer.json()["detail"].startswith("an update is running")
    assert spawned == []


def test_the_update_is_refused_without_an_installer(client, installed, spawned, monkeypatch):
    monkeypatch.delenv("LADO_UPDATE_INSTALLER")
    assert client.post("/api/update", json={"to": NEW}).status_code == 409
    assert spawned == []


def test_the_detached_update_is_lado_update_with_its_id(monkeypatch):
    started = {}

    class Popen:
        def __init__(self, argv, **kwargs):
            started.update(argv=argv, **kwargs)

    monkeypatch.setattr(self_update.subprocess, "Popen", Popen)
    self_update.start_detached(NEW, "u-1")
    assert started["argv"][-5:] == ["update", "--yes", NEW, "--id", "u-1"]
    assert started["start_new_session"] is True


@pytest.mark.parametrize(
    ("path", "body"), [("/api/update/check", None), ("/api/update", {"to": NEW})]
)
def test_an_update_needs_the_token_and_the_servers_own_origin(client, path, body, spawned):
    kwargs = {} if body is None else {"json": body}
    del client.headers["origin"]
    assert client.post(path, **kwargs).status_code == 403
    client.headers["origin"] = OWN
    client.cookies.clear()
    assert client.post(path, **kwargs).status_code == 401


@pytest.mark.parametrize("path", ["/api/system", "/api/update/plan"])
def test_the_system_and_the_plan_need_the_token(client, path):
    client.cookies.clear()
    assert client.get(path).status_code == 401


def test_a_cli_whose_version_cannot_be_read_puts_no_path_in_the_report(tmp_path):
    """`--version` that prints nothing, or does not run, leaves its path in the check's
    detail: the report says only that the version is unknown."""
    bin = tmp_path / "bin"
    bin.mkdir()
    for name in ("tmux", "claude", "kilo"):
        (bin / name).write_text("#!/bin/sh\nexit 0\n")  # prints no version
        (bin / name).chmod(0o755)
    (bin / "codex").write_text("not runnable")  # `--version` fails
    found = doctor.system_info(
        lambda command: str(bin / command) if (bin / command).exists() else None
    )
    report = doctor.report(found, False, 60)
    assert str(tmp_path) not in report
    assert "- tmux: version unknown, socket" in report
    assert "  - claude: installed, version unknown\n" in report
    assert "  - codex: installed, version unknown\n" in report
