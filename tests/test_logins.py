"""The agent CLIs' logins in the core (lado.logins): the reason an agent waits with, where a
login variable comes from, the agents and projects that concern a provider, the login
windows' bookkeeping (tmux recorded; the windows run for real in
tests/integration/test_provider_logins.py)."""

import pytest

from lado import agent_env, logins, project_secrets, projects, providers, state, tmux
from lado.providers import base

CLAUDE = providers.get("claude")


def test_the_wait_reason_names_settings_and_the_first_login_variable():
    assert logins.wait_reason(CLAUDE) == (
        "Claude Code is not logged in: log in in Settings → Providers and environment, or set "
        "CLAUDE_CODE_OAUTH_TOKEN; the agent starts by itself once you do"
    )
    assert logins.wait_reason(providers.get("kilo")) == (
        "Kilo CLI is not logged in: log in in Settings → Providers and environment; the agent "
        "starts by itself once you do"
    )


def test_a_cli_that_needs_a_login_and_has_none_is_refused(cli_logins):
    cli_logins.logged_out()
    assert logins.refusal(CLAUDE, {}, logins.SESSION) == (
        "Claude Code is not logged in, so the session was not started: log in in LADO's UI "
        "(Settings → Providers and environment, `lado ui`), or set CLAUDE_CODE_OAUTH_TOKEN "
        "as LADO's secret or a project secret"
    )
    assert logins.refusal(CLAUDE, {}, logins.WORKER) == (
        "Claude Code is not logged in, so the worker was not started: ask the human to log "
        "in in Settings → Providers and environment, or start the worker with another provider"
    )
    # Read in the environment given, the one the agent would start from.
    cli_logins.calls.clear()
    logins.refusal(CLAUDE, {"MARK": "1"}, logins.SESSION)
    assert [env["MARK"] for _, env in cli_logins.calls] == ["1"]


def test_a_login_an_unknown_one_or_no_need_refuses_nothing(cli_logins):
    cli_logins.logged_in()
    assert logins.refusal(CLAUDE, {}, logins.SESSION) is None
    cli_logins.answer("claude", "`claude auth status --json` timed out after 10 s")
    assert logins.refusal(CLAUDE, {}, logins.SESSION) is None
    cli_logins.logged_out()
    for name in ("codex", "kilo", "opencode"):
        assert logins.refusal(providers.get(name), {}, logins.WORKER) is None


def _agent(session, name, provider="claude", status=state.STARTING):
    return state.Agent(session, name, "role", "/r", None, None, status, provider)


def test_waits_for_reads_the_reason_only():
    agent = _agent("s", "sup")
    assert logins.waits_for(agent, logins.wait_reason(CLAUDE)) == "claude"
    assert logins.waits_for(agent, "something else") is None
    assert logins.waits_for(agent, None) is None
    other = _agent("s", "w", provider="codex")
    assert logins.waits_for(other, logins.wait_reason(CLAUDE)) is None
    assert logins.waits_for(_agent("s", "x", provider="gone"), "r") is None


@pytest.fixture
def inherit(monkeypatch):
    monkeypatch.setenv(agent_env.SOURCE_VAR, agent_env.INHERIT)


def test_layer_names_where_a_variable_comes_from(tmp_path, monkeypatch, inherit):
    folder = tmp_path / "out"
    folder.mkdir()
    monkeypatch.setenv(agent_env.ENV_DIR_VAR, str(folder))
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "shell")
    env = logins.environment()
    assert logins.layer("CLAUDE_CODE_OAUTH_TOKEN", env) == logins.INHERITED
    assert logins.layer("ANTHROPIC_API_KEY", env) == ""
    (folder / "CLAUDE_CODE_OAUTH_TOKEN").write_text("out")
    assert logins.layer("CLAUDE_CODE_OAUTH_TOKEN", logins.environment()) == logins.OUTSIDE
    project_secrets.write_lado("CLAUDE_CODE_OAUTH_TOKEN", "lado")
    env = logins.environment()
    assert env["CLAUDE_CODE_OAUTH_TOKEN"] == "lado"
    assert logins.layer("CLAUDE_CODE_OAUTH_TOKEN", env) == logins.SECRET == "LADO's secret"


def test_the_login_shell_is_named_as_such(monkeypatch):
    monkeypatch.setattr(agent_env, "source", lambda: agent_env.SHELL)
    assert logins.layer("X", {"X": "1"}) == logins.SHELL


@pytest.fixture
def no_windows(monkeypatch):
    monkeypatch.setattr(tmux, "sessions_with", lambda *options: [])


def test_read_gives_the_status_its_source_and_the_variables(cli_logins, inherit, no_windows):
    cli_logins.logged_in()
    project_secrets.write_lado("CLAUDE_CODE_OAUTH_TOKEN", "canary-tok")
    env = logins.environment()
    found = logins.read(CLAUDE, env)
    assert found.status == base.LoginStatus(base.YES, "token", variable="CLAUDE_CODE_OAUTH_TOKEN")
    assert found.layer == logins.SECRET
    assert found.variables == [
        logins.Variable("CLAUDE_CODE_OAUTH_TOKEN", True, logins.SECRET),
        logins.Variable("ANTHROPIC_API_KEY", False, ""),
    ]
    assert (found.waiting, found.running, found.projects, found.window) == ([], [], [], False)
    # The status command got the agents' environment, with the token.
    [(argv, given)] = cli_logins.calls
    assert argv[:2] == ["claude", "auth"] and given["CLAUDE_CODE_OAUTH_TOKEN"] == "canary-tok"
    assert "canary-tok" not in repr(found)


