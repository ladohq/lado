"""Codex CLI as a LADO provider (lado.providers.codex)."""

import datetime
import json
import math
import os
import subprocess
import sys
from pathlib import Path

import agent_helpers
import pytest

from lado import hooks, providers, runtime, state
from lado.providers import Event, base, codex

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

ROLE = "PROMPT-MARK the role"


def _agent(cwd, name="w1"):
    return state.Agent(
        "s", name, "worker", str(cwd), None, None, state.STARTING, "codex", instance="i1"
    )


def _launch(cwd, mode=None, spec=None, notice=None, environ=None):
    """Launch a Codex agent in `cwd`; its Launch and the config.toml LADO wrote for it."""
    agent = _agent(cwd)
    if spec is None:
        environ = dict(os.environ) if environ is None else environ
        spec = providers.AgentSpec(ROLE, mcp={"lado": base.mcp_server(agent)}, environ=environ)
    sess = state.Session("s", str(cwd), mode, "codex")
    launch = providers.get("codex").launch_command(agent, sess, spec, notice=notice)
    return launch, _config(launch)


def _config(launch):
    return tomllib.loads((Path(launch.env["CODEX_HOME"]) / "config.toml").read_text())


def _user_config(codex_home, text):
    codex_home.mkdir(parents=True, exist_ok=True)
    (codex_home / "config.toml").write_text(text)


def _trust(codex_home, *folders, level="trusted"):
    entries = "".join(f'[projects."{f}"]\ntrust_level = "{level}"\n' for f in folders)
    _user_config(codex_home, entries)


def _blocker(launch, cwd):
    return providers.get("codex").first_hook_blocker(str(cwd), {**launch.env})


def _worktree(repo, name="w1"):
    worktree = repo / ".lado" / "worktrees" / "s" / name
    subprocess.run(
        ["git", "-C", str(repo), "worktree", "add", "-q", "-b", f"lado/s/{name}", str(worktree)],
        check=True,
    )
    return worktree


def test_codex_is_registered():
    cli = providers.get("codex")
    assert (cli.name, cli.title, cli.command) == ("codex", "Codex CLI", "codex")
    assert cli.tested_version == codex.TESTED_VERSION == "0.162"
    assert "npm install -g @openai/codex" in cli.install_hint


def test_each_agent_gets_its_own_codex_home(repo, lado_home):
    launch, config = _launch(repo)
    home = lado_home / "agents" / "s" / "w1"
    assert launch.env == {"CODEX_HOME": str(home)}
    # No background app server: it would outlive the agent, run its hooks with its own
    # environment and copy the CLI into the home.
    assert launch.argv == ["codex", "--no-daemon"]
    assert config["developer_instructions"] == ROLE
    assert launch.warnings == []


def test_the_role_is_never_on_the_command_line(repo):
    launch, _ = _launch(repo, notice="[from lado] your task (#7, 3 lines: call read_messages)")
    assert not [a for a in launch.argv if "MARK" in a]
    # The first line goes last, as the prompt Codex submits first.
    assert launch.argv[-1] == "[from lado] your task (#7, 3 lines: call read_messages)"


def test_the_config_is_only_the_owners_also_over_an_older_file(repo, lado_home):
    old = lado_home / "agents" / "s" / "w1" / "config.toml"
    old.parent.mkdir(parents=True)
    old.write_text("")
    old.chmod(0o644)
    _launch(repo)
    assert old.stat().st_mode & 0o777 == 0o600


def test_the_agent_does_not_update_itself_nor_start_its_own_agents(repo):
    """Codex has two versions of its own subagents: `features.multi_agent` switches the first
    off, but newer models turn the second on through their metadata (the `collaboration`
    tools, `wait_agent` among them), over `features.multi_agent_v2`; only `agents.enabled`
    wins over the model, and `multi_agent_v2` is checked before it (LAD-167)."""
    _, config = _launch(repo)
    assert config["check_for_update_on_startup"] is False
    assert config["features"]["multi_agent"] is False
    assert config["features"]["multi_agent_v2"] is False
    assert config["agents"] == {"enabled": False}
    assert config["analytics"] == {"enabled": False}
    assert config["feedback"] == {"enabled": False}


def test_the_agent_keeps_no_snapshot_of_its_environment(repo):
    """Codex's shell snapshot writes the agent's whole environment into its home, a kit's
    MCP secrets too: no value of those may be on disk (lado.mcp_exec)."""
    _, config = _launch(repo)
    assert config["features"]["shell_snapshot"] is False


def test_the_agent_has_no_goal_tools(repo):
    """Codex's goals (`update_goal`, on by default) make local models loop; LADO's agents
    get their task as messages."""
    _, config = _launch(repo)
    assert config["features"]["goals"] is False


def test_a_read_only_agent_has_no_codex_worktrees_and_is_warned_about_apply_patch(repo):
    """Codex's own worktrees (create_worktree) change the repository. Its apply_patch tool
    comes with a model's metadata, which no config key takes away: the warning says so."""
    agent = _agent(repo)
    spec = providers.AgentSpec(ROLE, mcp={"lado": base.mcp_server(agent)}, read_only=True)
    sess = state.Session("s", str(repo), None, "codex")
    launch = providers.get("codex").launch_command(agent, sess, spec)
    assert _config(launch)["features"]["worktrees"] is False
    [warning] = launch.warnings
    assert "apply_patch" in warning and "w1" in warning
    _, config = _launch(repo)
    assert "worktrees" not in config["features"]


