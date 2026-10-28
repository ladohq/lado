"""Claude Code as a LADO provider."""

import contextlib
import fcntl
import hashlib
import json
import os
import re
import shutil
import stat
import sys
import tempfile
from collections.abc import Callable, Iterator
from pathlib import Path

from lado import state
from lado.providers import base, gitpaths

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
TESTED_VERSION = "2.1.295"

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

# Claude Code's tools that change files, denied to a read-only agent (AgentSpec.read_only)
# the same way: a deny rule takes them out of its tool list, also with bypassPermissions,
# and out of its Task subagents' (checked by hand with 2.1.296 on haiku, `claude -p
# --permission-mode bypassPermissions`: neither the agent nor a general-purpose subagent
# has Write or Edit, and ToolSearch finds neither).
EDIT_TOOLS = ["Edit", "Write", "NotebookEdit"]

# How long Claude Code waits for a command hook that sets no `timeout`: 600 s (`lu`, read in
# the binary of 2.1.296). LADO sets one only for its turn-end hooks (_timeout).
HOOK_LIMIT = 600


def _timeout(event: str) -> int | None:
    """The `timeout` LADO writes for its hook of `event`; None for Claude Code's default."""
    return base.TURN_END_HOOK_TIMEOUT if EVENTS.get(event) == base.TURN_END else None


# Variables that log Claude Code in without the keychain: a token, an API key, or another
# API provider (all in the binary of 2.1.296).
LOGINS = (
    "CLAUDE_CODE_OAUTH_TOKEN",
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_AUTH_TOKEN",
    "CLAUDE_CODE_USE_BEDROCK",
    "CLAUDE_CODE_USE_VERTEX",
)


