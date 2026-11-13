"""Codex CLI as a LADO provider (lado.providers.codex)."""

import datetime
import json
import math
import os
import subprocess
import sys
from pathlib import Path

import pytest

from lado import providers, runtime, state
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


def _launch(cwd, mode=None, spec=None, notice=None, environ=None, model=None):
    """Launch a Codex agent in `cwd`; its Launch and the config.toml LADO wrote for it."""
    agent = _agent(cwd)
    if spec is None:
        environ = dict(os.environ) if environ is None else environ
        spec = providers.AgentSpec(
            ROLE, mcp={"lado": base.mcp_server(agent)}, environ=environ, model=model
        )
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


# Codex's sandbox on Linux needs bubblewrap, which Docker's seccomp refuses (LAD-151).
BWRAP = (
    "bwrap: No permissions to create a new namespace, likely because the kernel does not "
    "allow non-privileged user namespaces."
)
IN_CONTAINER = (
    f"Codex's sandbox cannot start here ({BWRAP}): Codex agent w1 runs without it, and "
    "LADO's container is its only boundary"
)
ON_A_HOST = (
    f"Codex's sandbox cannot start here ({BWRAP}): Codex agent w1 asks before each shell "
    "command; docs/install.md says how to allow it, or use bypassPermissions"
)