def test_hooks_report_each_event_lado_uses(repo):
    launch, config = _launch(repo)
    groups = config["hooks"]
    assert set(groups) - {"state"} == set(codex.EVENTS)
    # SessionEnd also ends a conversation /resume leaves, after the next one has started.
    assert "SessionEnd" not in groups
    for event in codex.EVENTS:
        [group] = groups[event]
        [handler] = group["hooks"]
        assert handler["type"] == "command"
        assert handler["command"] == base.hook_command(_agent(repo), event)
    # Interrupt's hook gets a second by default; its hand-over may take longer.
    assert groups["Interrupt"][0]["hooks"][0]["timeout"] == 3
    # The turn-end hook gets LADO's limit: a batch it never printed waits that long, and a
    # margin, before it is typed in (lado.runtime.HOOK_OUTPUT_WAIT).
    assert groups["Stop"][0]["hooks"][0]["timeout"] == base.TURN_END_HOOK_TIMEOUT == 60


def test_lado_trusts_its_own_hooks_so_codex_asks_no_review(repo, lado_home):
    launch, config = _launch(repo)
    source = Path(launch.env["CODEX_HOME"]).resolve() / "config.toml"
    trusted = config["hooks"]["state"]
    for event, label in codex.LABELS.items():
        if event not in codex.EVENTS:
            continue
        [group] = config["hooks"][event]
        key = f"{source}:{label}:0:0"
        assert trusted[key] == {"trusted_hash": codex.hook_hash(event, group, group["hooks"][0])}


# Written by Codex CLI 0.162.0 when the human trusted these two hooks in its review dialog.
CODEX_WROTE = [
    (
        "Stop",
        "echo stop >> /private/tmp/claude-501/-Users-kao-Projects-lado--lado-worktrees-agents-"
        "feature-codex-provider/23d990cc-443c-4cea-afb5-930903359aae/scratchpad/p1/log",
        "sha256:5a84426ebb716d20775c3268a2eb9c460064ee1dd63144dbe4a0dfbd82236130",
    ),
    (
        "SessionEnd",
        "echo end >> /private/tmp/claude-501/-Users-kao-Projects-lado--lado-worktrees-agents-"
        "feature-codex-provider/23d990cc-443c-4cea-afb5-930903359aae/scratchpad/p1/log",
        "sha256:46895cb473c16a7ef9d7fe412cd6bcfc6f7da0ff0682c9226d8691f052fffbca",
    ),
]


@pytest.mark.parametrize(("event", "command", "written"), CODEX_WROTE)
def test_the_hook_hash_is_the_one_codex_writes(event, command, written):
    handler = {"type": "command", "command": command}
    assert codex.hook_hash(event, {"hooks": [handler]}, handler) == written


def test_the_hook_hash_follows_what_codex_normalizes():
    def digest(event, group, handler):
        return codex.hook_hash(event, group, handler)

    plain = {"type": "command", "command": "x"}
    # The default timeout counts as given.
    assert digest("Stop", {}, plain) == digest("Stop", {}, {**plain, "timeout": 600})
    assert digest("Interrupt", {}, plain) == digest("Interrupt", {}, {**plain, "timeout": 1})
    assert digest("Interrupt", {}, {**plain, "timeout": 9}) == digest(
        "Interrupt", {}, {**plain, "timeout": 3}
    )
    # Stop has no matcher; PostToolUse has.
    assert digest("Stop", {"matcher": "a"}, plain) == digest("Stop", {}, plain)
    assert digest("PostToolUse", {"matcher": "a"}, plain) != digest("PostToolUse", {}, plain)
    assert digest("Stop", {}, {**plain, "async": True}) != digest("Stop", {}, plain)


def test_the_hook_limit_is_the_timeout_codex_gives_lado_s_hook(repo):
    cli = providers.get("codex")
    # The same timeout the hook hash goes by, for the handler LADO writes (HOOK_TIMEOUTS).
    assert [cli.hook_limit(e) for e in ("UserPromptSubmit", "Stop", "Interrupt")] == [600, 60, 3]
    _, config = _launch(repo)
    for event in ("Stop", "Interrupt"):
        [group] = config["hooks"][event]
        assert group["hooks"][0]["timeout"] == cli.hook_limit(event)


def test_lado_s_mcp_server_starts_with_the_agent_and_is_used_without_asking(repo):
    agent = _agent(repo)
    _, config = _launch(repo)
    lado = config["mcp_servers"]["lado"]
    server = base.mcp_server(agent)
    assert [lado["command"], *lado["args"]] == server.command
    assert lado["env"] == server.env
    # Its tools are there at the first turn, and calling them asks nobody.
    assert lado["required"] is True
    assert lado["default_tools_approval_mode"] == "approve"


