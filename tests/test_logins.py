"""The agent CLIs' logins in the core (lado.logins): the reason an agent waits with, where a
login variable comes from, the agents and projects that concern a provider, the login
windows' bookkeeping (tmux recorded; the windows run for real in
tests/integration/test_provider_logins.py)."""

import sys

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


TOKEN, KEY = CLAUDE.login_variables
NO_LAYERS = agent_env.Layers({}, {}, {}, {})


def test_layer_names_where_a_variable_comes_from(tmp_path, monkeypatch, inherit):
    folder = tmp_path / "out"
    folder.mkdir()
    monkeypatch.setenv(agent_env.ENV_DIR_VAR, str(folder))
    monkeypatch.setenv(TOKEN, "shell")
    found = agent_env.layers()
    assert logins.layer(TOKEN, found) == logins.INHERITED
    assert logins.layer(KEY, found) == ""
    (folder / TOKEN).write_text("out")
    assert logins.layer(TOKEN, agent_env.layers()) == logins.OUTSIDE == "outside folder"
    project_secrets.write_lado(TOKEN, "lado")
    found = agent_env.layers()
    assert logins.environment(CLAUDE, found)[TOKEN] == "lado"
    assert logins.layer(TOKEN, found) == logins.SECRET == "LADO's secret"


def test_the_login_shell_is_named_as_such(monkeypatch):
    monkeypatch.setattr(agent_env, "source", lambda: agent_env.SHELL)
    found = agent_env.Layers({"X": "1"}, {}, {}, {})
    assert logins.layer("X", found) == logins.SHELL == "login shell"


def test_the_layer_of_a_login_is_the_one_that_gives_it_whole(inherit, monkeypatch):
    monkeypatch.setenv(KEY, "shell-key")
    project_secrets.write_lado(TOKEN, "lado-token")
    found = agent_env.layers()
    env = logins.environment(CLAUDE, found)
    assert (env[TOKEN], KEY in env) == ("lado-token", False)
    assert logins.layer(KEY, found, CLAUDE.login_variables) == ""  # the agents do not get it
    assert logins.layer(KEY, found) == logins.INHERITED  # name by name, as another CLI's
    assert logins.layer(TOKEN, found, CLAUDE.login_variables) == logins.SECRET


@pytest.fixture
def no_windows(monkeypatch):
    monkeypatch.setattr(tmux, "sessions_with", lambda *options: [])


def test_read_gives_the_status_where_it_comes_from_and_the_variables(
    cli_logins, inherit, no_windows, monkeypatch
):
    cli_logins.logged_in()
    monkeypatch.setenv(KEY, "canary-key")  # the login shell's, hidden by the token's layer
    project_secrets.write_lado(TOKEN, "canary-tok")
    found = logins.read(CLAUDE, agent_env.layers())
    assert found.status == base.LoginStatus(
        base.YES, "Subscription (token)", variable=TOKEN, choice="subscription"
    )
    assert (found.layer, found.where) == (logins.SECRET, logins.SECRET)
    assert (found.waiting, found.running, found.projects, found.window) == ([], [], [], False)
    # The status command got the agents' environment: the token, not the shell's key.
    [(argv, given)] = cli_logins.calls
    assert argv[:2] == ["claude", "auth"] and given[TOKEN] == "canary-tok"
    assert KEY not in given
    assert "canary" not in repr(found)


def test_a_login_of_the_clis_own_file_is_named_by_the_provider(
    cli_logins, inherit, no_windows, monkeypatch
):
    monkeypatch.setattr(sys, "platform", "linux")  # not the keychain of a Mac
    cli_logins.logged_in("claude.ai")
    found = logins.read(CLAUDE, agent_env.layers(), full=False)
    assert (found.layer, found.where) == ("", "Claude Code's login file")
    cli_logins.logged_out()
    assert logins.read(CLAUDE, agent_env.layers(), full=False).where == ""


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
    found = logins.read(CLAUDE, agent_env.layers())
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
    found = logins.read(CLAUDE, agent_env.layers())
    assert found.projects == ["acme", "shop"]
    assert "canary" not in repr(found)
    assert logins.read(providers.get("kilo"), NO_LAYERS).projects == []


def test_only_a_login_variable_may_be_lados_secret():
    logins.check_variable(CLAUDE, "ANTHROPIC_API_KEY")
    with pytest.raises(ValueError, match="GH_TOKEN is not a login variable of Claude Code"):
        logins.check_variable(CLAUDE, "GH_TOKEN")
    with pytest.raises(ValueError, match=r"LADO's secrets take: none"):
        logins.check_variable(providers.get("codex"), "OPENAI_API_KEY")


OPENCODE = providers.get("opencode")


def test_an_action_is_found_by_its_id():
    assert logins.action(OPENCODE, "logout").argv == ("opencode", "auth", "logout")
    with pytest.raises(ValueError, match='no login action "nope" \\(known: login, logout\\)'):
        logins.action(OPENCODE, "nope")
    with pytest.raises(ValueError, match="known: none"):
        logins.action(CLAUDE, "login")  # Claude Code logs in by a pasted token or key


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
    assert logins.open_window(OPENCODE, "login") == "lado-login-opencode"
    [(kind, name, _, cmd, options)] = windows["calls"]
    assert (kind, name) == ("new", "lado-login-opencode")
    assert cmd[-3:] == ["opencode", "auth", "login"]
    assert cmd[-4] == str(state.home() / "logins" / "opencode.json")  # the agents' environment
    assert options[logins.LOGIN] == "opencode" and options[logins.HOME] == windows["home"]
    assert options["prefix"] == "None" and options["status"] == "off"
    # Opened again (any action): the same window, no second command.
    assert logins.open_window(OPENCODE, "logout") == "lado-login-opencode"
    assert len(windows["calls"]) == 1
    assert logins.open_windows() == {"opencode": "lado-login-opencode"}
    assert logins.read(OPENCODE, NO_LAYERS).window is True


def test_windows_end_by_their_labels_only(windows):
    windows["rows"] += [
        ["lado-login-codex", "", windows["home"]],  # named like one, no label
        ["theirs", "kilo", "/another/home"],  # another LADO_HOME's
        ["mine", "claude", windows["home"]],  # labelled, whatever its name
    ]
    logins.open_window(OPENCODE, "login")
    assert sorted(logins.end_windows()) == ["lado-login-opencode", "mine"]
    assert [r[0] for r in windows["rows"]] == ["lado-login-codex", "theirs"]


def test_close_window(windows):
    assert logins.close_window(OPENCODE) is False
    logins.open_window(OPENCODE, "login")
    assert logins.close_window(OPENCODE) is True
    assert logins.open_windows() == {}


def test_a_window_needs_a_known_action(windows):
    with pytest.raises(ValueError, match="no login action"):
        logins.open_window(providers.get("codex"), "login")
    assert windows["calls"] == []
