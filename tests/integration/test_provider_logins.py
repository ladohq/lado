"""An agent whose CLI needs a login, and the login windows, for real (openspec change
provider-logins): real tmux, the waiting window (`lado login-wait`), hooks and lado.db,
with the fake provider "fake-login" (fake_provider.py), logged in by a marker file, by
FAKE_AGENT_TOKEN, or by its login command (fake_login.py) in a login window."""

import json
import subprocess
import time

import agent_helpers
import fake_provider
import pytest

from lado import logins, project_secrets, providers, runtime, state, terminal, tmux
from lado.server import models

pytestmark = pytest.mark.integration

SESSION = "logins"
PROVIDER = "fake-login"
VALUE = "canary-login-7f3a"


@pytest.fixture
def marker(tmp_path, monkeypatch, fakes_known_to_lado):
    """Where the fake CLI's login is (absent: not logged in), in the agents' environment
    (LADO_AGENT_ENV=inherit) and for the waiting window, which knows the fake providers."""
    path = tmp_path / "fake-login"
    monkeypatch.setenv("FAKE_AGENT_LOGIN", str(path))
    return path


def reason() -> str:
    return logins.wait_reason(providers.get(PROVIDER))


def status(agent: str = "supervisor") -> str | None:
    found = state.get_agent(SESSION, agent)
    return found.status if found else None


def wait_status(expected: str, agent: str = "supervisor") -> None:
    agent_helpers.wait_for(lambda: status(agent) == expected, f"{agent} {expected}", SESSION)


def seen(agent: str = "supervisor") -> dict:
    path = agent_helpers.fake_logs(SESSION, agent) / "seen.json"
    return json.loads(path.read_text()) if path.exists() else {}


def environ(agent: str = "supervisor") -> dict[str, str]:
    return seen(agent).get("environ", {})


def lado_ls() -> str:
    return subprocess.run(
        fake_provider.lado_command("ls"), capture_output=True, text=True, timeout=60, check=True
    ).stdout


def stopped_logged_out(repo, marker) -> None:
    """SESSION of PROVIDER started while logged in, stopped, its login gone since: a new one
    is refused, a resume waits for the login (openspec change refuse-start-without-login)."""
    marker.write_text("logged in")
    runtime.start_session(str(repo), SESSION, None, PROVIDER)
    runtime.stop_session(SESSION)
    marker.unlink()