# An apiKeySource that is a variable (ANTHROPIC_API_KEY), not Claude Code's own login's key
# ("/login managed key") or its apiKeyHelper.
ENV_NAME = re.compile(r"[A-Z][A-Z0-9_]*")


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
        output_taken_when_printed=True,
        deny_edit_tools=True,
        needs_login=True,
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
        notice: str | None = None,
    ) -> base.Launch:
        if notice:
            raise ValueError(f"{self.title} takes no notice on its command line")
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
            if (timeout := _timeout(event)) is not None:
                command["timeout"] = timeout
            return [{"hooks": [command]}]

        settings = config_dir / "settings.json"
        config = {
            "hooks": {e: hook(e) for e in EVENTS},
            "permissions": {"deny": BUILT_IN_MESSAGING + (EDIT_TOOLS if spec.read_only else [])},
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
                base.TURN_END,
                error=error,
                transient=kind in TRANSIENT,
                output_ignored=True,
                background=_background(data),
            )
        neutral = EVENTS[native]
        if neutral in (base.WAITING, base.RESUMED):
            return base.Event(neutral, key=_request_key(data))
        if native == "Stop":
            return base.Event(
                neutral,
                continued=bool(data.get("stop_hook_active")),
                background=_background(data),
            )
        return base.Event(neutral, data.get("prompt", ""))

    def hook_limit(self, native: str) -> float | None:
        timeout = _timeout(native)
        return HOOK_LIMIT if timeout is None else timeout

    def continue_output(self, text: str) -> str | None:
        # Blocking the stop makes Claude Code continue with `reason` as its next input. It
        # runs no UserPromptSubmit for it; the Stop that ends the turn it went on to has
        # stop_hook_active true, also after several blocks in a row (checked by hand with
        # 2.1.291, `claude -p`). After CLAUDE_CODE_STOP_HOOK_BLOCK_CAP blocks in a row
        # (8 by default) it ends the turn without the text (read in the binary of 2.1.291):
        # sweep types it in then (lado.runtime._plan).
        return json.dumps({"decision": "block", "reason": text})

    login_variables = ("CLAUDE_CODE_OAUTH_TOKEN", "ANTHROPIC_API_KEY")

    def login_status(self, env: dict[str, str]) -> base.LoginStatus:
        # `claude auth status --json` (2.1.295, about 0.1 s): loggedIn, authMethod
        # (claude.ai, oauth_token, api_key, none), subscriptionType for claude.ai,
        # apiKeySource for a key, configDirectory; exit 1 when not logged in. It does not
        # check a token with the server: a made-up one is loggedIn.
        argv = [self.command, "auth", "status", "--json"]
        found = base.run_status(argv, env)
        if isinstance(found, str):
            return base.LoginStatus(base.UNKNOWN, problem=found)
        command = " ".join(argv)
        try:
            data = json.loads(found.stdout)
        except ValueError:
            data = None
        if not isinstance(data, dict) or not isinstance(data.get("loggedIn"), bool):
            if found.returncode not in (0, 1):
                why = base.error_line(f"exit status {found.returncode}", found.stderr)
                return base.LoginStatus(base.UNKNOWN, problem=f"`{command}` failed with {why}")
            return base.LoginStatus(base.UNKNOWN, problem=f"cannot read `{command}`'s output")
        if not data["loggedIn"]:
            return base.LoginStatus(base.NO)
        method, source = data.get("authMethod"), data.get("apiKeySource")
        credentials = (
            "the login keychain"
            if sys.platform == "darwin"
            else str(Path(str(data.get("configDirectory") or "")) / ".credentials.json")
        )
        if method == "claude.ai":
            plan = data.get("subscriptionType")
            words = f"Claude subscription ({plan.capitalize()})" if plan else "Claude subscription"
            return base.LoginStatus(base.YES, words, file=credentials)
        if method == "oauth_token":
            # CLAUDE_CODE_OAUTH_TOKEN, or ANTHROPIC_AUTH_TOKEN (also "oauth_token", 2.1.295).
            given = [n for n in ("CLAUDE_CODE_OAUTH_TOKEN", "ANTHROPIC_AUTH_TOKEN") if env.get(n)]
            return base.LoginStatus(base.YES, "token", variable=given[0] if given else "")
        if method == "api_key":
            if isinstance(source, str) and ENV_NAME.fullmatch(source):
                return base.LoginStatus(base.YES, "API key", variable=source)
            return base.LoginStatus(base.YES, "Anthropic Console", file=credentials)
        if method == "third_party":  # Bedrock, Vertex, ... by their CLAUDE_CODE_USE_* variable
            return base.LoginStatus(base.YES, str(data.get("apiProvider") or method).capitalize())
        return base.LoginStatus(base.YES, str(method))

    def login_actions(self) -> tuple[base.LoginAction, ...]:
        # Without a browser it prints `If the browser didn't open, visit: <url>` and `Paste
        # code here if prompted >`, and waits for the code (2.1.295).
        login = (self.command, "auth", "login")
        return (
            base.LoginAction("login", "Log in with your Claude account…", (*login, "--claudeai")),
            base.LoginAction(
                "login-console", "Log in with Anthropic Console…", (*login, "--console")
            ),
        )

    def logout_argv(self) -> list[str] | None:
        return [self.command, "auth", "logout"]

    def keychain_login(self, env: dict[str, str]) -> str | None:
        # On macOS Claude Code keeps its OAuth login in the login keychain ("Claude
        # Code-credentials"). It needs none with one of LOGINS. apiKeyHelper in its settings
        # is not read: missing it only warns, and only outside the graphical session.
        if sys.platform != "darwin" or any(env.get(name) for name in LOGINS):
            return None
        return ", or set `CLAUDE_CODE_OAUTH_TOKEN` (`claude setup-token`) in your login shell"

    def first_hook_blocker(self, cwd: str, env: dict[str, str]) -> base.Blocker:
        # Claude Code asks whether to trust a folder it does not trust before any hook runs,
        # and no flag, permission mode or setting skips the question; its default answer,
        # "No, exit", ends it. So LADO records the trust of the session's repository itself
        # in Claude Code's global config (see _trusted and _record_trust); the question in
        # Needs you is left for when it cannot.
        try:
            trusted = _trusted(Path(cwd), env)
        except (OSError, ValueError) as error:
            repo = gitpaths.main_root(Path(cwd))
            return base.Blocker(warning=f"cannot tell whether {self.title} trusts {repo}: {error}")
        notes: list[str] = []
        if not trusted:
            repo = gitpaths.main_root(Path(cwd))
            try:
                path = _record_trust(repo, env)
            except (OSError, ValueError) as error:
                return base.Blocker(
                    reason=f"{self.title} asks whether to trust {repo}: LADO could not record "
                    f'the trust ({error}); in its terminal choose "Yes, I trust this folder" '
                    '(Enter alone answers "No, exit" and closes the agent)'
                )
            if path is not None:  # else another LADO recorded it meanwhile
                notes.append(f"LADO recorded {self.title}'s trust in {repo} in {path}")
        # A logged-in Claude Code still shows its first-run screens before any hook: the
        # theme, then for a key in its environment whether to use it (default "No"). Not
        # while it is not logged in: those agents wait for a login (lado.login_wait), which
        # calls this again once there is one.
        if self.login_status(env).state != base.YES:
            return base.Blocker(notes=tuple(notes))
        try:
            if path := _record_first_run(env):
                notes.append(f"LADO recorded {self.title}'s first run in {path}")
            key = env.get("ANTHROPIC_API_KEY")
            if key:
                path, rejected = _approve_key(env, key)
                if rejected:
                    return base.Blocker(
                        reason=f"{self.title} asks whether to use ANTHROPIC_API_KEY, which you "
                        f"rejected before (in {rejected}): in its terminal choose to use it, or "
                        "remove the key from customApiKeyResponses.rejected there",
                        notes=tuple(notes),
                    )
                if path:
                    notes.append(f"LADO recorded the approval of ANTHROPIC_API_KEY in {path}")
        except (OSError, ValueError) as error:
            return base.Blocker(
                warning=f"cannot record {self.title}'s first run: {error}", notes=tuple(notes)
            )
        return base.Blocker(notes=tuple(notes))