def test_read_names_the_waiting_and_running_agents(lado_home, inherit, no_windows):
    state.add_session(state.Session("s", "/r", None, "claude"))
    state.add_session(state.Session("old", "/r", None, "claude"))
    state.add_agent(_agent("s", "supervisor"))
    state.add_agent(_agent("s", "dev"))
    state.add_agent(_agent("s", "rev", provider="codex"))
    state.add_agent(_agent("old", "supervisor"))
    state.stop_session("old")
    state.block("s", "supervisor", logins.wait_reason(CLAUDE))
    state.block("s", "dev", "Claude Code asks whether to trust /r: …")
    found = logins.read(CLAUDE, logins.environment())
    assert found.waiting == [logins.AgentRef("s", "supervisor")]
    assert found.running == [logins.AgentRef("s", "supervisor"), logins.AgentRef("s", "dev")]


def test_read_names_the_projects_with_a_login_of_their_own(
    tmp_path, monkeypatch, inherit, no_windows
):
    monkeypatch.setenv("LADO_REPOS", str(tmp_path / "ws"))
    for id in ("shop", "acme", "plain"):
        projects.create(id, None)
    projects.set_secret("shop", "CLAUDE_CODE_OAUTH_TOKEN", "canary-s")
    projects.set_secret("acme", "ANTHROPIC_API_KEY", "canary-a")
    projects.set_variable("plain", "OTHER", "x")
    found = logins.read(CLAUDE, logins.environment())
    assert found.projects == ["acme", "shop"]
    assert "canary" not in repr(found)
    assert logins.read(providers.get("kilo"), {}).projects == []


def test_only_a_login_variable_may_be_lados_secret():
    logins.check_variable(CLAUDE, "ANTHROPIC_API_KEY")
    with pytest.raises(ValueError, match="GH_TOKEN is not a login variable of Claude Code"):
        logins.check_variable(CLAUDE, "GH_TOKEN")
    with pytest.raises(ValueError, match=r"LADO's secrets take: none"):
        logins.check_variable(providers.get("codex"), "OPENAI_API_KEY")


def test_an_action_is_found_by_its_id():
    assert logins.action(CLAUDE, "login").argv[-1] == "--claudeai"
    with pytest.raises(
        ValueError, match='no login action "nope" \\(known: login, login-console\\)'
    ):
        logins.action(CLAUDE, "nope")
    with pytest.raises(ValueError, match="known: none"):
        logins.action(providers.get("codex"), "login")


@pytest.fixture
def windows(monkeypatch, lado_home, inherit, fake_clis):
    """tmux recorded: the sessions it lists (name, @lado-login, @lado-home) and the calls."""
    home = str(state.home().resolve())
    found = {"rows": [], "calls": []}

    def made(name, cwd, cmd, options, before_attempt=None):
        found["calls"].append(("new", name, cwd, cmd, options))
        found["rows"].append([name, options[logins.LOGIN], options[logins.HOME]])
        return []

    def killed(name):
        found["calls"].append(("kill", name))
        found["rows"] = [r for r in found["rows"] if r[0] != name]

    monkeypatch.setattr(tmux, "sessions_with", lambda *options: list(found["rows"]))
    monkeypatch.setattr(tmux, "new_labelled_session", made)
    monkeypatch.setattr(tmux, "kill_session", killed)
    found["home"] = home
    return found


def test_a_login_window_is_one_per_provider_and_labelled(windows):
    assert logins.open_window(CLAUDE, "login") == "lado-login-claude"
    [(kind, name, _, cmd, options)] = windows["calls"]
    assert (kind, name) == ("new", "lado-login-claude")
    assert cmd[-4:] == ["claude", "auth", "login", "--claudeai"]
    assert cmd[-5] == str(state.home() / "logins" / "claude.json")  # the agents' environment
    assert options[logins.LOGIN] == "claude" and options[logins.HOME] == windows["home"]
    assert options["prefix"] == "None" and options["status"] == "off"
    # Opened again (any action): the same window, no second command.
    assert logins.open_window(CLAUDE, "login-console") == "lado-login-claude"
    assert len(windows["calls"]) == 1
    assert logins.open_windows() == {"claude": "lado-login-claude"}
    assert logins.read(CLAUDE, {}).window is True


def test_windows_end_by_their_labels_only(windows):
    windows["rows"] += [
        ["lado-login-codex", "", windows["home"]],  # named like one, no label
        ["theirs", "kilo", "/another/home"],  # another LADO_HOME's
        ["mine", "opencode", windows["home"]],  # labelled, whatever its name
    ]
    logins.open_window(CLAUDE, "login")
    assert sorted(logins.end_windows()) == ["lado-login-claude", "mine"]
    assert [r[0] for r in windows["rows"]] == ["lado-login-codex", "theirs"]


def test_close_window(windows):
    assert logins.close_window(CLAUDE) is False
    logins.open_window(CLAUDE, "login")
    assert logins.close_window(CLAUDE) is True
    assert logins.open_windows() == {}


def test_a_window_needs_a_known_action(windows):
    with pytest.raises(ValueError, match="no login action"):
        logins.open_window(providers.get("codex"), "login")
    assert windows["calls"] == []
