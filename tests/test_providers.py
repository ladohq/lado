import importlib
import json
from pathlib import Path

import agent_helpers
import pytest

from lado import hooks, providers, runtime, state, tmux
from lado.providers import Event, base, opencode_family

# The OpenCode family (lado.providers.opencode_family) and the variable its config goes in.
FAMILY = {"kilo": "KILO_CONFIG_CONTENT", "opencode": "OPENCODE_CONFIG_CONTENT"}


def test_registry():
    assert not hasattr(providers, "DEFAULT")  # no provider is privileged
    assert providers.names() == ["claude", "kilo", "opencode"]
    claude = providers.get("claude")
    assert (claude.name, claude.command) == ("claude", "claude")
    assert claude.capabilities.deliver_on_turn_end
    with pytest.raises(ValueError, match='unknown provider "nope"; known: claude, kilo, opencode'):
        providers.get("nope")


@pytest.mark.parametrize(
    ("native", "payload", "expected"),
    [
        ("SessionStart", {"source": "startup"}, Event(providers.SESSION_START)),
        ("UserPromptSubmit", {"prompt": "hi"}, Event(providers.PROMPT_SUBMIT, "hi")),
        ("Stop", {}, Event(providers.TURN_END)),
        ("Stop", {"stop_hook_active": False}, Event(providers.TURN_END)),
        # The turn went on from what the previous Stop hook printed.
        ("Stop", {"stop_hook_active": True}, Event(providers.TURN_END, continued=True)),
        ("SessionEnd", {}, Event(providers.SESSION_END)),
        ("SessionEnd", {"reason": "prompt_input_exit"}, Event(providers.SESSION_END)),
        ("SessionEnd", {"reason": "other"}, Event(providers.SESSION_END)),
        # /clear and /resume end the conversation, and the process goes on with another one
        ("SessionEnd", {"reason": "clear"}, Event(providers.CONVERSATION_END)),
        ("SessionEnd", {"reason": "resume"}, Event(providers.CONVERSATION_END)),
        ("SessionStart", {"source": "clear"}, Event(providers.CONVERSATION_START)),
        ("SessionStart", {"source": "resume"}, Event(providers.CONVERSATION_START)),
        ("SessionStart", {"source": "compact"}, Event(providers.SESSION_START)),
        # The keyed hooks below say it, sooner: a notification about a dialog is none.
        ("Notification", {"notification_type": "permission_prompt"}, None),
        ("Notification", {"message": "Claude needs your permission"}, None),
        ("Notification", {"notification_type": "elicitation_dialog"}, None),
        ("Notification", {"notification_type": "idle_prompt"}, None),
        ("PreToolUse", {"tool_name": "AskUserQuestion", "tool_use_id": "t1"}, None),
    ],
)
def test_claude_maps_native_events(native, payload, expected):
    assert providers.get("claude").parse_event(native, json.dumps(payload)) == expected


@pytest.mark.parametrize(
    ("payload", "error"),
    [
        ({"error": "server_error"}, "server_error"),
        (
            {"error": "rate_limit", "error_details": "429 Too Many Requests\nretry later"},
            "rate_limit: 429 Too Many Requests",
        ),
        ({"error": "unknown", "error_details": "x" * 300}, "unknown: " + "x" * 150 + "…"),
        ({}, "unknown"),
    ],
)
def test_claude_stop_failure_is_a_turn_end_on_an_error_whose_output_goes_nowhere(payload, error):
    """Claude Code runs StopFailure instead of Stop when an API error ended the turn, and
    ignores what the hook prints (2.1.291, read in its binary)."""
    event = providers.get("claude").parse_event("StopFailure", json.dumps(payload))
    assert event == Event(providers.TURN_END, error=error, output_ignored=True)


def test_claude_agents_report_a_failed_turn(repo, fake_tmux):
    runtime.start_session(str(repo), "s", None, provider="claude")
    cmd = fake_tmux[0][-1]
    settings = json.loads(open(cmd[cmd.index("--settings") + 1]).read())
    assert "StopFailure" in settings["hooks"]


