"""Claude Code as a LADO provider."""

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

from lado import state
from lado.providers import base

# `lado doctor` warns when the installed Claude Code is not this version, the one
# `make test-live PROVIDER=claude` last passed on. Checked with 2.1.287 (and 2.1.286) by
# hand: a server with alwaysLoad in --mcp-config has its tools loaded up front when it is
# connected before the first turn; one that connects later has its tools
# deferred behind ToolSearch all the same. The interactive first turn does not wait for
# MCP servers (CLAUDE_CODE_MCP_STARTUP_WAIT_MS, MCP_CONNECTION_NONBLOCKING=false and
# CLAUDE_CODE_MCP_PREWAIT_SERVERS change nothing there), but it does wait for the
# SessionStart hooks. So LADO's SessionStart hook waits for LADO's MCP server
# (hold_first_turn, lado.hooks). The live test checks this in w1's transcript.
# AgentSpec.read (the lead's lead-files, lado.runtime) checked by hand with 2.1.289 in mode
# default (`claude -p`): a SKILL.md folder in an --add-dir directory without .claude/skills
# is not listed as a skill, and the Read tool reads it with no permission denial.
TESTED_VERSION = "2.1.289"

# Claude Code hook events and the neutral events they stand for.
#
# A dialog for the human: PermissionRequest runs just before Claude Code shows one, also
# for an AskUserQuestion question (with bypassPermissions only for that) and never for a
# call that dontAsk refuses; Elicitation before an MCP server's form. Checked in the modes
# default, bypassPermissions and dontAsk; not in auto (Claude Code offers it to no Haiku,
# BACKLOG.md): if its classifier refuses a call after PermissionRequest, no hook ends the
# wait before the turn's end. Their answer: the tool call's PostToolUse or PostToolUseFailure, or
# ElicitationResult. The pair has the same key (_request_key), so a subagent's tool or the
# next tool after a refusal does not end the wait. When the human refuses a permission or
# dismisses a question, no hook runs at all: the agent stays waiting until the human types
# (BACKLOG.md); when the human refuses with a comment, until its turn ends. Notification
# says the same as these, about 6 s later, so it is not used. Checked by hand with Claude
# Code 2.1.289.
#
# StopFailure runs instead of Stop when an API error ended the turn (rate_limit, overloaded,
# authentication_failed, billing_error, server_error, also for "your computer went to
# sleep", max_output_tokens, unknown, ...), with `error` and `error_details`; Claude Code
# ignores its output and exit code (read in the binary of 2.1.291, not triggered by hand).
# Of these types, the ones that pass by themselves, so LADO resumes the agent after a while
# (Event.transient): an overloaded or failing API, and unknown, which the machine's sleep
# is too. The others need someone to act and go to the lead at once.
TRANSIENT = frozenset({"overloaded", "server_error", "unknown"})
EVENTS = {
    "SessionStart": base.SESSION_START,
    "UserPromptSubmit": base.PROMPT_SUBMIT,
    "Stop": base.TURN_END,
    "StopFailure": base.TURN_END,
    "SessionEnd": base.SESSION_END,
    "PermissionRequest": base.WAITING,
    "Elicitation": base.WAITING,
    "PostToolUse": base.RESUMED,
    "PostToolUseFailure": base.RESUMED,
    "ElicitationResult": base.RESUMED,
}
# Hooks that run without holding Claude Code up: one runs after every tool call.
ASYNC = ("PostToolUse", "PostToolUseFailure", "ElicitationResult")

# /clear and /resume end Claude Code's session (SessionEnd with this reason) and start
# another one in the same process (SessionStart with it as source); /exit ends it with
# "prompt_input_exit". Checked with Claude Code 2.1.287. /resume opens its picker without a
# hook and Esc cancels it without one; both events come only once a conversation is chosen.
SWITCHES = ("clear", "resume")

# Claude Code's own tools for messaging and listing agents (its subagents, teammates and
# other local sessions). An agent that picks them instead of LADO's send_message and
# list_agents talks to nobody, so they are denied. A deny rule removes them from the
# agent's tool list, also with --permission-mode bypassPermissions (checked with 2.1.286).
BUILT_IN_MESSAGING = ["SendMessage", "ListAgents"]