def test_a_new_session_without_a_login_is_refused_by_lado_start(repo, marker):
    found = subprocess.run(
        fake_provider.lado_command(
            "start", str(repo), "--name", SESSION, "--provider", PROVIDER, "--no-attach"
        ),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert found.returncode == 1, found.stderr
    assert found.stderr.splitlines() == [
        "lado: Fake agent is not logged in, so the session was not started: log in in LADO's UI "
        "(Settings → Providers and environment, `lado ui`), or set FAKE_AGENT_TOKEN as LADO's "
        "secret or a project secret"
    ]
    assert state.get_session(SESSION) is None
    assert not tmux.has_session(SESSION)
    assert not (state.home() / "agents" / SESSION).exists()


def test_a_supervisor_spawning_a_worker_without_a_login_gets_the_refusal(repo, marker):
    marker.write_text("logged in")
    runtime.start_session(str(repo), SESSION, None, PROVIDER)
    wait_status(state.IDLE)
    marker.unlink()
    runtime.send_message(SESSION, "human", "supervisor", "spawn sleep 0")
    agent_helpers.wait_for(
        lambda: "spawn_text" in seen(),
        "the spawn's answer",
        SESSION,
    )
    [text] = seen()["spawn_text"]
    assert text.endswith(
        "Fake agent is not logged in, so the worker was not started: ask the human to log in "
        "in Settings → Providers and environment, or start the worker with another provider"
    ), text
    assert [a.name for a in state.list_agents(SESSION)] == ["supervisor"]
    assert runtime.git(str(repo), "branch", "--list", f"lado/{SESSION}/*") == ""
    assert not (repo / ".lado" / "worktrees" / SESSION).exists()
    runtime.stop_session(SESSION)


def test_an_agent_without_a_login_waits_then_starts_by_itself(repo, marker):
    stopped_logged_out(repo, marker)
    started = runtime.start_session(str(repo), SESSION, None)  # a resume
    assert started.resumed
    assert started.warnings == [reason()]
    assert status() == state.WAITING
    assert runtime.status_reasons(SESSION) == {"supervisor": reason()}
    assert f"waiting: {reason()}" in lado_ls()
    info = models.agent_info(state.get_agent(SESSION, "supervisor"))
    assert info.login_wait == PROVIDER
    # Its window waits: it checks every few seconds, and nothing else happens meanwhile.
    seen_before = environ()
    time.sleep(logins.POLL + 0.5)
    assert status() == state.WAITING and environ() == seen_before

    marker.write_text("logged in")
    wait_status(state.IDLE)  # its first hook came, with no restart
    assert runtime.status_reasons(SESSION) == {}
    assert "fake-login is logged in" not in lado_ls()
    log = (state.home() / "loop.log").read_text()
    assert f"{SESSION}: supervisor: Fake agent is logged in: starting it" in log
    runtime.stop_session(SESSION)


def test_a_lado_secret_saved_meanwhile_reaches_the_waiting_agent(repo, marker):
    stopped_logged_out(repo, marker)
    runtime.start_session(str(repo), SESSION, None)
    assert status() == state.WAITING
    project_secrets.write_lado(fake_provider.TOKEN, VALUE)
    wait_status(state.IDLE)
    assert environ()[fake_provider.TOKEN] == VALUE
    # The next agent starts at once with it.
    runtime.spawn_worker(SESSION, "sleep 0", name="w1")
    assert status("w1") != state.WAITING
    wait_status(state.IDLE, "w1")
    assert environ("w1")[fake_provider.TOKEN] == VALUE
    home = state.home()
    records = [home / "lado.db", *(home / n for n in ("hooks.log", "loop.log", "errors.jsonl"))]
    assert [str(p) for p in records if p.is_file() and VALUE.encode() in p.read_bytes()] == []
    assert list((home / "agents").rglob("env.json")) == []
    runtime.stop_session(SESSION)


def test_a_login_it_cannot_read_never_holds_the_agent(repo, marker, monkeypatch):
    monkeypatch.setenv("FAKE_AGENT_LOGIN_STATUS", "unknown")
    started = runtime.start_session(str(repo), SESSION, None, PROVIDER)  # nor refuses it
    assert started.warnings == [
        "cannot tell whether Fake agent is logged in: `fake auth status` timed out; the agent "
        "starts all the same"
    ]
    assert status() != state.WAITING
    wait_status(state.IDLE)
    runtime.spawn_worker(SESSION, "sleep 0", name="w1")
    wait_status(state.IDLE, "w1")
    runtime.stop_session(SESSION)


def _read_until(term, text: str, timeout: float = 20) -> str:
    seen, deadline = b"", time.monotonic() + timeout
    while text.encode() not in seen:
        assert time.monotonic() < deadline, f"no {text!r} in {seen!r}"
        chunk = term.read()
        if chunk is None:
            break
        seen += chunk
    return seen.decode(errors="replace")


def test_a_login_window_runs_the_login_with_the_agents_environment_then_ends(repo, marker):
    provider = providers.get(PROVIDER)
    stopped_logged_out(repo, marker)
    runtime.start_session(str(repo), SESSION, None)  # resumed, it waits for the login
    name = logins.open_window(provider, "login")
    assert logins.open_window(provider, "login") == name  # one per provider
    assert logins.open_windows() == {PROVIDER: name}
    assert name not in lado_ls()  # no LADO session
    term = terminal.open_login(PROVIDER)
    try:
        shown = _read_until(term, "Paste code here")
        assert "https://login.example.invalid/oauth?state=fake" in shown
        term.write(b"code-42\r")
        agent_helpers.wait_for(lambda: marker.exists(), "the login", SESSION)
        agent_helpers.wait_for(lambda: PROVIDER not in logins.open_windows(), "its end", SESSION)
        assert marker.read_text() == "code-42"
        assert terminal.login_ended(PROVIDER) is not None
    finally:
        term.close()
    wait_status(state.IDLE)  # the waiting agent took the login
    runtime.stop_session(SESSION)


def test_the_login_windows_end_with_lado_stop_all(repo, marker):
    name = logins.open_window(providers.get(PROVIDER), "login")
    assert tmux.has_session(name)
    runtime.stop_all(lambda session, stopped: None)
    assert logins.open_windows() == {}
    assert not tmux.has_session(name)