# What Claude Code 2.1.289 gives its hooks (checked by hand, trimmed): PermissionRequest comes
# before a dialog, for a question too, and has no tool_use_id; a question's answer adds to
# its input; an elicitation and its result name only the MCP server.
BASH = {"tool_name": "Bash", "tool_input": {"command": "touch b.txt", "description": "Create b"}}
QUESTIONS = [{"question": "Red or blue?", "header": "Color", "options": [], "multiSelect": False}]
ASK = {"tool_name": "AskUserQuestion", "tool_input": {"questions": QUESTIONS}}
ANSWERED = {**ASK, "tool_input": {"questions": QUESTIONS, "answers": {"Red or blue?": "Blue"}}}


def _claude_event(native, payload):
    return providers.get("claude").parse_event(native, json.dumps(payload))


def _paired(asked, answered):
    waiting, resumed = _claude_event(*asked), _claude_event(*answered)
    assert (waiting.kind, resumed.kind) == (providers.WAITING, providers.RESUMED)
    assert waiting.key
    return waiting.key == resumed.key


def test_claude_pairs_a_dialog_with_its_answer():
    used = {**BASH, "tool_use_id": "toolu_1", "tool_response": {"stdout": ""}}
    assert _paired(("PermissionRequest", BASH), ("PostToolUse", used))
    assert _paired(("PermissionRequest", BASH), ("PostToolUseFailure", {**used, "error": "x"}))
    assert _paired(("PermissionRequest", ASK), ("PostToolUse", {**ANSWERED, "tool_use_id": "t"}))
    elicitation = {"mcp_server_name": "probe", "message": "Which color?", "mode": "form"}
    result = {"mcp_server_name": "probe", "mode": "form", "action": "accept"}
    assert _paired(("Elicitation", elicitation), ("ElicitationResult", result))


def test_claude_tells_another_tool_call_from_the_one_asked_about():
    # A subagent's tool, or the next tool after a refusal, while the dialog is open.
    other = {"tool_name": "Bash", "tool_input": {"command": "echo skipped"}, "agent_id": "a1"}
    assert not _paired(("PermissionRequest", BASH), ("PostToolUse", other))
    read = {"tool_name": "Read", "tool_input": BASH["tool_input"]}
    assert not _paired(("PermissionRequest", BASH), ("PostToolUse", read))
    assert not _paired(("PermissionRequest", ASK), ("PostToolUse", BASH))
    elicitation = {"mcp_server_name": "probe"}
    assert not _paired(
        ("Elicitation", elicitation), ("ElicitationResult", {"mcp_server_name": "x"})
    )


def test_claude_hooks_leave_the_human_s_answer_to_the_human(repo, fake_tmux):
    """The hooks that see a dialog print nothing: any output could decide it."""
    runtime.start_session(str(repo), "s", None, provider="claude")
    claude = providers.get("claude")
    for native, payload in [
        ("PermissionRequest", BASH),
        ("Elicitation", {"mcp_server_name": "probe"}),
        ("ElicitationResult", {"mcp_server_name": "probe", "action": "accept"}),
        ("PostToolUse", BASH),
    ]:
        neutral = claude.parse_event(native, json.dumps(payload))
        assert hooks.handle(claude, neutral, "s", "supervisor") is None


def _claude_settings(repo, mode=None):
    sess = state.Session("s", str(repo), mode, provider="claude")
    agent = state.Agent(
        "s", "w1", "worker", str(repo), None, None, state.STARTING, provider="claude"
    )
    spec = providers.AgentSpec("the role", mcp={"lado": base.mcp_server(agent)})
    cmd = providers.get("claude").launch_command(agent, sess, spec).argv
    return json.loads(open(cmd[cmd.index("--settings") + 1]).read())["hooks"]


@pytest.mark.parametrize("mode", [None, *providers.get("claude").permission_modes])
def test_claude_reports_dialogs_at_once_and_their_answers_without_holding_tools(repo, mode):
    hooks_ = _claude_settings(repo, mode)
    # A dialog is reported before it shows, in every mode: Claude Code asks this hook only
    # when it shows one (also for a question with bypassPermissions, never for a refusal
    # with dontAsk).
    for native in ("PermissionRequest", "Elicitation"):
        [asked] = hooks_[native]
        assert "matcher" not in asked and "async" not in asked["hooks"][0]
    # Every tool call ends with one of these: they must not hold up the next.
    for native in ("PostToolUse", "PostToolUseFailure", "ElicitationResult"):
        [answered] = hooks_[native]
        assert "matcher" not in answered
        assert answered["hooks"][0]["async"] is True
        assert answered["hooks"][0]["command"].split()[-7] == native
    assert "Notification" not in hooks_ and "PreToolUse" not in hooks_


