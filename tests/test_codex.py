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
    _, config = _launch(repo)
    assert config["check_for_update_on_startup"] is False
    assert config["features"]["multi_agent"] is False
    assert config["analytics"] == {"enabled": False}
    assert config["feedback"] == {"enabled": False}


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
    assert config["mcp_servers"]["db"] == {
        "command": "db-server",
        "args": ["--port", "1"],
        "env": {"T": "x"},
        "env_vars": ["TOKEN"],
    }


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
        ("Stop", {"stop_hook_active": True}, Event(providers.TURN_END, continued=True)),
        # Esc, or a refused approval: the turn ends, and Codex ignores the hook's output.
        ("Interrupt", {}, Event(providers.TURN_END, output_ignored=True)),
        ("SessionEnd", {"reason": "other"}, None),
        ("PreToolUse", {"tool_name": "Bash"}, None),
    ],
)
def test_codex_maps_native_events(native, payload, expected):
    assert providers.get("codex").parse_event(native, json.dumps(payload)) == expected


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
    hooks.handle(providers.get("codex"), Event(providers.SESSION_START), "s", "supervisor")
    hooks.handle(
        providers.get("codex"), Event(providers.PROMPT_SUBMIT, argv[-1]), "s", "supervisor"
    )
    assert state.list_messages("s")[0].state == state.DELIVERED


# Codex's own rule (0.162.0, checked by hand): the agent's folder, its project root (the
# nearest folder up with .git), then its repository's main root; the first entry with a
# trust level decides, trusted or not. Nothing above the git root counts.


def test_codex_trusts_the_repo_the_user_trusts(repo, codex_home):
    _trust(codex_home, repo.resolve())
    launch, config = _launch(repo)
    assert config["projects"] == {str(repo.resolve()): {"trust_level": "trusted"}}
    assert _blocker(launch, repo) == base.Blocker()


def test_codex_asks_about_a_repo_the_user_does_not_trust(repo, codex_home):
    launch, config = _launch(repo)
    assert "projects" not in config
    blocker = _blocker(launch, repo)
    assert blocker.reason.startswith(f"Codex CLI asks whether to trust {repo.resolve()}")
    assert "Trust and continue" in blocker.reason


def test_trust_above_the_git_root_does_not_cover_it(repo, codex_home):
    _trust(codex_home, repo.parent.resolve())
    launch, config = _launch(repo)
    assert "projects" not in config
    assert _blocker(launch, repo).reason


def test_a_subfolder_is_trusted_by_its_repo(repo, codex_home):
    (repo / "sub").mkdir()
    _trust(codex_home, repo.resolve())
    launch, _ = _launch(repo / "sub")
    assert _blocker(launch, repo / "sub") == base.Blocker()


def test_a_worktree_is_trusted_by_its_main_repo(repo, codex_home):
    _trust(codex_home, repo.resolve())
    worktree = _worktree(repo)
    launch, config = _launch(worktree)
    assert config["projects"] == {str(repo.resolve()): {"trust_level": "trusted"}}
    assert _blocker(launch, worktree) == base.Blocker()


def test_a_subfolder_of_a_worktree_is_trusted_by_the_worktree(repo, codex_home):
    worktree = _worktree(repo)
    (worktree / "sub").mkdir()
    _trust(codex_home, worktree.resolve())
    launch, config = _launch(worktree / "sub")
    assert config["projects"] == {str(worktree.resolve()): {"trust_level": "trusted"}}
    assert _blocker(launch, worktree / "sub") == base.Blocker()


def test_a_folder_is_trusted_by_its_real_path(repo, codex_home, tmp_path):
    link = tmp_path / "link"
    link.symlink_to(repo)
    _trust(codex_home, repo.resolve())
    launch, _ = _launch(link)
    assert _blocker(launch, link) == base.Blocker()


def test_an_untrusted_repo_is_carried_and_asks_nothing(repo, codex_home):
    _trust(codex_home, repo.resolve(), level="untrusted")
    launch, config = _launch(repo)
    assert config["projects"] == {str(repo.resolve()): {"trust_level": "untrusted"}}
    assert _blocker(launch, repo) == base.Blocker()


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


def test_the_repo_s_own_hooks_asked_about_are_named(repo, codex_home):
    _repo_hooks(repo)
    _trust(codex_home, repo.resolve())
    launch, _ = _launch(repo)
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
    assert _blocker(launch, repo) == base.Blocker()


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
    assert _blocker(launch, worktree) == base.Blocker()


def test_hooks_in_the_repo_s_codex_config_count_too(repo, codex_home):
    (repo / ".codex").mkdir()
    (repo / ".codex" / "config.toml").write_text(
        '[[hooks.Stop]]\n[[hooks.Stop.hooks]]\ntype = "command"\ncommand = "repo-hook"\n'
    )
    _trust(codex_home, repo.resolve())
    launch, _ = _launch(repo)
    assert str(repo.resolve() / ".codex" / "config.toml") in _blocker(launch, repo).reason


def test_an_untrusted_repo_s_hooks_do_not_load(repo, codex_home):
    _repo_hooks(repo)
    _trust(codex_home, repo.resolve(), level="untrusted")
    launch, _ = _launch(repo)
    assert _blocker(launch, repo) == base.Blocker()


def test_a_repo_codex_will_ask_about_names_its_hooks_too(repo, codex_home):
    _repo_hooks(repo)
    launch, _ = _launch(repo)
    reason = _blocker(launch, repo).reason
    assert "whether to trust" in reason and "hooks.json" in reason