class ClaudeProvider(base.Provider):
    name = "claude"
    title = "Claude Code"
    command = "claude"
    install_hint = "install it: https://docs.anthropic.com/en/docs/claude-code"
    tested_version = TESTED_VERSION
    capabilities = base.Capabilities(
        status_events=True,
        permission_event=True,
        deliver_on_turn_end=True,
        skills=True,
        hold_first_turn=True,
    )
    # Passed on as --permission-mode: the choices of Claude Code 2.1.287, which also takes
    # "default" without listing it.
    permission_modes = (
        "default",
        "acceptEdits",
        "auto",
        "bypassPermissions",
        "manual",
        "dontAsk",
        "plan",
    )

    def launch_command(
        self,
        agent: state.Agent,
        session: state.Session,
        spec: base.AgentSpec,
    ) -> base.Launch:
        config_dir = base.config_dir(agent)

        mcp_config = config_dir / "mcp.json"
        # A stdio server gets Claude Code's whole environment, the agent's, also names the
        # config does not list, AWS_SECRET_ACCESS_KEY included: a kit's secrets reach it
        # through lado.mcp_exec, never through this file. Claude Code expands ${VAR} in
        # the args of a --mcp-config file, so the wrapper's args hold none (both checked by
        # hand with 2.1.291, `claude -p --mcp-config`).
        servers = {
            name: {"command": s.command[0], "args": s.command[1:], "env": s.env}
            for name, s in spec.mcp.items()
        }
        # Claude Code defers MCP tools behind its ToolSearch tool; a weak model then may not
        # find send_message and never report. alwaysLoad puts LADO's tools in the prompt,
        # if the server is connected before the first turn (see TESTED_VERSION).
        if "lado" in servers:
            servers["lado"]["alwaysLoad"] = True
        mcp_config.write_text(json.dumps({"mcpServers": servers}, indent=2))

        def hook(event: str) -> list[dict]:
            command: dict = {"type": "command", "command": base.hook_command(agent, event)}
            if event in ASYNC:
                command["async"] = True
            return [{"hooks": [command]}]

        settings = config_dir / "settings.json"
        config = {
            "hooks": {e: hook(e) for e in EVENTS},
            "permissions": {"deny": BUILT_IN_MESSAGING},
        }
        settings.write_text(json.dumps(config, indent=2))

        # From a file, so the role is not on the command line (checked by hand with 2.1.294
        # in an interactive session).
        prompt = config_dir / "prompt.md"
        prompt.write_text(spec.prompt)

        cmd = [
            self.command,
            "--mcp-config",
            str(mcp_config),
            "--settings",
            str(settings),
            "--append-system-prompt-file",
            str(prompt),
        ]
        # Claude Code loads the skills in <dir>/.claude/skills of every --add-dir directory
        # (checked with Claude Code 2.1.286; symlinked skill folders work, and their scripts
        # run from there). Nothing is written into the worktree or ~/.claude.
        skills_root = config_dir / "skills"
        if spec.skills:
            base.link_skills(skills_root / ".claude" / "skills", spec.skills)
            cmd += ["--add-dir", str(skills_root)]
        elif skills_root.exists():
            shutil.rmtree(skills_root)
        # Files in an --add-dir directory are read without asking; with no .claude/skills
        # in it, nothing there is loaded as a skill.
        for folder in spec.read:
            cmd += ["--add-dir", str(folder)]
        if session.permission_mode:
            cmd += ["--permission-mode", session.permission_mode]
        return base.Launch(cmd)

    def parse_event(self, native: str, payload: str) -> base.Event | None:
        if native not in EVENTS:
            return None
        data = json.loads(payload) if payload.strip() else {}
        if native == "SessionEnd" and data.get("reason") in SWITCHES:
            return base.Event(base.CONVERSATION_END)
        if native == "SessionStart" and data.get("source") in SWITCHES:
            return base.Event(base.CONVERSATION_START)
        if native == "StopFailure":
            kind = data.get("error") or "unknown"
            error = base.error_line(kind, data.get("error_details", ""))
            return base.Event(
                base.TURN_END, error=error, transient=kind in TRANSIENT, output_ignored=True
            )
        neutral = EVENTS[native]
        if neutral in (base.WAITING, base.RESUMED):
            return base.Event(neutral, key=_request_key(data))
        if native == "Stop":
            return base.Event(neutral, continued=bool(data.get("stop_hook_active")))
        return base.Event(neutral, data.get("prompt", ""))

    def continue_output(self, text: str) -> str | None:
        # Blocking the stop makes Claude Code continue with `reason` as its next input. It
        # runs no UserPromptSubmit for it; the Stop that ends the turn it went on to has
        # stop_hook_active true, also after several blocks in a row (checked by hand with
        # 2.1.291, `claude -p`). After CLAUDE_CODE_STOP_HOOK_BLOCK_CAP blocks in a row
        # (8 by default) it ends the turn without the text (read in the binary of 2.1.291):
        # sweep types it in then (lado.runtime._plan).
        return json.dumps({"decision": "block", "reason": text})

    def first_hook_blocker(self, cwd: str, env: dict[str, str]) -> base.Blocker:
        # Claude Code asks whether to trust a folder it does not trust before any hook runs,
        # and no flag, permission mode or setting skips the question; its default answer,
        # "No, exit", ends it. LADO only reads whether it trusts the folder: recording the
        # trust is the human's, in Claude Code's global config (see _trusted).
        try:
            trusted = _trusted(Path(cwd), env)
        except (OSError, ValueError) as error:
            repo = _main_root(Path(cwd))
            return base.Blocker(warning=f"cannot tell whether {self.title} trusts {repo}: {error}")
        if trusted:
            return base.Blocker()
        return base.Blocker(
            reason=f"{self.title} asks whether to trust {_main_root(Path(cwd))}: in its "
            'terminal choose "Yes, I trust this folder" (Enter alone answers "No, exit" and '
            "closes the agent)"
        )


