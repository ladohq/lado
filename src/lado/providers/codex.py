"""Codex CLI as a LADO provider.

Codex keeps everything it reads and writes in one home, CODEX_HOME: config.toml, its
sessions and state databases, its skills. The only file key that adds a role and keeps
Codex's base prompt is `developer_instructions` in config.toml (`model_instructions_file`
replaces the base prompt), and Codex writes into config.toml itself (trust, TUI state). So
each agent gets a home of its own, its config folder, with a config.toml LADO writes anew
at each launch, and what of the user's own Codex config the agent needs is read, never
written (`CARRIED`, the trust of the folder and of the repository's own hooks).

Checked by hand with Codex CLI 0.162.0 on a local model (Ollama, qwen3-coder:30b), in
throwaway homes; where Codex's open source was read for a behaviour, the comment says so.
"""

import hashlib
import json
import math
import os
import re
import sys
from pathlib import Path

from lado import state
from lado.providers import base, gitpaths

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

# `lado doctor` warns when the installed Codex CLI is not this version.
TESTED_VERSION = "0.162"

# Codex hook events and the neutral events they stand for (0.162.0, checked by hand).
#
# SessionStart runs only when the first input is submitted, just before its
# UserPromptSubmit, not when the TUI starts (session_start_on_first_input). /new does not
# run it at the command; the next prompt does, with source "clear", /resume's next prompt
# with source "resume": a session start only makes a starting or held agent ready
# (lado.hooks), so these change nothing.
#
# SessionEnd is not used: after /resume, Codex runs it for the conversation it left (reason
# "other", the only reason it gives) once the next one has started, which would end a
# running agent. An agent whose Codex exits is ended by the session loop's window check
# (lado.runtime.check_windows), also when `required` lado MCP server fails at the start:
# Codex then exits with "required MCP servers failed to initialize".
#
# A turn ends with Stop; a turn the human interrupts (Esc), or whose approval the human
# refuses, ends with Interrupt and no Stop. Codex reads Interrupt's output only for a
# message to the human (read in its source, hooks/src/events/interrupt.rs): the queue is
# typed in after it (output_ignored). A turn that ends on a model or API error runs no hook
# at all (BACKLOG.md): the agent stays busy.
#
# No turn's end is Event.background: Stop's input (session, turn, transcript, cwd, model,
# permission mode, stop_hook_active, last_assistant_message) says nothing of work still
# running, though Codex can move a shell command to a background terminal; its own
# subagents are off (BACKLOG.md).
#
# PermissionRequest runs just before an approval dialog (a shell command that asks to leave
# the sandbox, an MCP tool call); its tool call's PostToolUse is the answer. It has no
# tool_use_id: the key is the tool and its input, which PostToolUse gets the same. A
# cancelled MCP call runs no PostToolUse: the wait ends with the turn's Stop.
EVENTS = {
    "SessionStart": base.SESSION_START,
    "UserPromptSubmit": base.PROMPT_SUBMIT,
    "Stop": base.TURN_END,
    "Interrupt": base.TURN_END,
    "PermissionRequest": base.WAITING,
    "PostToolUse": base.RESUMED,
}
# Codex gives Interrupt's hook 1 s by default, at most 3 s; it hands the queue over.
HOOK_TIMEOUTS = {"Interrupt": 3}

# How Codex names each hook event in a hook's trust key and hash (its hook_event_key_label).
LABELS = {
    "PreToolUse": "pre_tool_use",
    "PermissionRequest": "permission_request",
    "PostToolUse": "post_tool_use",
    "PreCompact": "pre_compact",
    "PostCompact": "post_compact",
    "SessionStart": "session_start",
    "SessionEnd": "session_end",
    "UserPromptSubmit": "user_prompt_submit",
    "SubagentStart": "subagent_start",
    "SubagentStop": "subagent_stop",
    "Stop": "stop",
    "Interrupt": "interrupt",
}
UNMATCHED = ("UserPromptSubmit", "Stop", "Interrupt")  # a group's matcher is ignored
SHORT = ("SessionEnd", "Interrupt")  # timeout 1 s by default, at most 3 s
CONTEXT_EVENTS = ("PreToolUse", "PostToolUse", "SessionStart", "UserPromptSubmit", "SubagentStart")
DEFAULT_CONTEXT_LIMIT = 2500

