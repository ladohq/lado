"""The window of an agent that waits for its CLI's login (lado.login_wait): it checks again
with the file layers read anew, never over LADO's and the provider's own variables, then
settles what the CLI asks first and runs it. With real processes:
tests/integration/test_provider_logins.py."""

import json
import os

import pytest

from lado import agent_env, login_wait, logins, project_secrets, projects, providers, state
from lado.providers import base


class Waiting(base.Provider):
    """A provider whose CLI is logged in after `logged_in_after` looks."""

    name = "waits"
    title = "Waits CLI"
    command = "sh"
    install_hint = ""
    permission_modes = ()
    capabilities = base.Capabilities(
        status_events=True,
        permission_event=False,
        deliver_on_turn_end=False,
        skills=False,
        needs_login=True,
    )
    login_variables = ("WAITS_TOKEN", "WAITS_KEY")

    def __init__(self, logged_in_after=2, blocker=None, answer=base.NO):
        self.looks: list[dict] = []
        self.logged_in_after = logged_in_after
        self.blocker = blocker or base.Blocker()
        self.answer = answer
        self.blocked_with: list[dict] = []

    def login_status(self, env):
        self.looks.append(dict(env))
        if env.get("WAITS_TOKEN") or len(self.looks) > self.logged_in_after:
            return base.LoginStatus(base.YES, "token")
        return base.LoginStatus(self.answer, problem="odd" if self.answer == base.UNKNOWN else "")

    def first_hook_blocker(self, cwd, env):
        self.blocked_with.append(dict(env))
        return self.blocker

    def launch_command(self, agent, session, spec, notice=None):
        raise NotImplementedError

    def parse_event(self, native, payload):
        return None


@pytest.fixture
def started(lado_home, monkeypatch):
    """A session `s` whose agent `sup` waits for its login; exec recorded, no sleep."""
    state.add_session(state.Session("s", "/r", None, "waits"))
    state.add_agent(state.Agent("s", "sup", "role", "/r", None, None, state.STARTING, "waits"))
    provider = Waiting()
    monkeypatch.setitem(providers._PROVIDERS, "waits", provider)
    state.block("s", "sup", logins.wait_reason(provider))
    calls = {"exec": [], "sleeps": 0}
    monkeypatch.setattr(os, "execvpe", lambda *a: calls["exec"].append(a))
    monkeypatch.setattr(
        login_wait.time, "sleep", lambda s: calls.__setitem__("sleeps", calls["sleeps"] + 1)
    )
    calls["provider"] = provider
    return calls


ENV = {"LADO_SESSION": "s", "LADO_AGENT": "sup", "PATH": os.environ["PATH"], "KEEP": "1"}


def _run(
    tmp_path,
    lado_home,
    env=None,
    ours=(),
    project=None,
    argv=("sh", "-c", "true"),
    shell_login=None,
):
    file = tmp_path / "env.json"
    env = {**ENV, "LADO_HOME": str(lado_home), **(env or {})}
    command = login_wait.command(
        file, "waits", env, list(ours), project, shell_login or {}, list(argv)
    )
    login_wait.main(command[command.index("login-wait") + 1 :])
    return file


def test_the_command_keeps_the_environment_in_a_private_file(tmp_path, lado_home, monkeypatch):
    monkeypatch.setattr(providers, "lado_command", lambda *a: ["lado", *a])
    file = tmp_path / "env.json"
    env = {"PATH": os.environ["PATH"], "TOKEN": "canary"}
    shell = {"TOKEN": "canary"}
    argv = login_wait.command(file, "claude", env, ["LADO_HOME"], "shop", shell, ["sh", "-c", "x"])
    assert argv == ["lado", "login-wait", "claude", str(file), "sh", "-c", "x"]
    assert file.stat().st_mode & 0o777 == 0o600
    assert json.loads(file.read_text()) == {
        "env": env,
        "ours": ["LADO_HOME"],
        "project": "shop",
        "shell_login": shell,
    }
    assert "canary" not in " ".join(argv)
    with pytest.raises(agent_env.AgentEnvError, match="not on the agents' PATH"):
        login_wait.command(file, "claude", {"PATH": str(tmp_path)}, [], None, {}, ["nope"])