def test_providers_that_report_a_wait_report_its_end():
    """A wait no event ends keeps the agent waiting until its turn ends."""
    for name in providers.names():
        provider = providers.get(name)
        # Each provider's module, or the module of the base it shares, maps its native
        # events in EVENTS.
        modules = [importlib.import_module(c.__module__) for c in type(provider).__mro__]
        events = next(m.EVENTS for m in modules if hasattr(m, "EVENTS"))
        mapped = set(events.values())
        if providers.WAITING in mapped:
            assert providers.RESUMED in mapped, name


def test_claude_continues_with_queued_messages():
    out = providers.get("claude").continue_output("[from w1] done")
    assert json.loads(out) == {"decision": "block", "reason": "[from w1] done"}


def test_agents_get_the_session_provider(repo, fake_tmux):
    runtime.start_session(str(repo), "s", None, provider="claude")
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
    runtime.start_session(str(repo), "s", None, provider="claude")
    # Busy, so the message waits for the turn's end. Not starting: its session start would
    # type the queue in itself, as any switch to idle does.
    state.set_status("s", "supervisor", state.BUSY)
    assert runtime.send_message("s", "w1", "supervisor", "done").startswith("queued")
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
    config = json.loads(launch.env["KILO_CONFIG_CONTENT"])
    return launch, config


def test_kilo_launch_writes_config_and_env(repo, lado_home):
    launch, config = _kilo_launch(repo, first_message="do it")
    assert launch.argv == ["kilo", "--prompt", "do it"]
    assert launch.env["KILO_NO_DAEMON"] == "1"
    # The config goes in as text: a KILO_CONFIG file loses to the repo's own kilo.json, the
    # text wins (Kilo 7.8.3). The same text is in the agent's config folder to look at.
    assert "KILO_CONFIG" not in launch.env
    file = lado_home / "agents" / "s" / "w1" / "kilo.json"
    assert file.read_text() == launch.env["KILO_CONFIG_CONTENT"]
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
    assert plugin == opencode_family.PLUGIN.as_uri()
    assert set(options["hooks"]) == set(opencode_family.EVENTS)
    idle = options["hooks"]["session.idle"]
    assert idle[-7:-6] == ["session.idle"]
    assert idle[-6:-2] == ["--session", "s", "--agent", "w1"]
    assert config["permission"] == {"external_directory": {f"{lado_home}/**": "allow"}}


def test_kilo_agent_does_not_update_itself(repo):
    launch, config = _kilo_launch(repo)
    assert launch.env["KILO_DISABLE_AUTOUPDATE"] == "1"
    assert config["autoupdate"] is False


def test_kilo_agent_takes_no_snapshots(repo):
    # On a slow repo Kilo's snapshot setup asks the human whether to go on; the agent waits.
    _, config = _kilo_launch(repo)
    assert config["snapshot"] is False


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
    for event in ("permission.asked", "permission.replied"):
        assert (event in hooks_) == (mode != "bypassPermissions")
    for event in ("question.asked", "question.replied", "question.rejected"):
        assert event in hooks_  # --auto does not answer questions


def test_kilo_plan_agent_may_use_lado_tools(repo):
    # Kilo's plan agent denies every tool it does not list, LADO's MCP tools too (Kilo 7.8.1);
    # an agent that cannot call send_message or flow_advance cannot report.
    _, config = _kilo_launch(repo, "plan")
    assert config["agent"] == {"plan": {"permission": {"lado_*": "allow"}}}
    _, config = _kilo_launch(repo, "default")
    assert "agent" not in config


def test_providers_declare_their_permission_modes():
    assert providers.get("kilo").permission_modes == (
        "default",
        "acceptEdits",
        "bypassPermissions",
        "plan",
    )
    # What Claude Code 2.1.287 accepts for --permission-mode ("default" without listing it).
    assert set(providers.get("claude").permission_modes) == {
        "default",
        "acceptEdits",
        "auto",
        "bypassPermissions",
        "manual",
        "dontAsk",
        "plan",
    }