def test_a_kit_server_gets_the_variables_it_reads(repo):
    agent = _agent(repo)
    db = providers.McpServer(["db-server", "--port", "1"], {"T": "x"}, ["TOKEN"])
    spec = providers.AgentSpec("r", mcp={"lado": base.mcp_server(agent), "db": db})
    _, config = _launch(repo, spec=spec)
    # Codex gives a server only some of its environment, plus these names.
    entry = config["mcp_servers"]["db"]
    assert (entry["command"], entry["args"], entry["env"]) == (
        "db-server",
        ["--port", "1"],
        {"T": "x"},
    )
    assert "TOKEN" in entry["env_vars"]


def test_every_server_gets_the_agents_whole_environment_by_name(repo):
    """Codex starts a stdio server with only a few variables, plus those `env_vars` names:
    each server gets the agent's environment, as the other CLIs give it, by name only."""
    agent = _agent(repo)
    db = providers.McpServer(["db-server"], {"T": "x"}, ["TOKEN"])
    environ = {"PATH": "/bin", "TMUX_TMPDIR": "/tmp/t", "DB_PROFILE": "s3cr3t-value"}
    spec = providers.AgentSpec("r", mcp={"lado": base.mcp_server(agent), "db": db}, environ=environ)
    launch, config = _launch(repo, spec=spec)
    for server in config["mcp_servers"].values():
        assert {"PATH", "TMUX_TMPDIR", "DB_PROFILE", "LADO_SESSION"} <= set(server["env_vars"])
    assert "TOKEN" in config["mcp_servers"]["db"]["env_vars"]
    text = (Path(launch.env["CODEX_HOME"]) / "config.toml").read_text()
    assert "s3cr3t-value" not in text


def test_skills_are_linked_in_the_codex_home(repo, tmp_path):
    skill = tmp_path / "kit" / "notes"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("---\nname: notes\ndescription: d\n---\n")
    spec = providers.AgentSpec("r", skills={"notes": skill})
    launch, _ = _launch(repo, spec=spec)
    link = Path(launch.env["CODEX_HOME"]) / "skills" / "notes"
    assert link.is_symlink() and link.resolve() == skill.resolve()


@pytest.mark.parametrize(
    ("mode", "flags"),
    [
        (None, []),
        ("default", ["-a", "on-request"]),
        ("bypassPermissions", ["--dangerously-bypass-approvals-and-sandbox"]),
    ],
)
def test_permission_modes(repo, mode, flags):
    launch, _ = _launch(repo, mode)
    assert launch.argv == ["codex", "--no-daemon", *flags]


def test_other_permission_modes_are_refused():
    cli = providers.get("codex")
    assert cli.permission_modes == ("default", "bypassPermissions")
    with pytest.raises(ValueError, match='"plan" is not supported by Codex CLI'):
        cli.check_permission_mode("plan")


@pytest.mark.parametrize("mode", [None, "default"])
def test_a_worker_in_the_sandbox_may_commit_but_not_change_git_hooks(repo, mode):
    """Codex keeps .git and a worktree's git folder read-only in its sandbox; a worker must
    commit, so LADO's permission profile lets it write there, but for the hooks and config
    git would run outside the sandbox."""
    worktree = _worktree(repo)
    git = (repo / ".git").resolve()
    agent = _agent(worktree)
    spec = providers.AgentSpec("r", mcp={"lado": base.mcp_server(agent)})
    sess = state.Session("s", str(repo), mode, "codex")
    config = _config(providers.get("codex").launch_command(agent, sess, spec))
    assert config["default_permissions"] == "lado"
    assert config["permissions"]["lado"] == {
        "extends": ":workspace",
        "filesystem": {
            str(git): "write",
            str(git / "worktrees" / "w1"): "write",
            str(git / "hooks"): "read",
            str(git / "config"): "read",
        },
    }


def test_bypassing_the_sandbox_needs_no_permission_profile(repo):
    _, config = _launch(repo, "bypassPermissions")
    assert "default_permissions" not in config and "permissions" not in config


USER_CONFIG = """
model = "qwen3-coder:30b"
model_provider = "ollama"
oss_provider = "ollama"
profile = "fast"
model_reasoning_effort = "high"
sandbox_mode = "danger-full-access"
notify = ["say", "done"]
developer_instructions = "the user's own"

[model_providers.ollama]
name = "Ollama"
base_url = "http://localhost:11434/v1"

[profiles.fast]
model = "small"

[mcp_servers.mine]
command = "mine"

[[hooks.Stop]]
[[hooks.Stop.hooks]]
type = "command"
command = "user-hook"
"""


def test_the_user_s_model_settings_are_carried_and_nothing_else(repo, codex_home):
    _user_config(codex_home, USER_CONFIG)
    launch, config = _launch(repo)
    user = tomllib.loads(USER_CONFIG)
    for key in codex.CARRIED:
        assert config[key] == user[key]
    assert "sandbox_mode" not in config and "notify" not in config
    assert set(config["mcp_servers"]) == {"lado"}
    assert config["developer_instructions"] == ROLE
    assert [h["hooks"][0]["command"] for h in config["hooks"]["Stop"]] != ["user-hook"]
    assert launch.warnings == []
    # Read, never written.
    assert (codex_home / "config.toml").read_text() == USER_CONFIG


