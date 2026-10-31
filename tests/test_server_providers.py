"""The UI server's API of Settings → Providers and environment (openspec change
provider-logins): each CLI's login, the login window, logout, and the login variables kept
as LADO's secrets. In process, with FastAPI's test client; the CLIs' status commands
answered by tests/conftest.py's cli_logins, tmux recorded for the windows."""

import time

import pytest
from fastapi.testclient import TestClient

from lado import agent_env, logins, project_secrets, projects, providers, runtime, state, tmux
from lado.server import app as server_app
from lado.server import auth, provider_check

PORT = 8126
OWN = "http://testserver"
TOKEN, KEY = "CLAUDE_CODE_OAUTH_TOKEN", "ANTHROPIC_API_KEY"


@pytest.fixture
def client(lado_home, fake_clis, monkeypatch):
    monkeypatch.setenv(agent_env.SOURCE_VAR, agent_env.INHERIT)
    client = TestClient(server_app.create_app(auth.token(), PORT))
    client.cookies.set(auth.cookie_name(PORT), auth.token())
    client.headers["origin"] = OWN
    provider_check.reset()
    yield client
    provider_check.reset()  # its check ended, while the CLIs' answers are the test's
    client.app.state.clones.close()


def _page(client):
    """The section's data once a check started now has ended."""
    assert client.post("/api/providers/check").status_code == 200
    deadline = time.monotonic() + 10
    while (page := client.get("/api/providers/logins").json())["checking"]:
        assert time.monotonic() < deadline, "the check never ended"
        time.sleep(0.01)
    return page


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
    page = _page(client)
    assert [p["cli"]["name"] for p in page["providers"]] == providers.names()
    assert all(p["ready"] for p in page["providers"]) and page["environment"] == ""
    claude = _row(page, "claude")
    assert claude["login"]["state"] == "no"
    assert claude["needs_login"] is True
    assert claude["actions"] == []  # LADO runs no login command of Claude Code
    assert claude["question"] == "How do you pay for Claude?"
    assert [(c["id"], c["variable"]) for c in claude["choices"]] == [
        ("subscription", TOKEN),
        ("usage", KEY),
    ]
    assert claude["choices"][0]["title"] == "Subscription — Claude Pro or Max"
    assert "claude setup-token" in claude["choices"][0]["detail"]
    assert claude["from_lado"] is False
    assert claude["login"] == {
        "state": "no",
        "method": "",
        "where": "",
        "choice": "",
        "problem": "",
    }
    codex = _row(page, "codex")
    assert codex["login"]["state"] == "yes" and codex["login"]["method"] == "ChatGPT"
    assert (codex["actions"], codex["choices"], codex["question"]) == ([], [], "")
    assert "#113" in codex["note"]
    assert [a["id"] for a in _row(page, "opencode")["actions"]] == ["login", "logout"]
    assert "checks" not in page  # lado doctor's lines are lado doctor's


def test_the_page_answers_at_once_and_only_a_post_starts_a_check(
    client, cli_logins, windows, monkeypatch
):
    page = client.get("/api/providers/logins").json()
    assert page["checking"] is False
    assert [p["ready"] for p in page["providers"]] == [False] * len(providers.names())
    assert _row(page, "claude")["cli"]["title"] == "Claude Code"
    assert cli_logins.calls == []  # nothing read
    started = []
    monkeypatch.setattr(provider_check, "start", lambda: started.append(1) or True)
    assert client.post("/api/providers/check").status_code == 200
    assert started == [1]


def test_a_saved_token_starts_a_check(client, cli_logins, windows, monkeypatch):
    started = []
    monkeypatch.setattr(provider_check, "start", lambda: started.append(1) or True)
    row = client.put(f"/api/providers/claude/variables/{TOKEN}", json={"value": "c-5"}).json()
    assert started == [1]
    # The row is kept at once: the section shows it before the check ends.
    assert _row(client.get("/api/providers/logins").json(), "claude") == row
    client.delete("/api/providers/claude/login-secrets")
    client.delete("/api/providers/claude/login")
    assert started == [1, 1, 1]
    client.post("/api/providers/opencode/login", json={"action": "login"})
    assert started == [1, 1, 1]  # opening a window changes no login