def test_permission_mode_check_names_mode_provider_and_supported_modes():
    kilo_cli = providers.get("kilo")
    kilo_cli.check_permission_mode(None)
    kilo_cli.check_permission_mode("plan")
    with pytest.raises(ValueError) as exc:
        kilo_cli.check_permission_mode("dontAsk")
    assert str(exc.value) == (
        'permission mode "dontAsk" is not supported by Kilo CLI (kilo); '
        "supported: default, acceptEdits, bypassPermissions, plan"
    )


def test_kilo_turn_end_prints_queued_messages(repo, fake_tmux):
    runtime.start_session(str(repo), "s", None, "kilo")
    runtime.send_message("s", "w1", "supervisor", "done")  # supervisor is starting: queued
    kilo_cli = providers.get("kilo")
    out = hooks.handle(kilo_cli, kilo_cli.parse_event("session.idle", "{}"), "s", "supervisor")
    assert out == "[from w1] done"
    assert state.get_agent("s", "supervisor").status == state.BUSY


def _opencode_launch(repo, permission_mode=None, first_message=None):
    sess = state.Session("s", str(repo), permission_mode, "opencode")
    agent = state.Agent(
        "s", "w1", "worker", str(repo), None, None, state.STARTING, "opencode", instance="i1"
    )
    spec = providers.AgentSpec("the role", mcp={"lado": base.mcp_server(agent)})
    launch = providers.get("opencode").launch_command(agent, sess, spec, first_message)
    config = json.loads(launch.env["OPENCODE_CONFIG_CONTENT"])
    return launch, config


def test_opencode_launch_writes_config_and_env(repo, lado_home):
    launch, config = _opencode_launch(repo, first_message="do it")
    assert launch.argv == ["opencode", "--prompt", "do it"]
    # The config goes in as text, after the repo's own opencode.json (OpenCode 1.18.34); the
    # same text is in the agent's config folder to look at.
    assert launch.env == {
        "OPENCODE_CONFIG_CONTENT": launch.env["OPENCODE_CONFIG_CONTENT"],
        "OPENCODE_DISABLE_AUTOUPDATE": "1",
    }
    file = lado_home / "agents" / "s" / "w1" / "opencode.json"
    assert file.read_text() == launch.env["OPENCODE_CONFIG_CONTENT"]
    [role] = config["instructions"]
    assert open(role).read() == "the role"
    mcp = config["mcp"]["lado"]
    assert (mcp["type"], mcp["command"][-1]) == ("local", "mcp")
    assert mcp["environment"]["LADO_INSTANCE"] == "i1"
    [[plugin, options]] = config["plugin"]
    assert plugin == opencode_family.PLUGIN.as_uri()
    assert set(options["hooks"]) == set(opencode_family.EVENTS)
    idle = options["hooks"]["session.idle"]
    assert idle[-7:-6] == ["session.idle"]
    assert idle[-6:-2] == ["--session", "s", "--agent", "w1"]
    assert config["skills"] == {"paths": [str(lado_home / "agents" / "s" / "w1" / "skills")]}
    assert config["permission"]["external_directory"] == {f"{lado_home}/**": "allow"}
    assert (config["autoupdate"], config["snapshot"]) == (False, False)


# What each mode asks the human, as Claude Code's modes of the same name do. OpenCode's
# default agent asks only before external_directory and doom_loop (OpenCode 1.18.34).
@pytest.mark.parametrize(
    ("mode", "flags", "permission"),
    [
        (None, [], {}),  # OpenCode's own defaults, as with Kilo
        ("default", [], {"edit": "ask", "bash": "ask"}),
        ("acceptEdits", [], {"bash": "ask"}),
        ("bypassPermissions", ["--auto"], {}),
        ("plan", ["--agent", "plan"], {}),
    ],
)
def test_opencode_permission_modes(repo, lado_home, mode, flags, permission):
    launch, config = _opencode_launch(repo, mode)
    assert launch.argv == ["opencode", *flags]
    readable = {"external_directory": {f"{lado_home}/**": "allow"}}
    assert config["permission"] == {**readable, **permission}
    # OpenCode's plan agent runs bash without asking (1.18.34); plan changes nothing unasked.
    assert config.get("agent") == (
        {"plan": {"permission": {"lado_*": "allow", "bash": "ask"}}} if mode == "plan" else None
    )
    hooks_ = config["plugin"][0][1]["hooks"]
    for event in ("permission.asked", "permission.replied"):
        assert (event in hooks_) == (mode != "bypassPermissions")
    for event in ("question.asked", "question.replied", "question.rejected"):
        assert event in hooks_  # --auto does not answer questions