def test_the_user_s_codex_home_is_the_agents_codex_home_or_home(repo, tmp_path):
    folder = tmp_path / "elsewhere" / ".codex"
    _user_config(folder, 'model = "from-home"\n')
    _, config = _launch(repo, environ={"HOME": str(folder.parent)})
    assert config["model"] == "from-home"
    _, config = _launch(repo, environ={"HOME": "/nowhere", "CODEX_HOME": str(folder)})
    assert config["model"] == "from-home"


def test_no_user_config_is_fine(repo, codex_home):
    launch, config = _launch(repo)
    assert "model" not in config and launch.warnings == []


def test_a_user_config_codex_cannot_read_is_a_warning(repo, codex_home):
    _user_config(codex_home, 'model = "x"\nmodel = "twice"\n')
    launch, config = _launch(repo)
    assert "model" not in config
    [warning] = launch.warnings
    assert str(codex_home / "config.toml") in warning
    assert "nothing of it is carried" in warning


def test_a_carried_value_lado_cannot_write_is_a_warning(repo, codex_home):
    _user_config(codex_home, 'model = "m"\n[profiles.p]\nsince = 1979-05-27T07:32:00Z\nx = 1\n')
    launch, config = _launch(repo)
    assert config["model"] == "m"
    assert config["profiles"] == {"p": {"x": 1}}
    [warning] = launch.warnings
    assert "profiles.p.since" in warning


@pytest.mark.parametrize(
    "value",
    [
        'say "hi"\\ there\nnext\ttab\x01\x7f é 🙂',
        "",
        1,
        -7,
        2.5,
        1e-05,
        True,
        False,
        [1, 2],
        ["a", ["b", "c"]],
        [],
        {},
        {"a b": {"c.d": "e", "": 1}},
        [{"x": 1, "sub": {"y": 2}}, {"x": 3}],
        {"t": [{"a": [{"b": 1}]}]},
        [1, {"inline": True}],
    ],
)
def test_the_toml_writer_reads_back(value):
    doc = {"key": value, "after": "x"}
    assert tomllib.loads(codex.toml_text(doc)) == doc


def test_the_toml_writer_writes_inf_and_nan():
    read = tomllib.loads(codex.toml_text({"a": math.inf, "b": -math.inf, "c": math.nan}))
    assert read["a"] == math.inf and read["b"] == -math.inf and math.isnan(read["c"])


def test_the_toml_writer_refuses_what_it_cannot_write():
    with pytest.raises(codex.Unwritable) as raised:
        codex.toml_text({"a": {"b": datetime.date(2026, 1, 1)}})
    assert raised.value.key == "a.b"


@pytest.mark.parametrize(
    ("native", "payload", "expected"),
    [
        ("SessionStart", {"source": "startup"}, Event(providers.SESSION_START)),
        # /new and /resume start another conversation at the next prompt; a session start
        # only makes a starting or held agent ready (lado.hooks).
        ("SessionStart", {"source": "clear"}, Event(providers.SESSION_START)),
        ("SessionStart", {"source": "resume"}, Event(providers.SESSION_START)),
        ("UserPromptSubmit", {"prompt": "hi"}, Event(providers.PROMPT_SUBMIT, "hi")),
        ("Stop", {"stop_hook_active": False}, Event(providers.TURN_END)),
        # Codex says nothing of work still running: never `background`.
        ("Stop", {"background_tasks": [{"status": "running"}]}, Event(providers.TURN_END)),
        ("Stop", {"stop_hook_active": True}, Event(providers.TURN_END, continued=True)),
        # Esc, or a refused approval: the turn ends, and Codex ignores the hook's output.
        ("Interrupt", {}, Event(providers.TURN_END, output_ignored=True)),
        ("SessionEnd", {"reason": "other"}, None),
        ("PreToolUse", {"tool_name": "Bash"}, None),
    ],
)
def test_codex_maps_native_events(native, payload, expected):
    assert providers.get("codex").parse_event(native, json.dumps(payload)) == expected


@pytest.mark.parametrize(
    ("native", "payload"),
    [
        ("SessionStart", {"source": "startup"}),
        ("UserPromptSubmit", {"prompt": "hi"}),
        ("Stop", {"stop_hook_active": False}),
        ("Interrupt", {}),
        ("PermissionRequest", {"tool_name": "Bash", "tool_input": {}}),
        ("PostToolUse", {"tool_name": "Bash", "tool_input": {}}),
    ],
)
def test_every_codex_hook_names_the_model(native, payload):
    cli = providers.get("codex")
    event = cli.parse_event(native, json.dumps({**payload, "model": "gpt-5.5"}))
    assert (event.model, event.effort) == ("gpt-5.5", None)  # no hook names the effort
    assert cli.parse_event(native, json.dumps(payload)).model == ""
    assert cli.parse_event(native, json.dumps({**payload, "model": 5})).model == ""