# Background work after a turn's end. Seen live with 2.1.295 (haiku): every Stop payload has
# `background_tasks`, the session's background tasks, the ones its subagents started too,
# e.g. {"id", "type": "subagent", "status": "running", "description", "agent_type"} and
# {"id", "type": "shell", "status": "running", "description", "command"}; only `running`
# was seen, `pending` was read in the binary only. Each result wakes the agent with a new
# turn, whose Stop lists fewer. The list can be stale: a task killed in /tasks stays
# `running`, with no hook after it, until the next turn's end. SubagentStop is not used: it
# carries the same session-wide list and fires for Claude Code's own side agents too
# (agent_type "").
BACKGROUND_RUNNING = ("running", "pending")


def _background(data: dict) -> bool:
    tasks = data.get("background_tasks") or []
    return any(isinstance(t, dict) and t.get("status") in BACKGROUND_RUNNING for t in tasks)


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
#
# LADO writes that flag for the session's repository (_record_trust), the one exception to
# "Never touch the user's global agent config" (AGENTS.md, LAD-106): there is no other way
# to start Claude Code in a new folder without a human at its terminal. Checked by hand
# with 2.1.295: the entry of the repository's main root covers its linked worktrees;
# hasTrustDialogAccepted alone lets the repository's own hooks run
# (hasTrustDialogHooksAccepted is not needed); an entry written into the file by another
# process (temporary file and rename) while Claude Code ran survived Claude Code's own
# rewrite of the file at its exit, as it watches the file and re-reads it. A missing
# config is made with the entry alone: Claude Code adds the rest at its start.
def _config_path(env: dict[str, str]) -> Path:
    """The global config Claude Code, started with `env`, reads its trust from."""
    home = Path(env.get("HOME") or Path.home())
    config_dir = env.get("CLAUDE_CONFIG_DIR")
    path = Path(config_dir or home / ".claude") / ".config.json"
    if not path.exists():
        path = Path(config_dir or home) / ".claude.json"
    return path