def test_opencode_declares_its_permission_modes_and_version():
    opencode_cli = providers.get("opencode")
    assert (opencode_cli.title, opencode_cli.command) == ("OpenCode", "opencode")
    assert opencode_cli.permission_modes == ("default", "acceptEdits", "bypassPermissions", "plan")
    assert opencode_cli.tested_version == "1.18"
    assert opencode_cli.install_hint == "install it: `npm install -g opencode-ai`"


@pytest.mark.parametrize("provider", list(FAMILY))
@pytest.mark.parametrize(
    ("native", "payload", "expected"),
    [
        ("plugin.init", {"directory": "/r"}, Event(providers.SESSION_START)),
        ("chat.message", {"sessionID": "x", "prompt": "hi"}, Event(providers.PROMPT_SUBMIT, "hi")),
        ("session.idle", {"sessionID": "x"}, Event(providers.TURN_END)),
        ("permission.asked", {"id": "per_1"}, Event(providers.WAITING, key="per_1")),
        ("permission.replied", {"id": "per_1"}, Event(providers.RESUMED, key="per_1")),
        ("question.asked", {"id": "que_1"}, Event(providers.WAITING, key="que_1")),
        ("question.replied", {"id": "que_1"}, Event(providers.RESUMED, key="que_1")),
        ("question.rejected", {"id": "que_1"}, Event(providers.RESUMED, key="que_1")),
        ("dispose", {}, Event(providers.SESSION_END)),
        ("session.created", {}, None),
        # The plugin could not hand the turn-end hook's output on.
        (
            "plugin.error",
            {"sessionID": "x", "error": {"name": "promptAsync", "message": "fetch failed"}},
            Event(providers.HOOK_ERROR, error="promptAsync: fetch failed"),
        ),
    ],
)
def test_opencode_family_maps_native_events(provider, native, payload, expected):
    assert providers.get(provider).parse_event(native, json.dumps(payload)) == expected


@pytest.mark.parametrize("provider", list(FAMILY))
@pytest.mark.parametrize(
    ("error", "expected"),
    [
        ({"name": "APIError", "message": "Overloaded\nretry"}, "APIError: Overloaded"),
        ({"name": "ProviderAuthError"}, "ProviderAuthError"),
        # The human pressed Esc: a turn end as any other.
        ({"name": "MessageAbortedError"}, ""),
    ],
)
def test_opencode_family_turn_end_carries_the_error_the_plugin_saw(provider, error, expected):
    payload = json.dumps({"sessionID": "x", "error": error})
    assert providers.get(provider).parse_event("session.idle", payload) == Event(
        providers.TURN_END, error=expected
    )


def test_opencode_family_shares_one_plugin_inside_the_package():
    import lado

    assert opencode_family.PLUGIN.is_file()
    assert opencode_family.PLUGIN.name == "opencode_plugin.js"
    assert opencode_family.PLUGIN.parent == Path(lado.__file__).parent / "providers"
    assert "export const LadoPlugin" in opencode_family.PLUGIN.read_text()
    for name in FAMILY:
        assert providers.get(name).plugin == opencode_family.PLUGIN
        assert isinstance(providers.get(name), opencode_family.OpenCodeFamily)


def test_opencode_turn_end_prints_queued_messages(repo, fake_tmux):
    runtime.start_session(str(repo), "s", None, "opencode")
    runtime.send_message("s", "w1", "supervisor", "done")  # supervisor is starting: queued
    cli = providers.get("opencode")
    out = hooks.handle(cli, cli.parse_event("session.idle", "{}"), "s", "supervisor")
    assert out == "[from w1] done"
    assert state.get_agent("s", "supervisor").status == state.BUSY