def test_carried_model_of_the_chosen_profile(repo, codex_home):
    _user_config(
        codex_home,
        'profile = "work"\nmodel = "gpt-5.5"\nmodel_reasoning_effort = "low"\n'
        '[profiles.work]\nmodel = "gpt-5.6-sol"\nmodel_reasoning_effort = "high"\n',
    )
    launch, _ = _launch(repo)
    assert launch.model == state.Choice("gpt-5.6-sol", state.CLI_CONFIG, "profile work")
    assert launch.effort == state.Choice("high", state.CLI_CONFIG, "profile work")


def test_carried_model_falls_back_to_the_top_level(repo, codex_home):
    _user_config(
        codex_home,
        'profile = "work"\nmodel = "gpt-5.5"\n[profiles.work]\nmodel_reasoning_effort = "high"\n',
    )
    launch, _ = _launch(repo)
    assert launch.model == state.Choice("gpt-5.5", state.CLI_CONFIG)
    assert launch.effort == state.Choice("high", state.CLI_CONFIG, "profile work")


def test_no_carried_model_leaves_none(repo, codex_home):
    _user_config(codex_home, '[profiles.work]\nmodel = "gpt-5.6-sol"\n')  # not the chosen one
    launch, _ = _launch(repo)
    assert (launch.model, launch.effort) == (None, None)


def test_codex_pairs_an_approval_with_its_tool_call():
    cli = providers.get("codex")
    asked = {"tool_name": "mcp__echo__echo", "tool_input": {"text": "hello"}, "turn_id": "t"}
    done = {**asked, "tool_use_id": "u1", "tool_response": "echo: hello"}
    wait = cli.parse_event("PermissionRequest", json.dumps(asked))
    answer = cli.parse_event("PostToolUse", json.dumps(done))
    assert (wait.kind, answer.kind) == (providers.WAITING, providers.RESUMED)
    assert wait.key == answer.key != ""
    other = cli.parse_event("PostToolUse", json.dumps({**done, "tool_input": {"text": "x"}}))
    assert other.key != wait.key


def test_codex_continues_with_queued_messages():
    out = providers.get("codex").continue_output("[from w1] done")
    assert json.loads(out) == {"decision": "block", "reason": "[from w1] done"}


def test_codex_capabilities():
    caps = providers.get("codex").capabilities
    assert caps.status_events and caps.permission_event and caps.deliver_on_turn_end
    assert caps.skills and caps.notice_on_argv and caps.session_start_on_first_input
    assert not caps.hold_first_turn


def test_a_codex_supervisor_starts_with_lado_s_line(repo, fake_tmux, codex_home):
    _trust(codex_home, repo.resolve())
    runtime.start_session(str(repo), "s", None, provider="codex")
    [hello] = state.list_messages("s")
    _, argv = agent_helpers.launched(fake_tmux[0])
    assert argv[-1] == f"[from lado] {runtime.FIRST_INPUT}"
    assert argv[-1] == (
        "[from lado] session started; nothing to do yet: end this turn,"
        " the next message starts a new one"
    )
    hooks.handle(providers.get("codex"), Event(providers.SESSION_START), "s", "supervisor")
    hooks.handle(
        providers.get("codex"), Event(providers.PROMPT_SUBMIT, argv[-1]), "s", "supervisor"
    )
    assert state.list_messages("s")[0].state == state.DELIVERED


def test_the_first_input_asks_to_end_the_turn_not_to_wait():
    """A model with a tool to wait takes "wait" literally and its turn never ends (LAD-167)."""
    assert "wait" not in runtime.FIRST_INPUT.lower()
    assert "end this turn" in runtime.FIRST_INPUT


def test_a_codex_supervisor_with_a_first_message_gets_no_first_input(repo, fake_tmux, codex_home):
    """The human's first message starts its session: no turn of LADO's FIRST_INPUT first."""
    _trust(codex_home, repo.resolve())
    runtime.start_session(str(repo), "s", None, provider="codex", prompt="Take LAD-19")
    [first] = state.list_messages("s")
    assert first.sender == "human"
    _, argv = agent_helpers.launched(fake_tmux[0])
    assert argv[-1] == (
        f"[from human] {runtime.FIRST_MESSAGE} (#{first.id}, 1 line: call read_messages)"
    )
    assert not [a for a in argv if "LAD-19" in a]


# Codex's own rule (0.162.0, checked by hand): the agent's folder, its project root (the
# nearest folder up with .git), then its repository's main root; the first entry with a
# trust level decides, trusted or not. Nothing above the git root counts.


def test_codex_trusts_the_repo_the_user_trusts(repo, codex_home):
    _trust(codex_home, repo.resolve())
    launch, config = _launch(repo)
    assert config["projects"] == {str(repo.resolve()): {"trust_level": "trusted"}}
    assert _blocker(launch, repo).reason is None


def test_a_repo_the_user_never_trusted_is_trusted_by_the_agents_config(repo, codex_home):
    launch, config = _launch(repo)
    assert config["projects"] == {str(repo.resolve()): {"trust_level": "trusted"}}
    assert _blocker(launch, repo).reason is None
    assert not codex_home.exists()  # nothing written into the user's Codex home