def test_the_environments_problem_is_on_the_page(client, windows, monkeypatch):
    def fails():
        raise agent_env.AgentEnvError("the login shell did not answer in 10 s")

    monkeypatch.setattr(agent_env, "layers", fails)
    assert _page(client)["environment"] == "the login shell did not answer in 10 s"


def test_a_cli_not_installed_is_unknown_with_why(client, monkeypatch, windows):
    monkeypatch.setenv("PATH", "/nowhere")
    page = _page(client)
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
    assert row["login"]["method"] == "Subscription (token)"
    assert (row["login"]["where"], row["login"]["choice"]) == ("LADO's secret", "subscription")
    assert row["from_lado"] is True
    _page(client)
    page = client.get("/api/providers/logins")
    assert "canary-1" not in page.text
    # The status command got it, as every agent would.
    assert any(env.get(TOKEN) == "canary-1" for argv, env in cli_logins.calls)
    # One variable alone is not removed: Log out removes the provider's login.
    assert client.delete(f"/api/providers/claude/variables/{TOKEN}").status_code == 405
    assert project_secrets.lado_names() == [TOKEN]


def test_a_saved_key_replaces_lados_token_and_beats_the_outside_folders(
    client, cli_logins, windows, tmp_path, monkeypatch
):
    outside = tmp_path / "out"
    outside.mkdir()
    (outside / TOKEN).write_text("canary-out")
    monkeypatch.setenv(agent_env.ENV_DIR_VAR, str(outside))
    client.put(f"/api/providers/claude/variables/{TOKEN}", json={"value": "canary-tok"})
    cli_logins.logged_in("api_key")
    answer = client.put(f"/api/providers/claude/variables/{KEY}", json={"value": "canary-key"})
    assert answer.status_code == 200, answer.text
    assert project_secrets.lado_names() == [KEY]  # one login in LADO's secrets
    row = answer.json()
    assert (row["login"]["method"], row["login"]["where"]) == (
        "Pay per use (API key)",
        "LADO's secret",
    )
    assert row["from_lado"] is True
    # The status command, as every agent, got the key and not the outside folder's token
    # (the check the save started reads the other CLIs too).
    _, env = [c for c in cli_logins.calls if c[0][0] == "claude"][-1]
    assert env[KEY] == "canary-key" and TOKEN not in env
    assert "canary" not in answer.text


def test_logging_out_removes_lados_login_and_shows_what_is_left(
    client, cli_logins, windows, tmp_path, monkeypatch
):
    outside = tmp_path / "out"
    outside.mkdir()
    (outside / TOKEN).write_text("canary-out")
    monkeypatch.setenv(agent_env.ENV_DIR_VAR, str(outside))
    project_secrets.write_lado(KEY, "canary-key")
    cli_logins.logged_in()
    answer = client.delete("/api/providers/claude/login-secrets")
    assert answer.status_code == 200, answer.text
    assert project_secrets.lado_names() == []
    row = answer.json()
    assert (row["login"]["where"], row["from_lado"]) == ("outside folder", False)
    assert "canary" not in answer.text
    assert client.delete("/api/providers/nope/login-secrets").status_code == 404
    # Claude Code's own logout is gone with its route.
    assert client.post("/api/providers/claude/logout").status_code in (404, 405)
    assert not [argv for argv, _ in cli_logins.calls if argv[1:3] == ["auth", "logout"]]


def test_only_a_login_variable_may_be_set(client, windows):
    answer = client.put("/api/providers/claude/variables/GH_TOKEN", json={"value": "canary-2"})
    assert answer.status_code == 400
    assert "GH_TOKEN is not a login variable of Claude Code" in answer.json()["detail"]
    assert "canary-2" not in answer.text
    assert (
        client.put("/api/providers/codex/variables/OPENAI_API_KEY", json={"value": "x"}).status_code
        == 400
    )
    assert (
        client.put(f"/api/providers/nope/variables/{TOKEN}", json={"value": "x"}).status_code == 404
    )
    assert (
        client.put(f"/api/providers/claude/variables/{TOKEN}", json={"value": ""}).status_code
        == 400
    )
    assert not (state.home() / "secrets").exists()