@pytest.mark.parametrize("provider", list(FAMILY))
def test_opencode_family_confirms_the_turn_end_output_by_the_prompt_it_makes(
    repo, fake_tmux, provider
):
    runtime.start_session(str(repo), "s", None, provider)
    runtime.send_message("s", "w1", "supervisor", "done")  # supervisor is starting: queued
    cli = providers.get(provider)
    text = hooks.handle(cli, cli.parse_event("session.idle", "{}"), "s", "supervisor")
    [done] = state.list_messages("s")
    assert (done.state, done.channel) == (state.SENT, state.HOOK_OUTPUT)
    # The plugin's promptAsync makes it the next user message: "chat.message" runs for it.
    prompt = json.dumps({"sessionID": "ses_1", "prompt": text})
    hooks.handle(cli, cli.parse_event("chat.message", prompt), "s", "supervisor")
    assert state.list_messages("s")[0].state == state.DELIVERED


def test_output_the_plugin_could_not_hand_on_is_logged_and_typed_in_after_the_delay(
    repo, fake_tmux
):
    runtime.start_session(str(repo), "s", None, "opencode")
    runtime.send_message("s", "w1", "supervisor", "done")  # supervisor is starting: queued
    cli = providers.get("opencode")
    assert hooks.handle(cli, cli.parse_event("session.idle", "{}"), "s", "supervisor")
    payload = {"sessionID": "ses_1", "error": {"name": "promptAsync", "message": "fetch failed"}}
    hooks.handle(cli, cli.parse_event("plugin.error", json.dumps(payload)), "s", "supervisor")
    log = (state.home() / "hooks.log").read_text()
    assert log == "s/supervisor: promptAsync: fetch failed\n"
    # The CLI never took the output: as for any hand-over no hook followed, sweep types it.
    [done] = state.list_messages("s")
    runtime.sweep("s", now=done.sent_at + runtime.RETRY_DELAYS[0])
    assert fake_tmux[-1] == ("send_text", "s", "supervisor", "[from w1] done")


def test_turn_end_hands_over_queued_messages_without_an_idle_moment(repo, fake_tmux, monkeypatch):
    """No one sees the messages delivered and the agent idle, as if it were done with them
    before it got them."""
    runtime.start_session(str(repo), "s", None, provider="claude")
    state.set_status("s", "supervisor", state.BUSY)
    runtime.send_message("s", "w1", "supervisor", "done")  # busy: queued
    status_once_delivered = []
    take_pending = state.take_pending

    def spy(*args, **kwargs):
        taken = take_pending(*args, **kwargs)
        if taken:
            status_once_delivered.append(state.get_agent("s", "supervisor").status)
        return taken

    monkeypatch.setattr(state, "take_pending", spy)
    out = hooks.handle(providers.get("claude"), Event(providers.TURN_END), "s", "supervisor")
    assert json.loads(out)["reason"] == "[from w1] done"
    assert status_once_delivered == [state.BUSY]


def test_provider_chosen_per_session_and_worker(repo, fake_tmux):
    runtime.start_session(str(repo), "s", None, "kilo")
    runtime.spawn_worker("s", "task")
    runtime.spawn_worker("s", "task", provider="claude")
    assert state.get_session("s").provider == "kilo"
    assert [a.provider for a in state.list_agents("s")] == ["kilo", "kilo", "claude"]
    supervisor_env, supervisor_cmd = agent_helpers.launched(fake_tmux[0])
    assert supervisor_cmd[0] == "kilo"
    assert supervisor_env["KILO_NO_DAEMON"] == "1"
    assert supervisor_env["LADO_AGENT"] == "supervisor"
    worker_env, worker_cmd = agent_helpers.launched(fake_tmux[-1])
    assert worker_cmd[0] == "claude"
    assert "KILO_CONFIG" not in worker_env


def test_unknown_provider_is_refused(repo, fake_tmux):
    with pytest.raises(runtime.LadoError, match="known: claude, kilo, opencode"):
        runtime.start_session(str(repo), "s", None, "nope")
    assert state.get_session("s") is None
    runtime.start_session(str(repo), "s", None, provider="claude")
    with pytest.raises(runtime.LadoError, match="known: claude, kilo, opencode"):
        runtime.spawn_worker("s", "task", provider="nope")
    assert [a.name for a in state.list_agents("s")] == ["supervisor"]


