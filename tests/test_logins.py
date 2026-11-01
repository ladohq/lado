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
    assert logins.refusal(CLAUDE, {}, logins.RESUME) == (
        "Claude Code is not logged in, so the session was not resumed: log in in LADO's UI "
        "(Settings → Providers and environment, `lado ui`), or set CLAUDE_CODE_OAUTH_TOKEN "
        "as LADO's secret or a project secret"
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


def test_whether_a_login_is_needed_is_asked_with_the_environment(cli_logins, monkeypatch, inherit):
    """A CLI whose need follows its model (Codex) is asked in the environment the agents
    would start from."""
    cli_logins.logged_out()
    seen = []

    def needs(env):
        seen.append(env.get("MODEL"))
        return env.get("MODEL") == "cloud"

    monkeypatch.setattr(CLAUDE, "needs_login", needs)
    assert logins.refusal(CLAUDE, {"MODEL": "local"}, logins.SESSION) is None
    assert logins.refusal(CLAUDE, {"MODEL": "cloud"}, logins.SESSION) is not None
    assert seen == ["local", "cloud"]
    seen.clear()
    project_secrets.write_lado(KEY, "local-key")  # the agents' environment, as read() gives it
    monkeypatch.setattr(CLAUDE, "needs_login", lambda env: env.get(KEY) != "local-key")
    assert logins.read(CLAUDE, agent_env.layers(), full=False).needs_login is False
    project_secrets.write_lado(KEY, "cloud-key")
    assert logins.read(CLAUDE, agent_env.layers(), full=False).needs_login is True


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
        logins.check_variable(providers.get("kilo"), "OPENAI_API_KEY")
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
    """tmux recorded: the sessions it lists (name, @lado-login, @lado-home, then
    @lado-login-action, pane_dead, pane_dead_status, pane_dead_signal: '' where a row
    leaves them out), the text of each window (`texts`), the calls, and `on_list`, run
    before each listing (tmux's state changing meanwhile)."""
    home = str(state.home().resolve())
    found = {"rows": [], "calls": [], "texts": {}, "on_list": None}

    def made(name, cwd, cmd, options, before_attempt=None):
        found["calls"].append(("new", name, cwd, cmd, options))
        found["rows"].append(
            [name, options[logins.LOGIN], options[logins.HOME], options[logins.ACTION]]
        )
        return []

    def killed(name):
        found["calls"].append(("kill", name))
        found["rows"] = [r for r in found["rows"] if r[0] != name]

    def listed(*options):
        if found["on_list"]:
            found["on_list"]()
        return [(r + [""] * len(options))[: len(options) + 1] for r in found["rows"]]

    monkeypatch.setattr(tmux, "sessions_with", listed)
    monkeypatch.setattr(tmux, "new_labelled_session", made)
    monkeypatch.setattr(tmux, "kill_session", killed)
    monkeypatch.setattr(tmux, "pane_text", lambda name: found["texts"].get(name, ""))
    found["home"] = home
    return found


def dies(windows, name: str, status: str, text: str, signal: str = "") -> list[str]:
    """The command of the window `name` ends with `status` or `signal` (both '' while tmux
    has not got its end yet), its pane kept with `text` (remain-on-exit); its row."""
    [row] = [r for r in windows["rows"] if r[0] == name]
    row[4:] = ["1", status, signal]
    windows["texts"][name] = text
    return row


def test_a_login_window_is_one_per_provider_and_labelled(windows):
    assert logins.open_window(OPENCODE, "login") == "lado-login-opencode"
    [(kind, name, _, cmd, options)] = windows["calls"]
    assert (kind, name) == ("new", "lado-login-opencode")
    assert cmd[-3:] == ["opencode", "auth", "login"]
    # The agents' environment, then the wrapper that keeps the command's exit status.
    assert str(state.home() / "logins" / "opencode.json") in cmd
    assert cmd[-5:-3] == ["lado.logins", str(logins.status_file(OPENCODE))]
    assert options[logins.LOGIN] == "opencode" and options[logins.HOME] == windows["home"]
    assert options["prefix"] == "None" and options["status"] == "off"
    assert options[logins.ACTION] == "login"
    assert options["remain-on-exit"] == "on"  # its text outlives its command
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


CODEX = providers.get("codex")
CODE_TEXT = (
    "1. Open this link in your browser and sign in to your account\n"
    "   https://auth.openai.com/codex/device\n\n"
    "2. Enter this one-time code (expires in 15 minutes)\n"
    "   UBSY-FIU1O\n"
)


def test_a_window_whose_command_ended_counts_as_ended(windows):
    name = logins.open_window(OPENCODE, "login")
    dies(windows, name, "0", "Logged in\n")
    assert logins.open_windows() == {}
    assert logins.read(OPENCODE, NO_LAYERS).window is False
    # Opened again: the dead one goes, a new one runs.
    assert logins.open_window(OPENCODE, "login") == name
    assert [c[0] for c in windows["calls"]] == ["new", "kill", "new"]
    assert logins.open_windows() == {"opencode": name}
    dies(windows, name, "1", "")
    assert logins.close_window(OPENCODE) is True
    dies_and_ends = logins.open_window(OPENCODE, "login")
    dies(windows, dies_and_ends, "1", "")
    assert logins.end_windows() == [name]


def test_a_look_reads_the_code_while_it_runs_and_the_last_words_at_its_end(windows):
    assert logins.look(CODEX) is None  # none open
    name = logins.open_window(CODEX, "login")
    assert logins.look(CODEX) == logins.Look()  # nothing printed yet
    windows["texts"][name] = CODE_TEXT
    prompt = base.LoginPrompt(
        "https://auth.openai.com/codex/device", "UBSY-FIU1O", "expires in 15 minutes"
    )
    assert logins.look(CODEX) == logins.Look(prompt)
    assert logins.look(CODEX, prompt=False) == logins.Look()  # shown already: not read again
    assert ("kill", name) not in windows["calls"]
    # The last line printed just before the exit is kept, read once the command ended.
    dies(windows, name, "1", CODE_TEXT + "\nError: device auth timed out after 15 minutes\n\n\n")
    ended = logins.Ended(1, "Error: device auth timed out after 15 minutes")
    assert logins.look(CODEX) == logins.Look(prompt, ended)
    assert windows["calls"][-1] == ("kill", name)  # read, then gone
    assert logins.look(CODEX) is None


def test_a_look_at_a_window_without_a_code(windows):
    name = logins.open_window(OPENCODE, "login")
    windows["texts"][name] = CODE_TEXT
    assert logins.look(OPENCODE) == logins.Look()  # its action shows no code: not read
    dies(windows, name, "", "", signal="15")  # ended by a signal, nothing said
    assert logins.look(OPENCODE) == logins.Look(ended=logins.Ended(None, ""))


def test_a_dead_pane_s_status_is_the_one_its_command_wrote(windows):
    """Under load tmux may list a pane dead and never give its exit status (seen for 15 s
    and more): a login that succeeded would show as failed (LAD-168 F1). The window's
    wrapper (`main`) writes its command's status; tmux's is only the fallback."""
    name = logins.open_window(CODEX, "login")
    dies(windows, name, "", "Successfully logged in\n")  # tmux has no status
    logins.status_file(CODEX).write_text("0\n")
    assert logins.look(CODEX) == logins.Look(ended=logins.Ended(0, "Successfully logged in"))
    assert windows["calls"][-1] == ("kill", name)
    assert not logins.status_file(CODEX).exists()  # read once
    # Opened again: a status left by an earlier window is not this one's.
    logins.status_file(CODEX).write_text("1\n")
    name = logins.open_window(CODEX, "login")
    assert not logins.status_file(CODEX).exists()
    dies(windows, name, "", "said\n")
    assert logins.look(CODEX) == logins.Look(ended=logins.Ended(None, "said"))


@pytest.mark.parametrize(
    ("script", "status"),
    [("print('Successfully logged in')", 0), ("raise SystemExit(3)", 3)],
)
def test_the_window_s_wrapper_writes_its_command_s_status(tmp_path, script, status):
    file = tmp_path / "codex.status"
    with pytest.raises(SystemExit) as end:
        logins.main([str(file), sys.executable, "-c", script])
    assert end.value.code == status
    assert file.read_text() == f"{status}\n"


def test_a_window_needs_a_known_action(windows):
    with pytest.raises(ValueError, match="no login action"):
        logins.open_window(providers.get("claude"), "login")  # LADO runs none of Claude's
    assert windows["calls"] == []
