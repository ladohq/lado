import json
from pathlib import Path

import pytest

from lado import hooks, providers, runtime, state, tmux
from lado.providers import Event, base, kilo


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
        ("SessionEnd", {"reason": "prompt_input_exit"}, Event(providers.SESSION_END)),
        ("SessionEnd", {"reason": "other"}, Event(providers.SESSION_END)),
        # /clear and /resume end the conversation, and the process goes on with another one
        ("SessionEnd", {"reason": "clear"}, Event(providers.CONVERSATION_END)),
        ("SessionEnd", {"reason": "resume"}, Event(providers.CONVERSATION_END)),
        ("SessionStart", {"source": "clear"}, Event(providers.CONVERSATION_START)),
        ("SessionStart", {"source": "resume"}, Event(providers.CONVERSATION_START)),
        ("SessionStart", {"source": "compact"}, Event(providers.SESSION_START)),
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
        status_events=True, permission_event=False, deliver_on_turn_end=False, skills=False
    )

    def launch_command(self, agent, session, spec, first_message=None):
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
    agent = state.Agent(
        "s", "w1", "worker", str(repo), None, None, state.STARTING, "kilo", instance="i1"
    )
    spec = providers.AgentSpec("the role", mcp={"lado": base.mcp_server(agent)})
    launch = providers.get("kilo").launch_command(agent, sess, spec, first_message)
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
        "LADO_TMUX_SOCKET": tmux.socket(),
        "LADO_INSTANCE": "i1",
    }
    [[plugin, options]] = config["plugin"]
    assert plugin == kilo.PLUGIN.as_uri()
    assert set(options["hooks"]) == set(kilo.EVENTS)
    idle = options["hooks"]["session.idle"]
    assert idle[-7:-6] == ["session.idle"]
    assert idle[-6:-2] == ["--session", "s", "--agent", "w1"]
    assert config["permission"] == {"external_directory": {f"{lado_home}/**": "allow"}}


def test_kilo_agent_does_not_update_itself(repo):
    launch, config = _kilo_launch(repo)
    assert launch.env["KILO_DISABLE_AUTOUPDATE"] == "1"
    assert config["autoupdate"] is False


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


def _spec_with_kit_parts(agent, skill_dir):
    return providers.AgentSpec(
        "the role",
        skills={"notes": skill_dir},
        mcp={
            "lado": base.mcp_server(agent),
            "db": providers.McpServer(["db-server", "--port", "1"], {"T": "x"}),
        },
    )


@pytest.fixture
def skill_dir(tmp_path):
    path = tmp_path / "kit" / "skills" / "notes"
    (path / "scripts").mkdir(parents=True)
    (path / "SKILL.md").write_text("---\nname: notes\ndescription: d\n---\n")
    return path


def test_claude_gets_skills_and_kit_mcp(repo, skill_dir):
    sess = state.Session("s", str(repo), None)
    agent = state.Agent("s", "w1", "worker", str(repo), None, None, state.STARTING)
    claude = providers.get("claude")
    cmd = claude.launch_command(agent, sess, _spec_with_kit_parts(agent, skill_dir)).argv
    mcp = json.loads(open(cmd[cmd.index("--mcp-config") + 1]).read())["mcpServers"]
    assert mcp["db"] == {"command": "db-server", "args": ["--port", "1"], "env": {"T": "x"}}
    assert mcp["lado"]["args"][-1] == "mcp"
    # LADO's tools are in the prompt from the start, not deferred behind tool search.
    assert mcp["lado"]["alwaysLoad"] is True
    # The server says which launch it serves; the session-start hook waits for it.
    assert mcp["lado"]["env"]["LADO_INSTANCE"] == agent.instance
    assert claude.capabilities.hold_first_turn
    added = Path(cmd[cmd.index("--add-dir") + 1])
    link = added / ".claude" / "skills" / "notes"
    assert link.is_symlink() and link.resolve() == skill_dir.resolve()
    assert (link / "scripts").is_dir()
    # Without skills, no --add-dir and no stale links.
    cmd = claude.launch_command(agent, sess, providers.AgentSpec("the role")).argv
    assert "--add-dir" not in cmd and not added.exists()
    assert cmd[cmd.index("--append-system-prompt") + 1] == "the role"


def test_claude_agent_cannot_use_built_in_agent_messaging(repo):
    sess = state.Session("s", str(repo), "bypassPermissions")
    agent = state.Agent("s", "w1", "worker", str(repo), None, None, state.STARTING)
    spec = providers.AgentSpec("the role", mcp={"lado": base.mcp_server(agent)})
    cmd = providers.get("claude").launch_command(agent, sess, spec).argv
    settings = json.loads(open(cmd[cmd.index("--settings") + 1]).read())
    assert settings["permissions"]["deny"] == ["SendMessage", "ListAgents"]


def test_kilo_gets_skills_and_kit_mcp(repo, skill_dir):
    sess = state.Session("s", str(repo), None, "kilo")
    agent = state.Agent("s", "w1", "worker", str(repo), None, None, state.STARTING, "kilo")
    spec = _spec_with_kit_parts(agent, skill_dir)
    launch = providers.get("kilo").launch_command(agent, sess, spec)
    config = json.loads(open(launch.env["KILO_CONFIG"]).read())
    assert config["mcp"]["db"] == {
        "type": "local",
        "command": ["db-server", "--port", "1"],
        "environment": {"T": "x"},
    }
    [skills] = config["skills"]["paths"]
    assert Path(skills, "notes").resolve() == skill_dir.resolve()
    # The links are under LADO_HOME, which the agent may read.
    assert Path(skills).is_relative_to(state.home())
