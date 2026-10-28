"""The UI server's API of Settings → Providers and environment (openspec change
provider-logins): each CLI's login, the login window, logout, and the login variables kept
as LADO's secrets. In process, with FastAPI's test client; the CLIs' status commands
answered by tests/conftest.py's cli_logins, tmux recorded for the windows."""

import json

import pytest
from fastapi.testclient import TestClient

from lado import agent_env, logins, project_secrets, projects, providers, runtime, state, tmux
from lado.server import app as server_app
from lado.server import auth

PORT = 8126
OWN = "http://testserver"
TOKEN = "CLAUDE_CODE_OAUTH_TOKEN"


@pytest.fixture
def client(lado_home, fake_clis, monkeypatch):
    monkeypatch.setenv(agent_env.SOURCE_VAR, agent_env.INHERIT)
    client = TestClient(server_app.create_app(auth.token(), PORT))
    client.cookies.set(auth.cookie_name(PORT), auth.token())
    client.headers["origin"] = OWN
    yield client
    client.app.state.clones.close()


@pytest.fixture
def windows(monkeypatch):
    """tmux's login sessions, recorded: name -> (labels, command)."""
    made: dict[str, tuple[dict, list[str]]] = {}
    home = str(state.home().resolve())

    def new(name, cwd, cmd, options, before_attempt=None):
        made[name] = (options, cmd)
        return []

    monkeypatch.setattr(tmux, "new_labelled_session", new)
    monkeypatch.setattr(tmux, "kill_session", lambda name: made.pop(name))
    monkeypatch.setattr(
        tmux,
        "sessions_with",
        lambda *o: [[n, opts[logins.LOGIN], home] for n, (opts, _) in made.items()],
    )
    return made


def _row(page, name):
    return next(p for p in page["providers"] if p["cli"]["name"] == name)


def test_the_page_lists_each_cli_with_its_login(client, cli_logins, windows):
    cli_logins.logged_out()
    cli_logins.answer("codex", 0, "Logged in using ChatGPT\n")
    answer = client.get("/api/providers/logins")
    assert answer.status_code == 200, answer.text
    page = answer.json()
    assert [p["cli"]["name"] for p in page["providers"]] == providers.names()
    claude = _row(page, "claude")
    assert claude["login"]["state"] == "no"
    assert claude["needs_login"] is True
    assert [a["id"] for a in claude["actions"]] == ["login", "login-console"]
    assert claude["can_logout"] is True
    assert claude["variables"] == [
        {"name": TOKEN, "secret": False, "layer": ""},
        {"name": "ANTHROPIC_API_KEY", "secret": False, "layer": ""},
    ]
    codex = _row(page, "codex")
    assert codex["login"]["state"] == "yes" and codex["login"]["method"] == "ChatGPT"
    assert codex["actions"] == [] and codex["can_logout"] is False
    assert "#113" in codex["note"]
    names = [c["name"] for c in page["checks"]]
    assert "Claude Code" in names and "Claude Code login" in names
    assert "Agent environment" in names


def test_a_cli_not_installed_is_unknown_with_why(client, monkeypatch, windows):
    monkeypatch.setenv("PATH", "/nowhere")
    page = client.get("/api/providers/logins").json()
    claude = _row(page, "claude")
    assert claude["cli"]["installed"] is False
    assert claude["login"] == {**claude["login"], "state": "unknown", "problem": "not installed"}


def test_a_saved_token_is_lados_secret_and_never_given_back(client, cli_logins, windows):
    answer = client.put(f"/api/providers/claude/variables/{TOKEN}", json={"value": "canary-1"})
    assert answer.status_code == 200, answer.text
    assert "canary-1" not in answer.text
    folder = state.home() / "secrets"
    assert (folder / TOKEN).read_text() == "canary-1"
    assert (folder / TOKEN).stat().st_mode & 0o777 == 0o600
    assert folder.stat().st_mode & 0o777 == 0o700
    row = answer.json()
    assert row["variables"][0] == {"name": TOKEN, "secret": True, "layer": "LADO's secret"}
    page = client.get("/api/providers/logins")
    assert "canary-1" not in page.text
    # The status command got it, as every agent would.
    assert any(env.get(TOKEN) == "canary-1" for argv, env in cli_logins.calls)
    answer = client.delete(f"/api/providers/claude/variables/{TOKEN}")
    assert answer.status_code == 200
    assert answer.json()["variables"][0]["secret"] is False
    assert project_secrets.lado_names() == []


