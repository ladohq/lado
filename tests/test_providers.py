import json
from pathlib import Path

import pytest

from lado import hooks, providers, runtime, state
from lado.providers import Event, kilo


def test_registry():
    assert providers.DEFAULT in providers.names()
    claude = providers.get("claude")
    assert (claude.name, claude.command) == ("claude", "claude")
    assert claude.capabilities.deliver_on_turn_end
    with pytest.raises(ValueError, match='unknown provider "nope"; known: claude, kilo'):
        providers.get("nope")


@pytest.mark.parametrize(
    ("native", "payload", "expected"),
    [
        ("SessionStart", {"source": "startup"}, Event(providers.SESSION_START)),
        ("UserPromptSubmit", {"prompt": "hi"}, Event(providers.PROMPT_SUBMIT, "hi")),
        ("Stop", {}, Event(providers.TURN_END)),
        ("SessionEnd", {}, Event(providers.SESSION_END)),
        ("Notification", {"notification_type": "permission_prompt"}, Event(providers.WAITING)),
        ("Notification", {"message": "Claude needs your permission"}, Event(providers.WAITING)),
        ("Notification", {"notification_type": "idle_prompt"}, None),
        ("PreToolUse", {}, None),
    ],
)
def test_claude_maps_native_events(native, payload, expected):
    assert providers.get("claude").parse_event(native, json.dumps(payload)) == expected


def test_claude_continues_with_queued_messages():
    out = providers.get("claude").continue_output("[from w1] done")
    assert json.loads(out) == {"decision": "block", "reason": "[from w1] done"}


def test_agents_get_the_session_provider(repo, fake_tmux):
    runtime.start_session(str(repo), "s", None)
    runtime.spawn_worker("s", "task")
    assert state.get_session("s").provider == "claude"
    assert [a.provider for a in state.list_agents("s")] == ["claude", "claude"]


class _NoTurnEndDelivery(providers.Provider):
    name = "plain"
    capabilities = providers.Capabilities(
        status_events=True, permission_event=False, deliver_on_turn_end=False
    )

    def launch_command(self, agent, session, prompt, first_message=None):
        return providers.Launch([])

    def parse_event(self, native, payload):
        return Event(native)


def test_turn_end_types_messages_when_provider_cannot_deliver_them(repo, fake_tmux):
    runtime.start_session(str(repo), "s", None)
    runtime.send_message("s", "w1", "supervisor", "done")  # supervisor is starting: queued
    out = hooks.handle(_NoTurnEndDelivery(), Event(providers.TURN_END), "s", "supervisor")
    assert out is None
    assert fake_tmux[-1] == ("send_text", "s", "supervisor", "[from w1] done")
    assert state.get_agent("s", "supervisor").status == state.BUSY


def _kilo_launch(repo, permission_mode=None, first_message=None):
    sess = state.Session("s", str(repo), permission_mode, "kilo")
    agent = state.Agent("s", "w1", runtime.WORKER, str(repo), None, None, state.STARTING, "kilo")
    launch = providers.get("kilo").launch_command(agent, sess, "the role", first_message)
    config = json.loads(open(launch.env["KILO_CONFIG"]).read())
    return launch, config


def test_kilo_launch_writes_config_and_env(repo, lado_home):
    launch, config = _kilo_launch(repo, first_message="do it")
    assert launch.argv == ["kilo", "--prompt", "do it"]
    assert launch.env["KILO_NO_DAEMON"] == "1"
    [role] = config["instructions"]
    assert open(role).read() == "the role"
    mcp = config["mcp"]["lado"]
    assert mcp["type"] == "local"
    assert mcp["command"][-1] == "mcp"
    assert mcp["environment"] == {
        "LADO_HOME": str(lado_home),
        "LADO_SESSION": "s",
        "LADO_AGENT": "w1",
    }
    [[plugin, options]] = config["plugin"]
    assert plugin == kilo.PLUGIN.as_uri()
    assert set(options["hooks"]) == set(kilo.EVENTS)
    idle = options["hooks"]["session.idle"]
    assert idle[-7:-6] == ["session.idle"]
    assert idle[-6:-2] == ["--session", "s", "--agent", "w1"]
    assert config["permission"] == {"external_directory": {f"{lado_home}/**": "allow"}}