@pytest.mark.parametrize(
    ("value", "why"),
    [
        pytest.param("canary\0x", "is not UTF-8 text", id="nul"),
        pytest.param("x" * (64 * 1024 + 1), "is larger than 64 KiB", id="too-large"),
    ],
)
def test_a_value_the_agents_could_not_get_is_refused(client, value, why):
    """The reader of LADO's secrets drops such a file, which the row would show as set."""
    answer = client.put(f"/api/providers/claude/variables/{TOKEN}", json={"value": value})
    assert answer.status_code == 400
    assert answer.json()["detail"] == f"the value of {TOKEN} {why}"
    assert "canary" not in answer.text
    assert project_secrets.lado_names() == []


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
    assert client.delete("/api/providers/claude/login-secrets").status_code == 403
    assert client.post("/api/providers/opencode/login", json={"action": "login"}).status_code == 403
    client.headers["origin"] = OWN
    client.cookies.clear()
    assert (
        client.put(f"/api/providers/claude/variables/{TOKEN}", json={"value": "x"}).status_code
        == 401
    )
    assert client.get("/api/providers/logins").status_code == 401
    assert project_secrets.lado_names() == []


def test_a_login_window_opens_once_and_closes(client, windows):
    answer = client.post("/api/providers/opencode/login", json={"action": "login"})
    assert answer.status_code == 200, answer.text
    assert answer.json()["window"] is True
    [(options, cmd)] = windows.values()
    assert cmd[-3:] == ["opencode", "auth", "login"]
    assert options[logins.LOGIN] == "opencode"
    client.post("/api/providers/opencode/login", json={"action": "logout"})
    assert len(windows) == 1  # the one open is kept
    answer = client.delete("/api/providers/opencode/login")
    assert answer.json()["window"] is False and windows == {}


def test_a_login_window_needs_a_known_action(client, windows):
    answer = client.post("/api/providers/claude/login", json={"action": "login"})
    assert answer.status_code == 400 and "no login action" in answer.json()["detail"]
    assert client.post("/api/providers/opencode/login", json={}).status_code == 422
    assert windows == {}


def test_the_row_names_waiting_and_running_agents_and_projects(
    client, cli_logins, windows, repo, fake_tmux, tmp_path, monkeypatch
):
    runtime.start_session(str(repo), "s", None, provider="claude")
    runtime.stop_session("s")
    cli_logins.logged_out()
    runtime.start_session(str(repo), "s", None, reason=runtime.AT_START)  # it waits
    monkeypatch.setenv("LADO_REPOS", str(tmp_path / "ws"))
    projects.create("shop", None)
    projects.set_secret("shop", TOKEN, "canary-4")
    claude = _row(_page(client), "claude")
    assert claude["waiting"] == [{"session": "s", "agent": "supervisor"}]
    assert claude["running"] == [{"session": "s", "agent": "supervisor"}]
    assert claude["projects"] == ["shop"]
    [agent] = client.get("/api/sessions/s/agents").json()
    assert agent["login_wait"] == "claude"
    assert agent["status_reason"] == logins.wait_reason(providers.get("claude"))
    # Logged in, the row names no agent that waits, though its window has not looked yet.
    cli_logins.logged_in()
    row = client.put(f"/api/providers/claude/variables/{TOKEN}", json={"value": "c-6"}).json()
    assert row["login"]["state"] == "yes" and row["waiting"] == []
    assert state.get_agent("s", "supervisor").status == state.WAITING
    assert _row(_page(client), "claude")["waiting"] == []


def test_no_login_wait_for_another_reason(client, repo, fake_tmux, claude_config):
    claude_config.refuse()
    runtime.start_session(str(repo), "s", None, provider="claude")
    [agent] = client.get("/api/sessions/s/agents").json()
    assert agent["status"] == "waiting" and agent["login_wait"] is None