def test_a_worker_trusts_the_main_repos_root(repo, codex_home):
    worktree = _worktree(repo)
    launch, config = _launch(worktree)
    assert config["projects"] == {str(repo.resolve()): {"trust_level": "trusted"}}
    assert _blocker(launch, worktree).reason is None


def test_a_folder_of_no_repository_is_trusted_by_its_real_path(tmp_path, codex_home):
    folder = tmp_path / "plain"
    folder.mkdir()
    launch, config = _launch(folder)
    assert config["projects"] == {str(folder.resolve()): {"trust_level": "trusted"}}
    assert _blocker(launch, folder).reason is None


def _rewrite(launch, change):
    """The agent's config.toml as LADO did not write it: `change` edits its table."""
    path = Path(launch.env["CODEX_HOME"]) / "config.toml"
    config = tomllib.loads(path.read_text())
    change(config)
    path.write_text(codex.toml_text(config))


def test_a_config_lado_did_not_write_without_the_trust_asks(repo, codex_home):
    """A hand-edited home: Codex asks, and the reason says so."""
    launch, _ = _launch(repo)
    _rewrite(launch, lambda config: config.pop("projects"))
    blocker = _blocker(launch, repo)
    assert blocker.reason.startswith(f"Codex CLI asks whether to trust {repo.resolve()}")
    assert "Trust and continue" in blocker.reason


def test_trust_above_the_git_root_does_not_cover_it(repo, codex_home):
    _trust(codex_home, repo.parent.resolve())
    launch, config = _launch(repo)
    # Not the user's entry, which Codex would not go by: LADO's own.
    assert config["projects"] == {str(repo.resolve()): {"trust_level": "trusted"}}
    assert _blocker(launch, repo).reason is None


def test_a_subfolder_is_trusted_by_its_repo(repo, codex_home):
    (repo / "sub").mkdir()
    _trust(codex_home, repo.resolve())
    launch, _ = _launch(repo / "sub")
    assert _blocker(launch, repo / "sub").reason is None


def test_a_worktree_is_trusted_by_its_main_repo(repo, codex_home):
    _trust(codex_home, repo.resolve())
    worktree = _worktree(repo)
    launch, config = _launch(worktree)
    assert config["projects"] == {str(repo.resolve()): {"trust_level": "trusted"}}
    assert _blocker(launch, worktree).reason is None


def test_a_subfolder_of_a_worktree_is_trusted_by_the_worktree(repo, codex_home):
    worktree = _worktree(repo)
    (worktree / "sub").mkdir()
    _trust(codex_home, worktree.resolve())
    launch, config = _launch(worktree / "sub")
    assert config["projects"] == {str(worktree.resolve()): {"trust_level": "trusted"}}
    assert _blocker(launch, worktree / "sub").reason is None


def test_a_folder_is_trusted_by_its_real_path(repo, codex_home, tmp_path):
    link = tmp_path / "link"
    link.symlink_to(repo)
    _trust(codex_home, repo.resolve())
    launch, _ = _launch(link)
    assert _blocker(launch, link).reason is None


def test_an_untrusted_repo_is_carried_and_asks_nothing(repo, codex_home):
    _trust(codex_home, repo.resolve(), level="untrusted")
    launch, config = _launch(repo)
    assert config["projects"] == {str(repo.resolve()): {"trust_level": "untrusted"}}
    assert _blocker(launch, repo).reason is None


def test_an_agent_config_lado_cannot_read_is_a_warning(repo, codex_home):
    launch, _ = _launch(repo)
    (Path(launch.env["CODEX_HOME"]) / "config.toml").write_text("= broken")
    blocker = _blocker(launch, repo)
    assert blocker.reason is None
    assert blocker.warning.startswith("cannot tell whether Codex CLI asks")


REPO_HOOKS = {"hooks": {"Stop": [{"hooks": [{"type": "command", "command": "repo-hook"}]}]}}


def _repo_hooks(repo):
    (repo / ".codex").mkdir()
    (repo / ".codex" / "hooks.json").write_text(json.dumps(REPO_HOOKS))
    group = REPO_HOOKS["hooks"]["Stop"][0]
    return group, codex.hook_hash("Stop", group, group["hooks"][0])


def _repo_hook_key(repo, file="hooks.json"):
    return f"{repo.resolve() / '.codex' / file}:stop:0:0"


def test_the_repo_s_own_hooks_are_trusted_by_the_agents_config(repo, codex_home):
    """As a human who trusts the folder takes them; the user never reviewed them."""
    _, digest = _repo_hooks(repo)
    launch, config = _launch(repo)
    assert config["hooks"]["state"][_repo_hook_key(repo)] == {"trusted_hash": digest}
    assert _blocker(launch, repo).reason is None
    assert not codex_home.exists()


@pytest.mark.parametrize(
    "text",
    ['hooks = "x"\n', '[hooks]\nstate = "x"\n', '[hooks.state]\n"{key}" = "x"\n'],
)
def test_user_hooks_of_odd_types_crash_no_launch(repo, codex_home, text):
    """No table where Codex has one is no trust of the user's: the repository's hooks are
    trusted as with none."""
    _, digest = _repo_hooks(repo)
    _user_config(codex_home, text.format(key=_repo_hook_key(repo)))
    launch, config = _launch(repo)
    assert config["hooks"]["state"][_repo_hook_key(repo)] == {"trusted_hash": digest}
    assert _blocker(launch, repo).reason is None