def test_only_a_login_variable_may_be_set(client, windows):
    answer = client.put("/api/providers/claude/variables/GH_TOKEN", json={"value": "canary-2"})
    assert answer.status_code == 400
    assert "GH_TOKEN is not a login variable of Claude Code" in answer.json()["detail"]
    assert "canary-2" not in answer.text
    assert (
        client.put("/api/providers/codex/variables/OPENAI_API_KEY", json={"value": "x"}).status_code
        == 400
    )
    assert client.delete("/api/providers/claude/variables/GH_TOKEN").status_code == 400
    assert (
        client.put(f"/api/providers/nope/variables/{TOKEN}", json={"value": "x"}).status_code == 404
    )
    assert (
        client.put(f"/api/providers/claude/variables/{TOKEN}", json={"value": ""}).status_code
        == 400
    )
    assert not (state.home() / "secrets").exists()


@pytest.mark.parametrize("body", [{"secret": "canary-3"}, {"value": 5}, {"value": ["canary-3"]}])
def test_a_body_the_server_cannot_read_is_not_echoed(client, body):
    answer = client.put(f"/api/providers/claude/variables/{TOKEN}", json=body)
    assert answer.status_code == 422
    assert "canary-3" not in answer.text and '"input"' not in answer.text


def test_the_variables_need_the_token_and_the_servers_own_origin(client):
    del client.headers["origin"]
    assert (
        client.put(f"/api/providers/claude/variables/{TOKEN}", json={"value": "x"}).status_code
        == 403
    )
    assert client.post("/api/providers/claude/logout").status_code == 403
    assert client.post("/api/providers/claude/login", json={"action": "login"}).status_code == 403
    client.headers["origin"] = OWN
    client.cookies.clear()
    assert (
        client.put(f"/api/providers/claude/variables/{TOKEN}", json={"value": "x"}).status_code
        == 401
    )
    assert client.get("/api/providers/logins").status_code == 401
    assert project_secrets.lado_names() == []


def test_a_login_window_opens_once_and_closes(client, windows):
    answer = client.post("/api/providers/claude/login", json={"action": "login"})
    assert answer.status_code == 200, answer.text
    assert answer.json()["window"] is True
    [(options, cmd)] = windows.values()
    assert cmd[-4:] == ["claude", "auth", "login", "--claudeai"]
    assert options[logins.LOGIN] == "claude"
    client.post("/api/providers/claude/login", json={"action": "login-console"})
    assert len(windows) == 1  # the one open is kept
    answer = client.delete("/api/providers/claude/login")
    assert answer.json()["window"] is False and windows == {}


def test_a_login_window_needs_a_known_action(client, windows):
    answer = client.post("/api/providers/codex/login", json={"action": "login"})
    assert answer.status_code == 400 and "no login action" in answer.json()["detail"]
    assert client.post("/api/providers/claude/login", json={}).status_code == 422
    assert windows == {}


def test_logout_runs_the_clis_own_logout(client, cli_logins, windows):
    cli_logins.answer("claude", 0, json.dumps({"loggedIn": False, "authMethod": "none"}))
    answer = client.post("/api/providers/claude/logout")
    assert answer.status_code == 200, answer.text
    assert ["claude", "auth", "logout"] in [argv for argv, env in cli_logins.calls]
    assert answer.json()["login"]["state"] == "no"
    refused = client.post("/api/providers/kilo/logout")
    assert refused.status_code == 400 and "login window" in refused.json()["detail"]


def test_a_failed_logout_says_why(client, cli_logins, windows):
    cli_logins.answer("claude", 1, "", "boom\n")
    answer = client.post("/api/providers/claude/logout")
    assert answer.status_code == 400
    assert answer.json()["detail"] == "`claude auth logout` failed with exit status 1: boom"


def test_the_row_names_waiting_and_running_agents_and_projects(
    client, cli_logins, windows, repo, fake_tmux, tmp_path, monkeypatch
):
    cli_logins.logged_out()
    runtime.start_session(str(repo), "s", None, provider="claude")
    monkeypatch.setenv("LADO_REPOS", str(tmp_path / "ws"))
    projects.create("shop", None)
    projects.set_secret("shop", TOKEN, "canary-4")
    claude = _row(client.get("/api/providers/logins").json(), "claude")
    assert claude["waiting"] == [{"session": "s", "agent": "supervisor"}]
    assert claude["running"] == [{"session": "s", "agent": "supervisor"}]
    assert claude["projects"] == ["shop"]
    [agent] = client.get("/api/sessions/s/agents").json()
    assert agent["login_wait"] == "claude"
    assert agent["status_reason"] == logins.wait_reason(providers.get("claude"))


def test_no_login_wait_for_another_reason(client, repo, fake_tmux, claude_config):
    claude_config.refuse()
    runtime.start_session(str(repo), "s", None, provider="claude")
    [agent] = client.get("/api/sessions/s/agents").json()
    assert agent["status"] == "waiting" and agent["login_wait"] is None