@pytest.fixture
def linux(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.delenv("LADO_CONTAINER", raising=False)


@pytest.mark.parametrize("mode", [None, "default"])
def test_the_sandbox_is_tried_with_the_agents_home_and_config(repo, linux, codex_sandbox, mode):
    launch, _ = _launch(repo, mode)
    [(home, cwd, config)] = codex_sandbox.calls
    assert str(home) == launch.env["CODEX_HOME"] and cwd == repo
    assert 'default_permissions = "lado"' in config
    assert launch.argv == ["codex", "--no-daemon", *(["-a", "on-request"] if mode else [])]
    assert not launch.warnings


@pytest.mark.parametrize(
    ("platform", "mode"), [("linux", "bypassPermissions"), ("darwin", None), ("darwin", "default")]
)
def test_no_probe_in_bypass_mode_nor_on_macos(repo, monkeypatch, codex_sandbox, platform, mode):
    monkeypatch.setattr(sys, "platform", platform)
    monkeypatch.setenv("LADO_CONTAINER", "1")
    codex_sandbox.error = BWRAP
    launch, _ = _launch(repo, mode)
    assert codex_sandbox.calls == [] and not launch.warnings
    assert "danger-full-access" not in launch.argv


@pytest.mark.parametrize(("mode", "flags"), [("default", ["-a", "on-request"]), (None, [])])
def test_in_the_container_a_sandbox_that_cannot_start_is_left_out(
    repo, linux, monkeypatch, codex_sandbox, mode, flags
):
    monkeypatch.setenv("LADO_CONTAINER", "1")
    codex_sandbox.error = BWRAP
    launch, config = _launch(repo, mode)
    assert launch.argv == ["codex", "--no-daemon", *flags, "--sandbox", "danger-full-access"]
    assert "default_permissions" not in config and "permissions" not in config
    assert launch.warnings == [IN_CONTAINER]


def test_in_the_container_with_a_notice_the_sandbox_flag_comes_before_it(
    repo, linux, monkeypatch, codex_sandbox
):
    monkeypatch.setenv("LADO_CONTAINER", "1")
    codex_sandbox.error = BWRAP
    launch, _ = _launch(repo, "default", notice="hello")
    assert launch.argv[-3:] == ["--sandbox", "danger-full-access", "hello"]


def test_on_a_host_a_sandbox_that_cannot_start_stays_with_a_warning(repo, linux, codex_sandbox):
    codex_sandbox.error = BWRAP
    launch, config = _launch(repo, "default")
    assert launch.argv == ["codex", "--no-daemon", "-a", "on-request"]
    assert config["default_permissions"] == "lado" and "lado" in config["permissions"]
    assert launch.warnings == [ON_A_HOST]


def _fake_codex(folder, script):
    folder.mkdir(exist_ok=True)
    (folder / "codex").write_text(f"#!/bin/sh\n{script}\n")
    (folder / "codex").chmod(0o755)
    return {**os.environ, "PATH": f"{folder}{os.pathsep}/usr/bin:/bin"}


# The real probe: the autouse fixture codex_sandbox replaces it in each test.
_REAL_PROBE = codex._sandbox_error


def test_the_probe_runs_codex_sandbox_true_in_the_agents_home(tmp_path):
    seen = tmp_path / "seen"
    environ = _fake_codex(tmp_path / "bin", f'echo "$CODEX_HOME|$(pwd)|$*" > {seen}; exit 0')
    assert _REAL_PROBE(tmp_path / "home", tmp_path, environ) is None
    assert seen.read_text().strip() == f"{tmp_path / 'home'}|{tmp_path}|sandbox -- true"


def test_the_probe_gives_the_first_line_of_codexs_error(tmp_path):
    environ = _fake_codex(
        tmp_path / "bin",
        "echo 'WARNING: proceeding, even though we could not create PATH aliases' >&2\n"
        f"echo '{BWRAP}' >&2\necho 'second line' >&2\nexit 1",
    )
    assert _REAL_PROBE(tmp_path, tmp_path, environ) == BWRAP


def test_a_probe_that_fails_with_no_words_says_its_exit(tmp_path):
    environ = _fake_codex(tmp_path / "bin", "exit 3")
    assert _REAL_PROBE(tmp_path, tmp_path, environ) == "`codex sandbox -- true` exited 3"


def test_a_probe_that_hangs_cannot_start(tmp_path, monkeypatch):
    monkeypatch.setattr(codex, "SANDBOX_TIMEOUT", 0.2)
    environ = _fake_codex(tmp_path / "bin", "exec sleep 5")
    assert _REAL_PROBE(tmp_path, tmp_path, environ) == (
        "`codex sandbox -- true` did not end in 0.2 s"
    )


def test_a_missing_codex_cannot_start(tmp_path):
    environ = {**os.environ, "PATH": str(tmp_path / "empty")}
    assert _REAL_PROBE(tmp_path, tmp_path, environ).startswith("cannot run `codex sandbox`")


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


def test_session_model_wins_over_the_carried_profile(repo, codex_home):
    text = (
        'profile = "work"\nmodel = "gpt-5.5"\n'
        '[profiles.work]\nmodel = "gpt-5.5"\nmodel_reasoning_effort = "high"\n'
    )
    _user_config(codex_home, text)
    before = (codex_home / "config.toml").read_bytes()
    launch, config = _launch(repo, model="gpt-5.6-sol")
    assert config["model"] == "gpt-5.6-sol"
    assert config["profiles"]["work"] == {"model": "gpt-5.6-sol", "model_reasoning_effort": "high"}
    assert launch.model == state.Choice("gpt-5.6-sol", state.SESSION)
    assert launch.effort == state.Choice("high", state.CLI_CONFIG, "profile work")
    assert (codex_home / "config.toml").read_bytes() == before


# The repository's .codex/config.toml wins over the agent's config.toml in a trusted folder,
# and -m over both (Codex CLI 0.162.0, checked by hand): the agent's model goes on the
# command line too.
REPO_MODEL = "the repository's .codex/config.toml"


def _repo_model(folder, text='model = "gpt-5.6-terra"\n'):
    (folder / ".codex").mkdir(parents=True, exist_ok=True)
    (folder / ".codex" / "config.toml").write_text(text)


def test_the_session_s_model_goes_on_the_command_line_over_the_repo_s(repo, codex_home):
    _repo_model(repo)
    launch, config = _launch(repo, model="gpt-5.6-luna")
    assert launch.argv == ["codex", "--no-daemon", "-m", "gpt-5.6-luna"]
    assert config["model"] == "gpt-5.6-luna"
    assert launch.model == state.Choice("gpt-5.6-luna", state.SESSION)


def test_the_user_s_carried_model_goes_on_the_command_line(repo, codex_home):
    _repo_model(repo)
    _user_config(codex_home, 'model = "gpt-5.6-sol"\n')
    launch, _ = _launch(repo)
    assert launch.argv == ["codex", "--no-daemon", "-m", "gpt-5.6-sol"]
    assert launch.model == state.Choice("gpt-5.6-sol", state.CLI_CONFIG)


def test_the_carried_profile_s_model_goes_on_the_command_line(repo, codex_home):
    _repo_model(repo)
    _user_config(
        codex_home, 'profile = "work"\nmodel = "gpt-5.5"\n[profiles.work]\nmodel = "gpt-5.6-sol"\n'
    )
    launch, _ = _launch(repo)
    assert launch.argv == ["codex", "--no-daemon", "-m", "gpt-5.6-sol"]
    assert launch.model == state.Choice("gpt-5.6-sol", state.CLI_CONFIG, "profile work")


def test_the_model_comes_before_the_permission_flags_and_the_notice(repo, codex_home):
    launch, _ = _launch(repo, mode="default", notice="hello", model="gpt-5.6-luna")
    assert launch.argv == [
        "codex",
        "--no-daemon",
        "-m",
        "gpt-5.6-luna",
        "-a",
        "on-request",
        "hello",
    ]


def test_no_model_anywhere_goes_on_no_command_line(repo, codex_home):
    launch, _ = _launch(repo)
    assert launch.argv == ["codex", "--no-daemon"]
    assert launch.model is None


def test_a_repo_s_model_with_none_of_lado_s_is_shown_from_the_start(repo, codex_home):
    _repo_model(repo)
    launch, config = _launch(repo)
    assert launch.argv == ["codex", "--no-daemon"]
    assert "model" not in config
    assert launch.model == state.Choice("gpt-5.6-terra", state.CLI_DEFAULT, REPO_MODEL)


def test_a_folder_s_own_codex_config_is_nearer(repo, codex_home):
    _repo_model(repo)
    _repo_model(repo / "sub", 'model = "gpt-5.6-terra-sub"\n')
    launch, _ = _launch(repo / "sub")
    assert launch.model == state.Choice("gpt-5.6-terra-sub", state.CLI_DEFAULT, REPO_MODEL)


def test_a_nearer_codex_config_without_a_model_leaves_the_repo_s(repo, codex_home):
    _repo_model(repo)
    _repo_model(repo / "sub", 'approval_policy = "never"\n')
    launch, _ = _launch(repo / "sub")
    assert launch.model == state.Choice("gpt-5.6-terra", state.CLI_DEFAULT, REPO_MODEL)


def test_a_worker_reads_its_worktree_s_own_codex_config(repo, codex_home):
    _repo_model(repo, 'model = "gpt-5.6-terra-main"\n')
    worktree = _worktree(repo)
    _repo_model(worktree)
    launch, _ = _launch(worktree)
    assert launch.model == state.Choice("gpt-5.6-terra", state.CLI_DEFAULT, REPO_MODEL)


def test_an_untrusted_repo_s_model_is_not_read(repo, codex_home):
    _repo_model(repo)
    _trust(codex_home, repo.resolve(), level="untrusted")
    launch, _ = _launch(repo)
    assert (launch.argv, launch.model) == (["codex", "--no-daemon"], None)


@pytest.mark.parametrize("text", ["model = [", 'approval_policy = "never"\n', "model = 5\n"])
def test_a_repo_codex_config_naming_no_model_gives_none(repo, codex_home, text):
    _repo_model(repo, text)
    launch, _ = _launch(repo)
    assert launch.model is None


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


def test_the_first_input_asks_to_end_the_turn_not_to_wait():
    """A model with a tool to wait takes "wait" literally and its turn never ends (LAD-167)."""
    assert "wait" not in runtime.FIRST_INPUT.lower()
    assert "end this turn" in runtime.FIRST_INPUT


# Codex's own rule (0.162.0, checked by hand): the agent's folder, its project root (the
# nearest folder up with .git), then its repository's main root; the first entry with a
# trust level decides, trusted or not. Nothing above the git root counts.


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


# On a model server.

CATALOGUE = {
    "models": [
        {"slug": "gpt-new", "tool_mode": "code_mode_only", "display_name": "New"},
        {
            "slug": "gpt-5.5",
            "display_name": "GPT-5.5",
            "description": "Legacy coding model.",
            "default_reasoning_level": "medium",
            "supported_reasoning_levels": [{"effort": "low", "description": "fast"}],
            "shell_type": "unified_exec",
            "visibility": "list",
            "additional_speed_tiers": ["fast"],
            "service_tiers": [{"id": "priority", "name": "Fast", "description": "quick"}],
            "availability_nux": {"message": "new"},
            "upgrade": {"model": "gpt-6"},
            "support_verbosity": True,
            "default_verbosity": "low",
            "apply_patch_tool_type": "freeform",
            "context_window": 272000,
            "max_context_window": 272000,
            "experimental_supported_tools": ["x"],
            "input_modalities": ["text", "image"],
            "supports_search_tool": True,
            "supports_reasoning_effort_updates": True,
            "multi_agent_version": 2,
            "base_instructions": "the binary's own",
        },
        {"slug": "auto-review", "tool_mode": "code_mode_only", "display_name": "Review"},
    ]
}
SECRET = "sk-canary-of-the-key"


def _server(key=SECRET, limits=None, model="gw-gpt", name="Шлюз GPT"):
    return base.ServerEntry(
        "aaaa1111",
        "Шлюз",
        "http://gw:4000/v1",
        "http://gw:4000",
        "LADO_MODEL_KEY_AAAA1111" if key else "",
        key,
        ((model, name),),
        limits or {},
    )


@pytest.fixture
def catalogue(monkeypatch):
    """`codex debug models --bundled` as the installed Codex prints it; the argv it was asked."""
    asked = []

    def run_list(argv, env):
        asked.append((argv, env.get("CODEX_HOME")))
        return json.dumps(CATALOGUE)

    monkeypatch.setattr(base, "run_list", run_list)
    return asked


def _launch_on(cwd, server=None, environ=None):
    server = server or _server()
    agent = _agent(cwd)
    spec = providers.AgentSpec(
        ROLE,
        mcp={"lado": base.mcp_server(agent)},
        environ=dict(os.environ) if environ is None else environ,
        model=server.models[0][0],
        servers=(server,),
    )
    launch = providers.get("codex").launch_command(
        agent, state.Session("s", str(cwd), None, "codex"), spec
    )
    return launch, _config(launch)


def test_a_server_is_a_provider_of_the_agent_s_config_and_its_choice(repo, catalogue):
    _, config = _launch_on(repo)
    assert config["model_provider"] == "lado-aaaa1111"
    assert config["model"] == "gw-gpt"
    assert config["model_providers"]["lado-aaaa1111"] == {
        "name": "LADO · Шлюз",
        "base_url": "http://gw:4000/v1",
        "wire_api": "responses",
        "env_key": "LADO_MODEL_KEY_AAAA1111",
    }


def test_a_server_s_model_goes_on_the_command_line_over_the_repo_s(repo, catalogue, codex_home):
    _repo_model(repo)
    _user_config(codex_home, 'model = "gpt-5.6-sol"\n')
    launch, _ = _launch_on(repo)
    assert launch.argv == ["codex", "--no-daemon", "-m", "gw-gpt"]


def test_the_user_s_providers_stay_beside_the_server_s(repo, catalogue, codex_home):
    _user_config(codex_home, '[model_providers.mine]\nbase_url = "http://mine/v1"\n')
    _, config = _launch_on(repo)
    assert config["model_providers"]["mine"] == {"base_url": "http://mine/v1"}
    assert "lado-aaaa1111" in config["model_providers"]


def test_a_carried_profile_goes_to_the_server_too(repo, catalogue, codex_home):
    _user_config(
        codex_home,
        'profile = "work"\n'
        "[profiles.work]\n"
        'model = "own"\nmodel_provider = "mine"\nmodel_reasoning_effort = "high"\n'
        'web_search = "live"\n'
        "[profiles.other]\n"
        'model = "another"\n',
    )
    _, config = _launch_on(repo)
    assert config["profiles"]["work"] == {"model": "gw-gpt", "model_provider": "lado-aaaa1111"}
    assert config["profiles"]["other"] == {"model": "another"}
    assert codex._model_provider(config) == "lado-aaaa1111"


def test_a_server_with_no_key_has_no_env_key(repo, catalogue):
    launch, config = _launch_on(repo, _server(key=None))
    assert "env_key" not in config["model_providers"]["lado-aaaa1111"]
    assert not [name for name in launch.env if name.startswith(base.KEY_VARIABLE)]
    assert "" not in launch.env


def test_an_agent_on_a_server_needs_no_login(codex_home):
    cli = providers.get("codex")
    env = {"CODEX_HOME": str(codex_home)}
    assert cli.needs_login(env)
    assert not cli.needs_login({**env, base.MODEL_SERVER: "aaaa1111"})


def test_a_home_that_ran_on_a_built_in_model_loses_its_login_link(repo, catalogue, codex_home):
    built_in, _ = _launch(repo, model="gpt-5.5")
    _blocker(built_in, repo)
    home = Path(built_in.env["CODEX_HOME"])
    assert (home / "auth.json").is_symlink()
    launch, _ = _launch_on(repo)
    _blocker(launch, repo)
    assert not (home / "auth.json").is_symlink()


def test_a_home_back_on_a_built_in_model_has_nothing_of_the_server(repo, catalogue, codex_home):
    launch, _ = _launch_on(repo)
    home = Path(launch.env["CODEX_HOME"])
    assert (home / "models.json").exists()
    built_in, config = _launch(repo, model="gpt-5.5")
    assert not (home / "models.json").exists()
    assert "model_catalog_json" not in config and "web_search" not in config
    assert config.get("model_provider") is None
    assert "lado-aaaa1111" not in config.get("model_providers", {})
    assert set(built_in.env) == {"CODEX_HOME"}
    _blocker(built_in, repo)
    assert (home / "auth.json").is_symlink()


def test_web_search_and_a_carried_effort_stay_off(repo, catalogue, codex_home):
    _user_config(codex_home, 'model_reasoning_effort = "xhigh"\n')
    launch, config = _launch_on(repo)
    assert config["web_search"] == "disabled"
    assert "model_reasoning_effort" not in config
    assert launch.effort is None


def _catalogue_of(launch, config):
    assert config["model_catalog_json"] == str(Path(launch.env["CODEX_HOME"]) / "models.json")
    return json.loads(Path(config["model_catalog_json"]).read_text())["models"]


def test_the_agent_s_list_is_its_one_model_in_the_binary_s_format(repo, catalogue):
    launch, config = _launch_on(repo)
    [model] = _catalogue_of(launch, config)
    assert catalogue == [(["codex", "debug", "models", "--bundled"], launch.env["CODEX_HOME"])]
    assert (model["slug"], model["display_name"]) == ("gw-gpt", "Шлюз GPT")
    assert model["description"] == "On Шлюз"
    assert model["base_instructions"] == "the binary's own"
    assert model["shell_type"] == "unified_exec"


def test_the_agent_s_list_adds_no_tool_or_parameter_of_openai_s(repo, catalogue):
    launch, config = _launch_on(repo)
    [model] = _catalogue_of(launch, config)
    off = {
        "apply_patch_tool_type": None,
        "supports_search_tool": False,
        "experimental_supported_tools": [],
        "multi_agent_version": None,
        "supported_reasoning_levels": [],
        "default_reasoning_level": None,
        "supports_reasoning_effort_updates": False,
        "support_verbosity": False,
        "default_verbosity": None,
        "service_tiers": [],
        "additional_speed_tiers": [],
        "availability_nux": None,
        "upgrade": None,
        "input_modalities": ["text"],
    }
    assert {key: model[key] for key in off} == off


@pytest.mark.parametrize(
    "printed", ["not json", "[]", '{"models": 1}', '{"models": [{"tool_mode": "x"}]}']
)
def test_a_list_lado_cannot_use_leaves_codex_s_with_a_warning(repo, monkeypatch, printed):
    monkeypatch.setattr(base, "run_list", lambda argv, env: printed)
    launch, config = _launch_on(repo)
    assert "model_catalog_json" not in config
    assert not (Path(launch.env["CODEX_HOME"]) / "models.json").exists()
    [warning] = [w for w in launch.warnings if "/model" in w]
    assert "OpenAI's models, which its server does not have" in warning


def test_a_known_context_reaches_the_config_and_the_list(repo, catalogue):
    limits = {"gw-gpt": base.Limit(65536)}
    launch, config = _launch_on(repo, _server(limits=limits))
    assert config["model_context_window"] == 65536
    assert config["model_auto_compact_token_limit"] == 57344
    [model] = _catalogue_of(launch, config)
    assert (model["context_window"], model["max_context_window"]) == (65536, 65536)


# A failed turn, from the agent's journal.

JOURNAL = "sessions/2026/11/07/rollout-2026-11-07T17-16-38-a.jsonl"
UNAUTHORIZED = {
    "message": "unexpected status 401 Unauthorized: Missing Authentication header, "
    "url: https://user:pass@gw/v1/responses, cf-ray: 8f1-AMS",
    "codex_error_info": {"http_connection_failed": {"http_status_code": 401}},
}


def _line(kind, **payload):
    return json.dumps({"type": "event_msg", "payload": {"type": kind, **payload}}) + "\n"


def _write(agent, *lines, name=JOURNAL, binary=False):
    path = base.config_path(agent) / name
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("ab") as file:
        for line in lines:
            file.write(line if binary else line.encode())
    return path


def _failed(agent, keys=()):
    return providers.get("codex").failed_turn(agent, lambda: keys)


@pytest.fixture
def on_server(repo, catalogue):
    _launch_on(repo)
    return _agent(repo)


def _read(on_server, error, keys=()):
    _write(on_server, _line("task_started"), _line("task_complete", error=error))
    return _failed(on_server, keys)


def test_a_refused_key_ends_the_turn_in_lado_s_words(on_server):
    event = _read(on_server, UNAUTHORIZED)
    assert event == Event(
        base.TURN_END,
        error="the model provider refused the key (401): Missing Authentication header",
        details="Missing Authentication header",
        output_ignored=True,
    )


def test_a_limit_keeps_only_the_status(on_server):
    event = _read(
        on_server,
        {
            "message": "exceeded retry limit, last status: 429 Too Many Requests",
            "codex_error_info": {"response_too_many_failed_attempts": {"http_status_code": 429}},
        },
    )
    assert event.error == "the model provider limits requests, or the quota is spent (429)"
    assert event.details == "" and not event.transient


@pytest.mark.parametrize(
    ("body", "line"),
    [
        (
            '{"error": {"message": "unknown model"}}',
            "the model provider refused the request (400): unknown model",
        ),
        (
            '{"message":"invalid api key secret","code":"InvalidArgument"}',
            "the model provider refused the key (400): invalid api key secret",
        ),
        ('{"error": "plain words"}', "the model provider refused the request (400): plain words"),
    ],
    ids=["OpenAI's shape", "cloud.ru's key", "a string"],
)
def test_a_body_codex_passes_as_it_came_is_a_400(on_server, body, line):
    event = _read(on_server, {"message": body, "codex_error_info": "other"})
    assert event.error == line


def test_a_context_too_small_keeps_lado_s_words(on_server):
    body = json.dumps(
        {
            "error": {
                "type": "exceed_context_size_error",
                "message": "request (70000 tokens) exceeds the available context size (65536 "
                "tokens)",
            }
        }
    )
    event = _read(on_server, {"message": body, "codex_error_info": "other"})
    assert event.error == base.context_line(body)
    assert event.error.startswith(base.OVERFLOW)


def test_a_server_error_is_temporary(on_server):
    words = "We’re currently experiencing high demand, which may cause temporary errors."
    event = _read(on_server, {"message": words, "codex_error_info": "internal_server_error"})
    assert (event.error, event.transient) == (words, True)


@pytest.mark.parametrize(
    ("status", "reason"),
    [
        (502, "Bad Gateway"),
        (503, "Service Unavailable"),
        (504, "Gateway Timeout"),
        (529, "<unknown status code>"),
    ],
)
def test_any_5xx_codex_gives_up_on_is_temporary(on_server, status, reason):
    event = _read(
        on_server,
        {
            "message": f"unexpected status {status} {reason}: upstream, url: http://gw/v1",
            "codex_error_info": {"http_connection_failed": {"http_status_code": status}},
        },
    )
    assert event.transient
    assert event.error == f"unexpected status {status} {reason}: upstream"


def test_a_model_at_capacity_is_temporary(on_server):
    event = _read(
        on_server,
        {"message": "Selected model is at capacity", "codex_error_info": "server_overloaded"},
    )
    assert (event.error, event.transient) == ("Selected model is at capacity", True)


@pytest.mark.parametrize("body", ["Bad Request", "<html>nginx 400</html>", "[1,2]"])
def test_a_400_with_no_json_object_says_so_as_codex_gives_no_status(on_server, body):
    """`other` is Codex's word for more than a 400: LADO cannot claim a refusal here, and the
    server's text stays out of what `lado stats` takes for the error's kind."""
    event = _read(on_server, {"message": body, "codex_error_info": "other"})
    assert event.error == f"{codex.NO_WORDS}: {body}"
    assert (event.details, event.transient) == (body, False)
    assert event.error.split(":")[0] == codex.NO_WORDS


def test_no_error_is_no_failed_turn(on_server):
    _write(on_server, _line("task_started"), _line("task_complete", last_agent_message="done"))
    assert _failed(on_server) is None


def test_no_journal_is_no_failed_turn(on_server):
    assert _failed(on_server) is None


def test_a_later_turn_takes_the_error_back(on_server):
    _write(
        on_server,
        _line("task_started"),
        _line("task_complete", error=UNAUTHORIZED),
        _line("task_started"),
    )
    assert _failed(on_server) is None
    assert _failed(on_server) is None


def test_a_line_in_writing_waits_for_the_next_pass(on_server):
    line = _line("task_complete", error=UNAUTHORIZED)
    _write(on_server, line[:40])
    assert _failed(on_server) is None
    _write(on_server, line[40:])
    assert _failed(on_server).error.startswith("the model provider refused the key")


def test_an_error_is_told_once(on_server):
    assert _read(on_server, UNAUTHORIZED) is not None
    assert _failed(on_server) is None


def test_a_new_journal_is_read_from_its_start(on_server):
    _read(on_server, UNAUTHORIZED)
    later = JOURNAL.replace("17-16-38", "18-00-00")
    _write(on_server, _line("task_complete", error=UNAUTHORIZED), name=later)
    assert _failed(on_server) is not None


def test_a_line_that_is_no_json_is_passed_over(on_server):
    _write(on_server, "not json\n", '"text"\n', '{"payload": 1}\n')
    assert _read(on_server, UNAUTHORIZED) is not None


def test_a_key_that_cannot_be_read_leaves_the_error_unread(on_server):
    """The error waits for the next pass: it is not lost."""

    def fails():
        raise OSError("no key")

    _write(on_server, _line("task_complete", error=UNAUTHORIZED))
    with pytest.raises(OSError):
        providers.get("codex").failed_turn(on_server, fails)
    assert _failed(on_server) is not None


def test_a_built_in_agent_s_journal_is_never_opened(repo, monkeypatch):
    _launch(repo, model="gpt-5.5")
    agent = _agent(repo)
    path = _write(agent, _line("task_complete", error=UNAUTHORIZED))
    monkeypatch.setattr(codex, "_newest_journal", lambda home: pytest.fail("a journal was read"))
    assert _failed(agent) is None
    assert path.exists() and not (base.config_path(agent) / "journal-offset").exists()


def test_the_other_clis_end_no_turn_by_a_journal(repo):
    for name in ("claude", "kilo", "opencode"):
        assert providers.get(name).failed_turn(_agent(repo), lambda: ()) is None