def test_a_repo_hook_the_user_disabled_stays_disabled(repo, codex_home):
    _repo_hooks(repo)
    key = _repo_hook_key(repo)
    _user_config(codex_home, f'[hooks.state."{key}"]\nenabled = false\n')
    launch, config = _launch(repo)
    assert config["hooks"]["state"][key] == {"enabled": False}
    assert _blocker(launch, repo).reason is None


def test_an_unreadable_repo_hooks_file_is_left_to_codex(repo, codex_home):
    """No hook read, no hash: Codex warns and skips such a file itself."""
    (repo / ".codex").mkdir()
    (repo / ".codex" / "hooks.json").write_text("{ not json")
    launch, config = _launch(repo)
    assert not [k for k in config["hooks"]["state"] if "hooks.json" in k]
    assert _blocker(launch, repo).reason is None


def test_the_repo_s_own_hooks_asked_about_are_named(repo, codex_home):
    """A config LADO did not write: the review question is named."""
    _repo_hooks(repo)
    launch, _ = _launch(repo)
    _rewrite(launch, lambda config: config["hooks"]["state"].pop(_repo_hook_key(repo)))
    blocker = _blocker(launch, repo)
    assert blocker.reason.startswith("Codex CLI asks to review the repository's own hooks")
    assert str(repo.resolve() / ".codex" / "hooks.json") in blocker.reason


def test_the_user_s_trust_in_the_repo_s_hooks_is_carried(repo, codex_home):
    _, digest = _repo_hooks(repo)
    key = f"{repo.resolve() / '.codex' / 'hooks.json'}:stop:0:0"
    other = f"{repo.resolve() / 'elsewhere.json'}:stop:0:0"
    _user_config(
        codex_home,
        f'[projects."{repo.resolve()}"]\ntrust_level = "trusted"\n'
        f'[hooks.state."{key}"]\ntrusted_hash = "{digest}"\n'
        f'[hooks.state."{other}"]\ntrusted_hash = "sha256:x"\n',
    )
    launch, config = _launch(repo)
    assert config["hooks"]["state"][key] == {"trusted_hash": digest}
    assert other not in config["hooks"]["state"]
    assert _blocker(launch, repo).reason is None


def test_a_worktree_runs_the_main_checkout_s_hooks_with_the_user_s_trust(repo, codex_home):
    """Codex loads a linked worktree's project hooks from the main checkout's .codex, by
    that file's path: the user's trust from the main checkout holds there too."""
    _, digest = _repo_hooks(repo)
    subprocess.run(["git", "-C", str(repo), "add", ".codex"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "hooks"], check=True)
    key = f"{repo.resolve() / '.codex' / 'hooks.json'}:stop:0:0"
    _user_config(
        codex_home,
        f'[projects."{repo.resolve()}"]\ntrust_level = "trusted"\n'
        f'[hooks.state."{key}"]\ntrusted_hash = "{digest}"\n',
    )
    worktree = _worktree(repo)
    launch, config = _launch(worktree)
    assert config["hooks"]["state"][key] == {"trusted_hash": digest}
    assert _blocker(launch, worktree).reason is None


def test_hooks_in_the_repo_s_codex_config_count_too(repo, codex_home):
    (repo / ".codex").mkdir()
    (repo / ".codex" / "config.toml").write_text(
        '[[hooks.Stop]]\n[[hooks.Stop.hooks]]\ntype = "command"\ncommand = "repo-hook"\n'
    )
    launch, config = _launch(repo)
    assert _repo_hook_key(repo, "config.toml") in config["hooks"]["state"]
    assert _blocker(launch, repo).reason is None
    _rewrite(launch, lambda c: c["hooks"]["state"].pop(_repo_hook_key(repo, "config.toml")))
    assert str(repo.resolve() / ".codex" / "config.toml") in _blocker(launch, repo).reason


def test_an_untrusted_repo_s_hooks_do_not_load(repo, codex_home):
    _repo_hooks(repo)
    _trust(codex_home, repo.resolve(), level="untrusted")
    launch, config = _launch(repo)
    assert _repo_hook_key(repo) not in config["hooks"]["state"]  # none to trust
    assert _blocker(launch, repo).reason is None


def test_a_repo_codex_will_ask_about_names_its_hooks_too(repo, codex_home):
    _repo_hooks(repo)
    launch, _ = _launch(repo)

    def forget(config):
        config.pop("projects")
        config["hooks"]["state"].pop(_repo_hook_key(repo))

    _rewrite(launch, forget)
    reason = _blocker(launch, repo).reason
    assert "whether to trust" in reason and "hooks.json" in reason


def test_plugins_are_off_and_the_login_is_kept_in_a_file(repo):
    """Codex would clone its plugins catalogue into each new home at its start; and a
    keyring login would be one of each agent's home."""
    _, config = _launch(repo)
    assert config["features"]["plugins"] is False
    assert config["cli_auth_credentials_store"] == "file"


