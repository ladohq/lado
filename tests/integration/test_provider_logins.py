"""An agent whose CLI needs a login, and the login windows, for real (openspec changes
provider-logins, provider-login-layers): real tmux, the waiting window (`lado login-wait`),
hooks and lado.db, with the fake provider "fake-login" (fake_provider.py), logged in by a
marker file (its own login file), by FAKE_AGENT_TOKEN or by FAKE_AGENT_KEY, each login taken
whole from one layer; the marker is written by the login command (fake_login.py) of
"fake-window" in a login window."""

import json
import subprocess
import time

import agent_helpers
import fake_provider
import pytest

from lado import logins, project_secrets, projects, providers, runtime, state, terminal, tmux
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


def environ(agent: str = "supervisor") -> dict[str, str]:
    path = agent_helpers.fake_logs(SESSION, agent) / "seen.json"
    return json.loads(path.read_text()).get("environ", {}) if path.exists() else {}


def lado_ls() -> str:
    return subprocess.run(
        fake_provider.lado_command("ls"), capture_output=True, text=True, timeout=60, check=True
    ).stdout


def test_an_agent_without_a_login_waits_then_starts_by_itself(repo, marker):
    started = runtime.start_session(str(repo), SESSION, None, PROVIDER)
    assert started.warnings == [reason()]
    assert status() == state.WAITING
    assert runtime.status_reasons(SESSION) == {"supervisor": reason()}
    assert f"waiting: {reason()}" in lado_ls()
    info = models.agent_info(state.get_agent(SESSION, "supervisor"))
    assert info.login_wait == PROVIDER
    # Its window waits: it checks every few seconds, and nothing else happens meanwhile.
    time.sleep(logins.POLL + 0.5)
    assert status() == state.WAITING and environ() == {}

    marker.write_text("logged in")
    wait_status(state.IDLE)  # its first hook came, with no restart
    assert runtime.status_reasons(SESSION) == {}
    assert "fake-login is logged in" not in lado_ls()
    log = (state.home() / "loop.log").read_text()
    assert f"{SESSION}: supervisor: Fake agent is logged in: starting it" in log
    runtime.stop_session(SESSION)


def test_a_lado_secret_saved_meanwhile_reaches_the_waiting_agent(repo, marker):
    runtime.start_session(str(repo), SESSION, None, PROVIDER)
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


def test_a_login_comes_whole_from_the_highest_layer_that_sets_one(
    repo, marker, tmp_path, monkeypatch
):
    outside = tmp_path / "out"
    outside.mkdir()
    (outside / fake_provider.KEY).write_text("canary-out-key")
    monkeypatch.setenv("LADO_ENV_DIR", str(outside))
    project_secrets.write_lado(fake_provider.TOKEN, VALUE)
    runtime.start_session(str(repo), SESSION, None, PROVIDER)
    assert status() != state.WAITING  # logged in by the token
    wait_status(state.IDLE)
    env = environ()
    assert env[fake_provider.TOKEN] == VALUE
    assert fake_provider.KEY not in env  # the outside folder's key never reaches it
    # The key is no login variable of "fake": its worker gets it, with the token.
    runtime.spawn_worker(SESSION, "sleep 0", name="w1", provider="fake")
    wait_status(state.IDLE, "w1")
    env = environ("w1")
    assert (env[fake_provider.KEY], env[fake_provider.TOKEN]) == ("canary-out-key", VALUE)
    runtime.stop_session(SESSION)


def test_a_projects_login_wins_whole(repo, marker, tmp_path, monkeypatch):
    monkeypatch.setenv("LADO_REPOS", str(tmp_path / "ws"))
    projects.create("shop", None)
    agent_helpers.init_repo(projects.folder("shop") / "app")
    projects.set_secret("shop", fake_provider.KEY, "canary-project-key")
    project_secrets.write_lado(fake_provider.TOKEN, VALUE)
    started = runtime.start_session(None, None, None, PROVIDER, project="shop", repo_name="app")
    session = started.session.name
    agent_helpers.wait_for(
        lambda: state.get_agent(session, "supervisor").status == state.IDLE, "idle", session
    )
    path = agent_helpers.fake_logs(session, "supervisor") / "seen.json"
    env = json.loads(path.read_text())["environ"]
    assert env[fake_provider.KEY] == "canary-project-key"
    assert fake_provider.TOKEN not in env
    runtime.stop_session(session)


def test_a_login_it_cannot_read_never_holds_the_agent(repo, marker, monkeypatch):
    monkeypatch.setenv("FAKE_AGENT_LOGIN_STATUS", "unknown")
    started = runtime.start_session(str(repo), SESSION, None, PROVIDER)
    assert started.warnings == [
        "cannot tell whether Fake agent is logged in: `fake auth status` timed out; the agent "
        "starts all the same"
    ]
    assert status() != state.WAITING
    wait_status(state.IDLE)
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


WINDOW = "fake-window"  # logs in by its own command, like OpenCode


def test_a_login_window_runs_the_login_with_the_agents_environment_then_ends(repo, marker):
    provider = providers.get(WINDOW)
    runtime.start_session(str(repo), SESSION, None, PROVIDER)  # it waits for the login
    name = logins.open_window(provider, "login")
    assert logins.open_window(provider, "login") == name  # one per provider
    assert logins.open_windows() == {WINDOW: name}
    assert name not in lado_ls()  # no LADO session
    term = terminal.open_login(WINDOW)
    try:
        shown = _read_until(term, "Paste code here")
        assert "https://login.example.invalid/oauth?state=fake" in shown
        term.write(b"code-42\r")
        agent_helpers.wait_for(lambda: marker.exists(), "the login", SESSION)
        agent_helpers.wait_for(lambda: WINDOW not in logins.open_windows(), "its end", SESSION)
        assert marker.read_text() == "code-42"
        assert terminal.login_ended(WINDOW) is not None
    finally:
        term.close()
    # The waiting agent took the login of the CLI's own file, as Claude Code's agents take
    # a login made outside LADO.
    wait_status(state.IDLE)
    runtime.stop_session(SESSION)


def test_the_login_windows_end_with_lado_stop_all(repo, marker):
    name = logins.open_window(providers.get(WINDOW), "login")
    assert tmux.has_session(name)
    runtime.stop_all(lambda session, stopped: None)
    assert logins.open_windows() == {}
    assert not tmux.has_session(name)