# The user's settings an agent needs to reach its model, carried as they are.
CARRIED = (
    "model",
    "model_provider",
    "model_providers",
    "oss_provider",
    "profile",
    "profiles",
    "model_reasoning_effort",
)
PROFILE = "lado"  # LADO's permission profile (see _git_profile)


class CodexProvider(base.Provider):
    name = "codex"
    title = "Codex CLI"
    command = "codex"
    install_hint = "install it: `npm install -g @openai/codex`"
    tested_version = TESTED_VERSION
    # Text typed in right after the start: not checked, so the first lines go on the command
    # line as Codex's own [PROMPT], submitted once the TUI is ready (after any dialog).
    capabilities = base.Capabilities(
        status_events=True,
        permission_event=True,
        deliver_on_turn_end=True,
        skills=True,
        notice_on_argv=True,
        session_start_on_first_input=True,
    )
    # No mode: Codex's own approvals (on-request in a trusted folder) and LADO's permission
    # profile. `default` asks for approvals as Codex's on-request does.
    permission_modes = ("default", "bypassPermissions")

    def launch_command(
        self,
        agent: state.Agent,
        session: state.Session,
        spec: base.AgentSpec,
        notice: str | None = None,
    ) -> base.Launch:
        home = base.config_dir(agent)
        cwd = Path(agent.cwd)
        warnings: list[str] = []
        user, user_path = _user_config(spec.environ or os.environ, warnings)
        dropped: list[str] = []
        config = {}
        for key in CARRIED:
            if key in user and (value := _keep(user[key], key, dropped)) is not None:
                config[key] = value
        config.update(
            developer_instructions=spec.prompt,
            check_for_update_on_startup=False,
            # Codex's own subagents: an agent that starts them talks to nobody. Its shell
            # snapshot writes the agent's whole environment, a kit's MCP secrets too, into
            # shell_snapshots/ of its home: no such value may go on disk (lado.mcp_exec).
            features={"multi_agent": False, "shell_snapshot": False},
            analytics={"enabled": False},
            feedback={"enabled": False},
        )
        if trust := _trust_entry(user.get("projects"), cwd):
            config["projects"] = {trust[0]: {"trust_level": trust[1]}}
        config["hooks"] = _hooks(agent, home)
        user_trust = (user.get("hooks") or {}).get("state") or {}
        for path in _repo_hook_files(cwd, home):
            for key, entry in user_trust.items():
                kept = _keep(entry, key, dropped) if key.startswith(f"{path}:") else None
                if kept is not None:
                    config["hooks"]["state"][key] = kept
        if dropped:
            warnings.append(
                f"cannot write {', '.join(dropped)} of {user_path} into the config of Codex "
                f"agent {agent.name}: left out"
            )
        # The variables Codex's own environment has, as the agent's window gets them.
        environ = [*(spec.environ or os.environ), *base.agent_env(agent), "CODEX_HOME"]
        config["mcp_servers"] = _mcp_servers(spec.mcp, environ)
        if session.permission_mode != "bypassPermissions" and (profile := _git_profile(cwd)):
            config["default_permissions"] = PROFILE
            config["permissions"] = {PROFILE: profile}
        # Codex loads SKILL.md folders from $CODEX_HOME/skills, links followed. It also
        # reads the user's $HOME/.agents/skills, whatever CODEX_HOME is (BACKLOG.md).
        base.link_skills(home / "skills", spec.skills)
        # The carried settings may hold credentials (model_providers): only the user reads it.
        fd = os.open(home / "config.toml", os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        os.fchmod(fd, 0o600)  # the mode above is only for a new file
        with os.fdopen(fd, "w") as file:
            file.write(toml_text(config))
        # --no-daemon: else Codex starts a background app server for the home, which runs
        # the hooks with its own environment, copies the CLI into the home and outlives the
        # agent.
        argv = [self.command, "--no-daemon"]
        if session.permission_mode == "default":
            argv += ["-a", "on-request"]
        elif session.permission_mode == "bypassPermissions":
            argv += ["--dangerously-bypass-approvals-and-sandbox"]
        if notice:
            argv.append(notice)
        return base.Launch(argv, {"CODEX_HOME": str(home)}, warnings)

    def parse_event(self, native: str, payload: str) -> base.Event | None:
        if native not in EVENTS:
            return None
        data = json.loads(payload) if payload.strip() else {}
        neutral = EVENTS[native]
        if native == "Interrupt":
            return base.Event(neutral, output_ignored=True)
        if native == "Stop":
            return base.Event(neutral, continued=bool(data.get("stop_hook_active")))
        if neutral in (base.WAITING, base.RESUMED):
            about = ["tool", data.get("tool_name", ""), data.get("tool_input")]
            digest = hashlib.sha256(json.dumps(about, sort_keys=True).encode()).hexdigest()
            return base.Event(neutral, key=digest[:16])
        return base.Event(neutral, data.get("prompt", ""))

    def continue_output(self, text: str) -> str | None:
        # Blocking the stop makes Codex go on with `reason` as the next input, with no
        # UserPromptSubmit for it; the Stop that ends that turn has stop_hook_active true.
        return json.dumps({"decision": "block", "reason": text})

    def first_hook_blocker(self, cwd: str, env: dict[str, str]) -> base.Blocker:
        # Read from the agent's own config.toml, which LADO wrote with what it carried: it
        # is what the agent's Codex reads.
        folder = Path(cwd)
        home = Path(env.get("CODEX_HOME") or "")
        path = home / "config.toml"
        try:
            config = _read_toml(path)
        except (OSError, ValueError) as error:
            return base.Blocker(
                warning=f"cannot tell whether {self.title} asks the human before its first "
                f"hook in {folder}: {path}: {error}"
            )
        trust = _trust_entry(config.get("projects"), folder)
        hooks: list[Path] = []
        if trust is None or trust[1] == "trusted":  # an untrusted folder's hooks do not load
            hooks = _unreviewed(folder, home, (config.get("hooks") or {}).get("state") or {})
        review = (
            f"the repository's own hooks in {', '.join(map(str, hooks))}: in its terminal "
            'choose "Trust all and continue" or "Continue without trusting (hooks won\'t '
            'run)"; reviewing them once in your own Codex there stops the question'
        )
        if trust is None:
            reason = (
                f"{self.title} asks whether to trust {gitpaths.main_root(folder)}: in its "
                'terminal choose "Trust and continue" ("Quit" closes the agent); trusting it '
                "once in your own Codex (`codex` in that folder) stops the question"
            )
            return base.Blocker(
                reason=f"{reason}; then it asks to review {review}" if hooks else reason
            )
        if hooks:
            return base.Blocker(reason=f"{self.title} asks to review {review}")
        return base.Blocker()


def _user_config(environ, warnings: list[str]) -> tuple[dict, Path]:
    """The user's own Codex config (CODEX_HOME of the agent's environment, else
    ~/.codex) and its path; {} when there is none, or with a warning when it cannot be
    read."""
    if environ.get("CODEX_HOME"):
        path = Path(environ["CODEX_HOME"]) / "config.toml"
    else:
        path = Path(environ.get("HOME") or Path.home()) / ".codex" / "config.toml"
    try:
        return _read_toml(path), path
    except (OSError, ValueError) as error:
        warnings.append(
            f"cannot read {path}: {error}; nothing of it is carried into the Codex agents' config"
        )
        return {}, path


def _read_toml(path: Path) -> dict:
    """A TOML file's table; {} when there is no file."""
    try:
        text = path.read_text()
    except FileNotFoundError:
        return {}
    return tomllib.loads(text)


# A folder's trust (Codex 0.162.0, checked by hand; the order read in its source,
# config/src/loader/mod.rs): Codex looks up the folder it runs in, its project root (the
# nearest folder up with a .git), then its repository's main root (a linked worktree's main
# repo), each by its real path, then as spelled; the first entry with a trust level decides,
# trusted or untrusted. An entry above the git root covers nothing. With none, Codex asks.
# The agent's Codex uses the default project_root_markers (.git): the user's are not
# carried.
def _trust_keys(cwd: Path) -> list[str]:
    folders = [cwd, _project_root(cwd)]
    if gitpaths.rev_parse(cwd, "--git-common-dir"):
        folders.append(gitpaths.main_root(cwd))
    keys: list[str] = []
    for folder in folders:
        for spelling in (str(folder.resolve()), str(folder)):
            if spelling not in keys:
                keys.append(spelling)
    return keys


def _project_root(cwd: Path) -> Path:
    for folder in (cwd.resolve(), *cwd.resolve().parents):
        git = folder / ".git"
        if git.is_file() or (git / "HEAD").exists():
            return folder
    return cwd.resolve()


def _trust_entry(projects, cwd: Path) -> tuple[str, str] | None:
    """The projects entry Codex goes by in `cwd`: its key and trust level."""
    if not isinstance(projects, dict):
        return None
    for key in _trust_keys(cwd):
        entry = projects.get(key)
        if isinstance(entry, dict) and isinstance(entry.get("trust_level"), str):
            return key, entry["trust_level"]
    return None


# The repository's own hooks (read in Codex's source, config/src/loader/mod.rs): from each
# folder from the project root down to the agent's folder that has a .codex folder (not the
# Codex home), its hooks.json and the [hooks] of its config.toml, only in a trusted folder.
# In a linked worktree they are the main checkout's, read from there, so the trust the user
# gave them in the main checkout holds. Plugins' hooks come from plugins installed in the
# Codex home, which is new for each agent: none.
def _repo_hook_files(cwd: Path, home: Path) -> list[Path]:
    cwd, root = cwd.resolve(), _project_root(cwd)
    top = gitpaths.rev_parse(cwd, "--show-toplevel")
    checkout = Path(top).resolve() if top else None
    main = gitpaths.main_root(cwd)
    folders = [f for f in (cwd, *cwd.parents) if f == root or root in f.parents]
    files = []
    for folder in reversed(folders):
        dot = folder / ".codex"
        if not dot.is_dir() or dot.resolve() == home.resolve():
            continue
        if checkout and checkout != main and folder.is_relative_to(checkout):
            dot = main / folder.relative_to(checkout) / ".codex"
        files += [dot / "hooks.json", dot / "config.toml"]
    return files


def _hook_handlers(path: Path) -> list[tuple[str, str]]:
    """The trust key and hash of each hook Codex loads from `path`; none from a file it
    cannot read (Codex warns and skips it too)."""
    try:
        if path.suffix == ".json":
            events = json.loads(path.read_text()).get("hooks") or {}
        else:
            events = _read_toml(path).get("hooks") or {}
    except (OSError, ValueError, AttributeError):
        return []
    handlers = []
    for event, groups in events.items() if isinstance(events, dict) else ():
        if event not in LABELS or not isinstance(groups, list):
            continue
        for g, group in enumerate(groups):
            listed = (group.get("hooks") or []) if isinstance(group, dict) else []
            for h, handler in enumerate(listed):
                if isinstance(handler, dict) and handler.get("type") in ("command", "mcp_tool"):
                    key = f"{path}:{LABELS[event]}:{g}:{h}"
                    handlers.append((key, hook_hash(event, group, handler)))
    return handlers


def _unreviewed(cwd: Path, home: Path, trusted: dict) -> list[Path]:
    """The repository's hook files with a hook Codex will ask the human to review."""
    files = []
    for path in _repo_hook_files(cwd, home):
        for key, digest in _hook_handlers(path):
            entry = trusted.get(key) or {}
            if entry.get("enabled") is not False and entry.get("trusted_hash") != digest:
                files.append(path)
                break
    return files


def hook_hash(event: str, group: dict, handler: dict) -> str:
    """The hash Codex trusts a hook by (trusted_hash; its hook_hash and version_for_toml,
    read in its source, hooks/src/engine/discovery.rs and config/src/fingerprint.rs, and
    checked against hashes Codex 0.162.0 wrote): SHA-256 of the compact, key-sorted JSON of
    the event's label, the group's matcher and the handler as Codex normalizes it."""
    timeout = handler.get("timeout")
    if event in SHORT:
        timeout = min(max(1 if timeout is None else timeout, 1), 3)
    else:
        timeout = max(600 if timeout is None else timeout, 1)
    if handler.get("type") == "mcp_tool":
        normalized = {
            "type": "mcp_tool",
            "server": handler.get("server"),
            "tool": handler.get("tool"),
            "input": handler.get("input") or {},
            "timeout": timeout,
        }
    else:
        normalized = {
            "type": "command",
            "command": handler.get("command"),
            "timeout": timeout,
            "async": bool(handler.get("async", False)),
        }
        limit = handler.get("additionalContextLimit")
        if event in CONTEXT_EVENTS and limit is not None and limit != DEFAULT_CONTEXT_LIMIT:
            normalized["additionalContextLimit"] = limit
    if handler.get("statusMessage") is not None:
        normalized["statusMessage"] = handler["statusMessage"]
    identity = {"event_name": LABELS[event], "hooks": [normalized]}
    if event not in UNMATCHED and group.get("matcher") is not None:
        identity["matcher"] = group["matcher"]
    text = json.dumps(identity, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(text.encode()).hexdigest()


def _hooks(agent: state.Agent, home: Path) -> dict:
    """LADO's hooks, trusted: Codex asks the human to review a hook whose trusted_hash is
    not its own, keyed by the real path of the config file that holds it."""
    source = Path(os.path.realpath(home)) / "config.toml"
    hooks: dict = {"state": {}}
    for event in EVENTS:
        handler: dict = {"type": "command", "command": base.hook_command(agent, event)}
        if event in HOOK_TIMEOUTS:
            handler["timeout"] = HOOK_TIMEOUTS[event]
        group = {"hooks": [handler]}
        hooks[event] = [group]
        key = f"{source}:{LABELS[event]}:0:0"
        hooks["state"][key] = {"trusted_hash": hook_hash(event, group, handler)}
    return hooks


def _mcp_servers(servers: dict[str, base.McpServer], environ: list[str]) -> dict:
    # Codex starts a stdio server with a few of its variables (HOME, PATH, USER, SHELL,
    # TERM, TMPDIR, ...), the literals of `env` and the variables `env_vars` names (checked
    # by hand). The other CLIs give a server their whole environment, the agent's, so each
    # server names all of the agent's variables (`environ`): a kit's server that reads one
    # itself works here too, and so do `lado mcp` (TMUX_TMPDIR) and lado.mcp_exec. Names
    # only: no value goes into this file.
    config = {}
    for name, server in servers.items():
        names = list(dict.fromkeys([*environ, *server.env_vars]))
        config[name] = {
            "command": server.command[0],
            "args": server.command[1:],
            "env": server.env,
            "env_vars": names,
        }
    if "lado" in config:
        # The first turn waits for a required server, so LADO's tools are there; one that
        # fails makes Codex exit. Each MCP call asks for approval unless the server's tools
        # are approved; a kit's servers ask as Codex's own would.
        config["lado"].update(required=True, default_tools_approval_mode="approve")
    return config


# Codex's sandbox (workspace-write) keeps .git under the folder it runs in and a worktree's
# git folder read-only, so a worker cannot commit; writable_roots does not lift it. A
# permission profile can: an explicit rule for the git folders wins (checked by hand: a
# commit in a LADO worktree and in the main checkout). Git's hooks and config stay
# read-only, as git runs them outside the sandbox. Reading is not restricted (checked), so
# AgentSpec.read needs nothing. Hooks run outside the sandbox (Codex's review dialog says
# so) and MCP servers are not sandboxed: both write LADO_HOME.
def _git_profile(cwd: Path) -> dict | None:
    common = gitpaths.rev_parse(cwd, "--git-common-dir")
    gitdir = gitpaths.rev_parse(cwd, "--git-dir")
    if not common or not gitdir:
        return None
    common_dir, git_dir = Path(common).resolve(), Path(gitdir).resolve()
    filesystem = {str(common_dir): "write", str(git_dir): "write"}
    filesystem.update({str(common_dir / "hooks"): "read", str(common_dir / "config"): "read"})
    return {"extends": ":workspace", "filesystem": filesystem}


# A small TOML writer for LADO's config.toml: the standard library reads TOML, it does not
# write it.
class Unwritable(ValueError):
    """A value LADO does not write as TOML (e.g. a date); `key` names it."""

    def __init__(self, key: str):
        super().__init__(f"cannot write {key} as TOML")
        self.key = key


BARE_KEY = re.compile(r"[A-Za-z0-9_-]+")
ESCAPES = {
    '"': '\\"',
    "\\": "\\\\",
    "\b": "\\b",
    "\t": "\\t",
    "\n": "\\n",
    "\f": "\\f",
    "\r": "\\r",
}


def _keep(value, key: str, dropped: list[str]):
    """`value` without what toml_text cannot write, each such key added to `dropped`;
    None when nothing is left of it."""
    if isinstance(value, dict):
        kept = {}
        for k, v in value.items():
            if (inner := _keep(v, f"{key}.{k}", dropped)) is not None:
                kept[k] = inner
        return kept or None
    try:
        _value(value, key)
    except Unwritable:
        dropped.append(key)
        return None
    return value


def toml_text(doc: dict) -> str:
    """`doc` as a TOML document; Unwritable for a value TOML or this writer cannot hold."""
    lines: list[str] = []
    _table(lines, [], doc)
    return "\n".join(lines) + "\n"


def _table(lines: list[str], path: list[str], table: dict) -> None:
    tables, arrays = [], []
    for key, value in table.items():
        if isinstance(value, dict):
            tables.append((key, value))
        elif _table_array(value):
            arrays.append((key, value))
        else:
            lines.append(f"{_key(key)} = {_value(value, '.'.join([*path, key]))}")
    for key, value in tables:
        lines += ["", f"[{'.'.join(_key(k) for k in [*path, key])}]"]
        _table(lines, [*path, key], value)
    for key, items in arrays:
        for item in items:
            lines += ["", f"[[{'.'.join(_key(k) for k in [*path, key])}]]"]
            _table(lines, [*path, key], item)


def _table_array(value) -> bool:
    return isinstance(value, list) and bool(value) and all(isinstance(v, dict) for v in value)


def _value(value, key: str) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if math.isnan(value):
            return "nan"
        if math.isinf(value):
            return "inf" if value > 0 else "-inf"
        return repr(value)
    if isinstance(value, str):
        return _string(value)
    if isinstance(value, list):
        return "[" + ", ".join(_value(v, key) for v in value) + "]"
    if isinstance(value, dict):
        items = ", ".join(f"{_key(k)} = {_value(v, f'{key}.{k}')}" for k, v in value.items())
        return "{ " + items + " }" if items else "{}"
    raise Unwritable(key)


def _key(key: str) -> str:
    return key if BARE_KEY.fullmatch(key) else _string(key)


def _string(text: str) -> str:
    out = []
    for char in text:
        if char in ESCAPES:
            out.append(ESCAPES[char])
        elif ord(char) < 0x20 or ord(char) == 0x7F:
            out.append(f"\\u{ord(char):04x}")
        else:
            out.append(char)
    return '"' + "".join(out) + '"'