def test_the_user_s_codex_home_is_written_for_the_login(repo, tmp_path):
    """The waiting window's environment holds the agent's own CODEX_HOME: the user's is
    kept beside its config (lado.providers.codex._settle_login)."""
    launch, _ = _launch(repo, environ={"HOME": "/h", "CODEX_HOME": str(tmp_path / "u")})
    home = Path(launch.env["CODEX_HOME"])
    assert (home / "user-codex-home").read_text() == f"{tmp_path / 'u'}\n"
    _launch(repo, environ={"HOME": "/h"})
    assert (home / "user-codex-home").read_text() == "/h/.codex\n"


# The agent's login (D1 of openspec change codex-shared-login): settled before its first
# hook, and again by its waiting window once a login is there (lado.login_wait).


def _homes(tmp_path, user_file=True):
    """An agent's Codex home that knows the user's; the user's with a login file."""
    home, user = tmp_path / "agent", tmp_path / "user"
    home.mkdir()
    if user_file:
        user.mkdir()
        (user / "auth.json").write_text("{}")
    (home / "user-codex-home").write_text(f"{user}\n")
    return home, user


def _settle(repo, home, **env):
    return providers.get("codex").first_hook_blocker(
        str(repo), {"HOME": "/h", "CODEX_HOME": str(home), **env}
    )


def test_the_agents_login_is_a_link_to_the_users(repo, tmp_path):
    home, user = _homes(tmp_path)
    blocker = _settle(repo, home)
    auth = home / "auth.json"
    assert auth.is_symlink() and os.readlink(auth) == str(user / "auth.json")
    assert f"LADO linked {auth} to {user / 'auth.json'}" in blocker.notes


def test_a_link_to_a_missing_file_is_made_without_its_folder(repo, tmp_path):
    """The user logs in later (a sign-in code): the link then reaches the login."""
    home, user = _homes(tmp_path, user_file=False)
    _settle(repo, home)
    assert os.readlink(home / "auth.json") == str(user / "auth.json")
    assert not user.exists()


def test_an_existing_link_is_left_with_no_note(repo, tmp_path):
    home, _ = _homes(tmp_path)
    _settle(repo, home)
    assert not [n for n in _settle(repo, home).notes if "auth.json" in n]


def test_without_the_users_home_written_it_is_the_default_one(repo, tmp_path):
    """An agent launched by an older LADO."""
    home, _ = _homes(tmp_path)
    (home / "user-codex-home").unlink()
    _settle(repo, home)
    assert os.readlink(home / "auth.json") == "/h/.codex/auth.json"


def test_an_api_key_becomes_the_agents_own_file(repo, tmp_path):
    """Codex's TUI does not read OPENAI_API_KEY: the agent gets it as Codex's own key
    login keeps it."""
    home, user = _homes(tmp_path)
    _settle(repo, home)  # a link first
    blocker = _settle(repo, home, OPENAI_API_KEY="sk-canary")
    auth = home / "auth.json"
    assert not auth.is_symlink()
    assert json.loads(auth.read_text()) == {"auth_mode": "apikey", "OPENAI_API_KEY": "sk-canary"}
    assert auth.stat().st_mode & 0o777 == 0o600
    assert (user / "auth.json").read_text() == "{}"  # the user's file untouched
    assert f"LADO wrote the API key of OPENAI_API_KEY into {auth}" in blocker.notes
    assert "canary" not in repr(blocker)


def test_the_access_token_wins_over_the_key(repo, tmp_path):
    home, user = _homes(tmp_path)
    _settle(repo, home, OPENAI_API_KEY="sk-x", CODEX_ACCESS_TOKEN="at-x")
    assert os.readlink(home / "auth.json") == str(user / "auth.json")


def test_a_key_file_turns_back_into_the_link(repo, tmp_path):
    home, user = _homes(tmp_path)
    _settle(repo, home, OPENAI_API_KEY="sk-x")
    _settle(repo, home)
    assert os.readlink(home / "auth.json") == str(user / "auth.json")


@pytest.mark.skipif(os.geteuid() == 0, reason="root writes any folder")
def test_a_login_lado_cannot_settle_is_a_warning(repo, tmp_path):
    home, _ = _homes(tmp_path)
    home.chmod(0o500)
    try:
        blocker = _settle(repo, home)
    finally:
        home.chmod(0o700)
    assert blocker.reason is None
    assert blocker.warning.startswith(f"cannot give the agent its Codex CLI login in {home}: ")
    # Its status is read in its own home, where no login is now: on a model that needs one,
    # it waits for a login it cannot see (Provider.needs_login), and the warning says so.
    assert blocker.warning.endswith(
        "; an agent whose model needs a login waits for one until it starts again with its "
        "folder writable"
    )


def test_a_launched_agent_gets_its_login_and_trust_with_notes(repo, codex_home):
    launch, _ = _launch(repo)
    blocker = _blocker(launch, repo)
    home = Path(launch.env["CODEX_HOME"])
    assert blocker.reason is None
    assert os.readlink(home / "auth.json") == str(codex_home / "auth.json")
    assert blocker.notes == (f"LADO linked {home / 'auth.json'} to {codex_home / 'auth.json'}",)