def _request_key(data: dict) -> str:
    """The key of the dialog a hook is about: the tool call (its tool and input), or the MCP
    server whose form it is. PermissionRequest has no tool_use_id (2.1.289), but the input
    it shows is the one the tool's PostToolUse gets; an AskUserQuestion's answer adds its
    answers to it, so only the questions count."""
    if "mcp_server_name" in data and "tool_name" not in data:
        about = ["elicitation", data["mcp_server_name"]]
    else:
        tool_input = data.get("tool_input") or {}
        if data.get("tool_name") == "AskUserQuestion":
            tool_input = {"questions": tool_input.get("questions")}
        about = ["tool", data.get("tool_name", ""), tool_input]
    return hashlib.sha256(json.dumps(about, sort_keys=True).encode()).hexdigest()[:16]


# Where Claude Code 2.1.291 keeps whether it trusts a folder (read in its binary, not
# triggered by hand): projects[<folder>].hasTrustDialogAccepted in its global config,
# <config home>/.config.json of older versions if that exists, else .claude.json in
# $CLAUDE_CONFIG_DIR or the home folder; the config home is $CLAUDE_CONFIG_DIR or
# ~/.claude. A folder is trusted by its git repository's main root (the main repo of a
# worktree), or by itself or a folder above it up to its git root, each by its real path.
def _trusted(cwd: Path, env: dict[str, str]) -> bool:
    """Whether Claude Code, started in `cwd` with `env`, trusts the folder. Reads only the
    config's projects; ValueError, naming the file, when it cannot be read. No config:
    none."""
    home = Path(env.get("HOME") or Path.home())
    config_dir = env.get("CLAUDE_CONFIG_DIR")
    path = Path(config_dir or home / ".claude") / ".config.json"
    if not path.exists():
        path = Path(config_dir or home) / ".claude.json"
    try:
        config = json.loads(path.read_text())
    except FileNotFoundError:
        return False
    except (OSError, ValueError) as error:
        raise ValueError(f"{path}: {error}") from error
    if not isinstance(config, dict):
        raise ValueError(f"{path} is not a JSON object")
    projects = config.get("projects", {})
    if not isinstance(projects, dict):
        raise ValueError(f"{path}: its projects are not a JSON object")

    def trusts(folder: Path) -> bool:
        project = projects.get(str(folder))
        return isinstance(project, dict) and project.get("hasTrustDialogAccepted") is True

    if trusts(_main_root(cwd)):
        return True
    root, folder = _git_root(cwd), cwd.resolve()
    while True:
        if trusts(folder):
            return True
        if folder == root or folder == folder.parent:
            return False
        folder = folder.parent


def _git(cwd: Path, *args: str) -> str | None:
    done = subprocess.run(
        ["git", "-C", str(cwd), "rev-parse", "--path-format=absolute", *args],
        capture_output=True,
        text=True,
        check=False,
    )
    return done.stdout.strip() if done.returncode == 0 else None


def _git_root(cwd: Path) -> Path:
    """The real path of `cwd`'s git work tree, or of the root folder outside git."""
    top = _git(cwd, "--show-toplevel")
    return Path(top).resolve() if top else Path(cwd.resolve().anchor)


def _main_root(cwd: Path) -> Path:
    """The real path of the main work tree of `cwd`'s repository (the main repo of a linked
    worktree); `cwd` itself outside git."""
    common = _git(cwd, "--git-common-dir")
    return Path(common).resolve().parent if common else cwd.resolve()