def test_it_waits_then_runs_the_cli_with_its_environment(tmp_path, lado_home, started):
    file = _run(tmp_path, lado_home)
    assert not file.exists()  # read and removed at once: it holds the user's keys
    provider = started["provider"]
    assert len(provider.looks) == 3 and started["sleeps"] == 2
    [(program, argv, env)] = started["exec"]
    assert (program, argv) == ("sh", ["sh", "-c", "true"])
    assert env["KEEP"] == "1" and env["LADO_SESSION"] == "s"
    assert provider.blocked_with and provider.blocked_with[0]["KEEP"] == "1"
    # The login came: the agent starts, no longer waiting for it.
    assert state.get_agent("s", "sup").status == state.STARTING
    assert state.block_reasons("s") == {}
    assert "sup: Waits CLI is logged in: starting it" in (lado_home / "loop.log").read_text()


def test_a_lado_secret_saved_meanwhile_reaches_the_cli(tmp_path, lado_home, started):
    started["provider"].logged_in_after = 99

    def save(seconds):
        started["sleeps"] += 1
        project_secrets.write_lado("WAITS_TOKEN", "canary-tok")

    login_wait.time.sleep = save
    _run(tmp_path, lado_home)
    [(_, _, env)] = started["exec"]
    assert env["WAITS_TOKEN"] == "canary-tok"


def test_a_token_saved_meanwhile_takes_the_whole_login_from_the_shells_key(
    tmp_path, lado_home, started
):
    started["provider"].logged_in_after = 99  # logged in by WAITS_TOKEN alone

    def save(seconds):
        started["sleeps"] += 1
        project_secrets.write_lado("WAITS_TOKEN", "canary-tok")

    login_wait.time.sleep = save
    _run(tmp_path, lado_home, {"WAITS_KEY": "shell-key"}, shell_login={"WAITS_KEY": "shell-key"})
    [(_, _, env)] = started["exec"]
    assert env["WAITS_TOKEN"] == "canary-tok"
    assert "WAITS_KEY" not in env


def test_a_login_of_a_layer_removed_meanwhile_falls_back_to_the_shells(tmp_path, lado_home):
    # The key came from LADO's secrets at the launch, which no longer hold it.
    env = {"WAITS_KEY": "lado-key", "KEEP": "1"}
    found = login_wait.layers(env, [], None, ("WAITS_TOKEN", "WAITS_KEY"), {"WAITS_TOKEN": "sh"})
    assert found == {"KEEP": "1", "WAITS_TOKEN": "sh"}


def test_the_layers_go_over_what_it_holds_but_not_over_lados_own(
    tmp_path, lado_home, started, monkeypatch
):
    started["provider"].logged_in_after = 1
    outside = tmp_path / "out"
    outside.mkdir()
    (outside / "FROM_OUT").write_text("new")
    (outside / "LADO_OWN").write_text("theirs")  # a reserved name the reader drops anyway
    (outside / "PROVIDERS").write_text("theirs")
    monkeypatch.setenv("LADO_REPOS", str(tmp_path / "ws"))
    projects.create("shop", None)
    projects.set_secret("shop", "FROM_PROJECT", "p")
    env = {agent_env.ENV_DIR_VAR: str(outside), "FROM_OUT": "old", "PROVIDERS": "ours"}
    _run(tmp_path, lado_home, env, ours=["PROVIDERS", "LADO_HOME"], project="shop")
    [(_, _, given)] = started["exec"]
    assert (given["FROM_OUT"], given["FROM_PROJECT"], given["PROVIDERS"]) == ("new", "p", "ours")


def test_unknown_never_holds_it(tmp_path, lado_home, started, monkeypatch):
    provider = Waiting(logged_in_after=99, answer=base.UNKNOWN)
    monkeypatch.setitem(providers._PROVIDERS, "waits", provider)
    _run(tmp_path, lado_home)
    assert len(provider.looks) == 1 and started["exec"]


def test_what_the_cli_asks_first_holds_it_with_why(
    tmp_path, lado_home, started, monkeypatch, capsys
):
    blocker = base.Blocker(reason="Waits CLI asks a question", notes=("LADO recorded x",))
    provider = Waiting(logged_in_after=0, blocker=blocker)
    monkeypatch.setitem(providers._PROVIDERS, "waits", provider)
    _run(tmp_path, lado_home)
    assert state.block_reasons("s") == {"sup": "Waits CLI asks a question"}
    log = (lado_home / "loop.log").read_text()
    assert "sup: LADO recorded x" in log and "sup: Waits CLI asks a question" in log
    # LADO's own write is in loop.log only, not in the agent's terminal.
    shown = capsys.readouterr().out
    assert "Waits CLI asks a question" in shown and "LADO recorded" not in shown
    assert started["exec"]