def test_permission_mode_the_provider_cannot_honour_is_refused(repo, fake_tmux):
    with pytest.raises(runtime.LadoError, match='"dontAsk" is not supported by Kilo CLI'):
        runtime.start_session(str(repo), "s", "dontAsk", "kilo")
    assert state.get_session("s") is None
    assert fake_tmux == []
    runtime.start_session(str(repo), "s", "dontAsk", provider="claude")
    with pytest.raises(runtime.LadoError, match="supported: default, acceptEdits"):
        runtime.spawn_worker("s", "task", provider="kilo")
    assert [a.name for a in state.list_agents("s")] == ["supervisor"]
    assert len(fake_tmux) == 1


def test_resume_with_a_provider_that_cannot_honour_the_stored_mode_is_refused(repo, fake_tmux):
    runtime.start_session(str(repo), "s", "dontAsk", provider="claude")
    runtime.stop_session("s")
    with pytest.raises(runtime.LadoError, match='"dontAsk" is not supported by Kilo CLI'):
        runtime.start_session(str(repo), "s", None, "kilo")
    sess = state.get_session("s")
    assert (sess.provider, sess.permission_mode, bool(sess.stopped_at)) == (
        "claude",
        "dontAsk",
        True,
    )


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
    sess = state.Session("s", str(repo), None, provider="claude")
    agent = state.Agent(
        "s", "w1", "worker", str(repo), None, None, state.STARTING, provider="claude"
    )
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
    sess = state.Session("s", str(repo), "bypassPermissions", provider="claude")
    agent = state.Agent(
        "s", "w1", "worker", str(repo), None, None, state.STARTING, provider="claude"
    )
    spec = providers.AgentSpec("the role", mcp={"lado": base.mcp_server(agent)})
    cmd = providers.get("claude").launch_command(agent, sess, spec).argv
    settings = json.loads(open(cmd[cmd.index("--settings") + 1]).read())
    assert settings["permissions"]["deny"] == ["SendMessage", "ListAgents"]


@pytest.mark.parametrize("provider", list(FAMILY))
def test_opencode_family_gets_skills_and_kit_mcp(repo, skill_dir, provider):
    sess = state.Session("s", str(repo), None, provider)
    agent = state.Agent("s", "w1", "worker", str(repo), None, None, state.STARTING, provider)
    spec = _spec_with_kit_parts(agent, skill_dir)
    launch = providers.get(provider).launch_command(agent, sess, spec)
    config = json.loads(launch.env[FAMILY[provider]])
    assert config["mcp"]["db"] == {
        "type": "local",
        "command": ["db-server", "--port", "1"],
        "environment": {"T": "x"},
    }
    [skills] = config["skills"]["paths"]
    assert Path(skills, "notes").resolve() == skill_dir.resolve()
    # The links are under LADO_HOME, which the agent may read.
    assert Path(skills).is_relative_to(state.home())


def test_claude_may_read_the_folders_of_spec_read(repo, skill_dir, tmp_path):
    sess = state.Session("s", str(repo), None, provider="claude")
    agent = state.Agent(
        "s", "w1", "worker", str(repo), None, None, state.STARTING, provider="claude"
    )
    read = [tmp_path / "files", tmp_path / "more"]
    spec = providers.AgentSpec("the role", skills={"notes": skill_dir}, read=read)
    cmd = providers.get("claude").launch_command(agent, sess, spec).argv
    added = [cmd[i + 1] for i, arg in enumerate(cmd) if arg == "--add-dir"]
    assert added[1:] == [str(p) for p in read]
    assert added[0] == str(base.config_dir(agent) / "skills")


@pytest.mark.parametrize("provider", list(FAMILY))
def test_opencode_family_may_read_the_folders_of_spec_read_and_takes_no_skills_from_them(
    repo, skill_dir, tmp_path, lado_home, provider
):
    sess = state.Session("s", str(repo), None, provider)
    agent = state.Agent("s", "w1", "worker", str(repo), None, None, state.STARTING, provider)
    read = [tmp_path / "files"]
    spec = providers.AgentSpec("the role", skills={"notes": skill_dir}, read=read)
    launch = providers.get(provider).launch_command(agent, sess, spec)
    config = json.loads(launch.env[FAMILY[provider]])
    assert config["permission"]["external_directory"] == {
        f"{lado_home}/**": "allow",
        f"{tmp_path / 'files'}/**": "allow",
    }
    assert config["skills"]["paths"] == [str(base.config_dir(agent) / "skills")]