@pytest.mark.parametrize(
    ("mode", "flags", "edit"),
    [
        (None, [], None),
        ("acceptEdits", [], None),
        ("default", [], "ask"),
        ("bypassPermissions", ["--auto"], None),
        ("plan", ["--agent", "plan"], None),
    ],
)
def test_kilo_permission_modes(repo, mode, flags, edit):
    launch, config = _kilo_launch(repo, mode)
    assert launch.argv == ["kilo", *flags]
    assert config["permission"].get("edit") == edit
    # --auto announces every permission and approves it at once: not a wait for the human.
    hooks_ = config["plugin"][0][1]["hooks"]
    assert ("permission.asked" in hooks_) == (mode != "bypassPermissions")


def test_kilo_plugin_ships_inside_the_package():
    import lado

    assert kilo.PLUGIN.is_file()
    assert kilo.PLUGIN.parent == Path(lado.__file__).parent / "providers"
    assert "export const LadoPlugin" in kilo.PLUGIN.read_text()


@pytest.mark.parametrize(
    ("native", "payload", "expected"),
    [
        ("plugin.init", {"directory": "/r"}, Event(providers.SESSION_START)),
        ("chat.message", {"sessionID": "x", "prompt": "hi"}, Event(providers.PROMPT_SUBMIT, "hi")),
        ("session.idle", {"sessionID": "x"}, Event(providers.TURN_END)),
        ("permission.asked", {"permission": "bash"}, Event(providers.WAITING)),
        ("question.asked", {}, Event(providers.WAITING)),
        ("dispose", {}, Event(providers.SESSION_END)),
        ("session.created", {}, None),
    ],
)
def test_kilo_maps_native_events(native, payload, expected):
    assert providers.get("kilo").parse_event(native, json.dumps(payload)) == expected


def test_kilo_turn_end_prints_queued_messages(repo, fake_tmux):
    runtime.start_session(str(repo), "s", None, "kilo")
    runtime.send_message("s", "w1", "supervisor", "done")  # supervisor is starting: queued
    kilo_cli = providers.get("kilo")
    out = hooks.handle(kilo_cli, kilo_cli.parse_event("session.idle", "{}"), "s", "supervisor")
    assert out == "[from w1] done"
    assert state.get_agent("s", "supervisor").status == state.BUSY


def test_provider_chosen_per_session_and_worker(repo, fake_tmux):
    runtime.start_session(str(repo), "s", None, "kilo")
    runtime.spawn_worker("s", "task")
    runtime.spawn_worker("s", "task", provider="claude")
    assert state.get_session("s").provider == "kilo"
    assert [a.provider for a in state.list_agents("s")] == ["kilo", "kilo", "claude"]
    supervisor_env, supervisor_cmd = fake_tmux[0][4:]
    assert supervisor_cmd[0] == "kilo"
    assert supervisor_env["KILO_NO_DAEMON"] == "1"
    assert supervisor_env["LADO_AGENT"] == "supervisor"
    assert fake_tmux[-1][5][0] == "claude"
    assert "KILO_CONFIG" not in fake_tmux[-1][4]


def test_unknown_provider_is_refused(repo, fake_tmux):
    with pytest.raises(runtime.LadoError, match="known: claude, kilo"):
        runtime.start_session(str(repo), "s", None, "nope")
    assert state.get_session("s") is None
    runtime.start_session(str(repo), "s", None)
    with pytest.raises(runtime.LadoError, match="known: claude, kilo"):
        runtime.spawn_worker("s", "task", provider="nope")
    assert [a.name for a in state.list_agents("s")] == ["supervisor"]