@contextlib.contextmanager
def _config_lock() -> Iterator[None]:
    """LADO's own changes of Claude Code's config one at a time (two agents started at once
    would lose each other's change). Claude Code's own lock is an internal detail of its
    binary, not used."""
    with open(state.home() / "claude-config.lock", "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield


def edit_config(env: dict[str, str], change: Callable[[dict], bool]) -> Path | None:
    """Change Claude Code's global config, the one it reads with `env`, by `change`, which
    gets the config, read again now, and returns whether it changed it; the file written, or
    None when nothing changed (nothing is written then). Every key `change` leaves is kept.
    The file is written as Claude Code writes it (JSON, indent 2) to a temporary file in its
    folder, then put in its place in one step, with the old file's mode (a new one 600: it
    holds the login); a symlinked config is written through to its target. ValueError,
    naming the file, for a file that is not a JSON object, or that `change` refuses: the
    file is left as it is; OSError for a file that cannot be read or written."""
    with _config_lock():
        path = _config_path(env)
        target = path.resolve()
        try:
            text = target.read_text()
        except FileNotFoundError:
            config: object = {}
            mode = 0o600
        except UnicodeDecodeError as error:
            raise ValueError(f"{path}: {error}") from error
        else:
            try:
                config = json.loads(text)
            except ValueError as error:
                raise ValueError(f"{path}: {error}") from error
            mode = stat.S_IMODE(target.stat().st_mode)
        if not isinstance(config, dict):
            raise ValueError(f"{path} is not a JSON object")
        try:
            if not change(config):
                return None
        except ValueError as error:
            raise ValueError(f"{path}: {error}") from error
        fd, temp = tempfile.mkstemp(prefix=f"{target.name}.", suffix=".tmp", dir=target.parent)
        try:
            with os.fdopen(fd, "w") as file:
                json.dump(config, file, indent=2, ensure_ascii=False)
                file.flush()
                os.fsync(file.fileno())
            os.chmod(temp, mode)
            os.replace(temp, target)
        except BaseException:
            Path(temp).unlink(missing_ok=True)
            raise
        return path


def _record_trust(repo: Path, env: dict[str, str]) -> Path | None:
    """Set hasTrustDialogAccepted in the entry of `repo`, a real path, in Claude Code's
    config (edit_config), keeping the entry's other keys; the file written, or None when it
    trusted `repo` already. ValueError for projects or an entry that is not an object."""

    def trust(config: dict) -> bool:
        projects = config.setdefault("projects", {})
        if not isinstance(projects, dict):
            raise ValueError("its projects are not a JSON object")
        entry = projects.setdefault(str(repo), {})
        if not isinstance(entry, dict):
            raise ValueError(f"the entry of {repo} in its projects is not a JSON object")
        if entry.get("hasTrustDialogAccepted") is True:
            return False
        entry["hasTrustDialogAccepted"] = True
        return True

    return edit_config(env, trust)


# Claude Code's first-run keys, LADO's other exception to the same rule (AGENTS.md,
# LAD-157), written the same way, only for an agent whose environment logs it in (checked
# by hand with 2.1.295): with hasCompletedOnboarding true it starts straight away with a
# token; with ANTHROPIC_API_KEY it asks "Detected a custom API key in your environment… Do
# you want to use this API key?" until the key's last 20 characters are in
# customApiKeyResponses.approved, as Claude Code itself stores the answer there. The key
# itself goes nowhere else.
KEY_TAIL = 20


def _record_first_run(env: dict[str, str]) -> Path | None:
    """Set hasCompletedOnboarding (edit_config); the file written, or None when it was set."""

    def onboard(config: dict) -> bool:
        if config.get("hasCompletedOnboarding") is True:
            return False
        config["hasCompletedOnboarding"] = True
        return True

    return edit_config(env, onboard)


def _approve_key(env: dict[str, str], key: str) -> tuple[Path | None, Path | None]:
    """Add the key's last characters to customApiKeyResponses.approved (edit_config) when
    they are in neither list: (the file written, None); (None, the config) when the human
    rejected them, which is left as it is; (None, None) when they were approved. ValueError
    for responses or a list that is not what Claude Code writes."""
    tail = key[-KEY_TAIL:]
    rejected = False

    def approve(config: dict) -> bool:
        nonlocal rejected
        responses = config.setdefault("customApiKeyResponses", {})
        if not isinstance(responses, dict):
            raise ValueError("its customApiKeyResponses are not a JSON object")
        approved = responses.setdefault("approved", [])
        refused = responses.get("rejected", [])
        if not isinstance(approved, list) or not isinstance(refused, list):
            raise ValueError("its customApiKeyResponses are not lists")
        if tail in refused:
            rejected = True
            return False
        if tail in approved:
            return False
        approved.append(tail)
        return True

    path = edit_config(env, approve)
    return path, (_config_path(env) if rejected else None)


def _trusted(cwd: Path, env: dict[str, str]) -> bool:
    """Whether Claude Code, started in `cwd` with `env`, trusts the folder. Reads only the
    config's projects; ValueError, naming the file, when it cannot be read. No config:
    none."""
    path = _config_path(env)
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

    if trusts(gitpaths.main_root(cwd)):
        return True
    root, folder = gitpaths.git_root(cwd), cwd.resolve()
    while True:
        if trusts(folder):
            return True
        if folder == root or folder == folder.parent:
            return False
        folder = folder.parent
