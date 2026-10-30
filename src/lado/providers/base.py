"""The provider interface: what LADO needs from an agent CLI (Claude Code, Codex, ...)."""

import contextlib
import os
import shlex
import shutil
import signal
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

from lado import agent_env as outside_env
from lado import interpreter, state, tmux

# Neutral hook events. A provider maps its own hook events onto these; see lado.hooks.
SESSION_START = "session_start"
PROMPT_SUBMIT = "prompt_submit"  # the agent received input, e.g. a typed message
TURN_END = "turn_end"
WAITING = "waiting"  # the agent needs the human, e.g. a permission prompt
RESUMED = "resumed"  # the human answered what the agent waited for; it works again
SESSION_END = "session_end"
# The agent leaves its conversation for another one and its process goes on (Claude Code's
# /clear and /resume): not ready until CONVERSATION_START, but not gone either.
CONVERSATION_END = "conversation_end"
CONVERSATION_START = "conversation_start"  # ready again, in the other conversation
# What LADO runs inside the CLI failed (a plugin could not hand the turn-end hook's output
# on): Event.error says what; lado.hooks writes it to hooks.log.
HOOK_ERROR = "hook_error"


@dataclass(frozen=True)
class Capabilities:
    status_events: bool  # hooks report when the agent starts, works and stops
    # A hook reports that the agent waits for the human (WAITING). A provider that reports
    # it reports the answer too (RESUMED), with the same key: else the agent would look
    # waiting until its turn ends.
    permission_event: bool
    deliver_on_turn_end: bool  # the turn-end hook can hand the agent its queued messages
    skills: bool  # the agent loads SKILL.md folders that LADO places for it
    # The session-start hook can hold the first turn until the CLI has listed LADO's MCP
    # tools (lado.hooks waits for it); False where that hook would hold the MCP server too.
    hold_first_turn: bool = False
    # The CLI loses what is typed into it right after its start, and says by no event when
    # it takes input: its first messages' lines (never a body) go on its command line as
    # the `notice` of launch_command, handed over as typed (lado.runtime).
    notice_on_argv: bool = False
    # The CLI starts its session (its session-start hook) only when its first input is
    # submitted: an agent with an empty queue would never be ready, so LADO gives it a line
    # of its own (lado.runtime). Only with notice_on_argv, which takes that line.
    session_start_on_first_input: bool = False
    # The CLI takes what its turn-end hook printed once the hook has ended by itself, goes
    # on with a turn from it, and that turn's end says so (Event.continued): a printed
    # batch waits for that turn's end, not for a delay (lado.hooks marks it printed,
    # lado.runtime._plan). False where more can fail after the print (a plugin's own call).
    output_taken_when_printed: bool = False
    # The CLI's own config can take the agent's edit tools away, also from its subagents and
    # in the permission modes LADO runs it with (AgentSpec.read_only). True only once checked
    # by hand on the CLI's tested version, as its provider's comment says; LADO refuses to
    # launch a read-only agent on a CLI that cannot (lado.runtime).
    deny_edit_tools: bool = False
    # An agent of this CLI cannot work without a login: LADO holds it, waiting, until the
    # CLI's login_status says there is one (lado.runtime, lado.login_wait). False for a CLI
    # that also works with models that need no login.
    needs_login: bool = False


@dataclass(frozen=True)
class Event:
    kind: str  # one of the neutral events above
    prompt: str = ""  # the input the agent received, for PROMPT_SUBMIT
    # For WAITING and RESUMED: the provider's id of the request waited for or answered, so
    # that only its answer ends the wait (lado.state.resume); "" where there is none.
    key: str = ""
    # For TURN_END: why the turn ended on an error (an API error, a rate limit), one short
    # line; "" for a turn that ended as usual, or that the human cancelled.
    error: str = ""
    # For TURN_END with an error: the provider says the error passes by itself (an
    # overloaded or failing API), so LADO resumes the agent after a while (lado.hooks).
    transient: bool = False
    # The CLI ignores what the hook prints (Claude Code's StopFailure): the queue cannot go
    # in the hook's output, so it is typed in.
    output_ignored: bool = False
    # For TURN_END: this turn went on from what the previous turn-end hook printed, so the
    # CLI took the messages in that output (lado.hooks). Set by a provider whose CLI runs no
    # prompt-submit hook for that output and says so at the turn's end.
    continued: bool = False
    # For TURN_END: work the agent started still runs after this turn ended (e.g. Claude
    # Code's background subagents and shells), so it is `background`, not idle (lado.hooks).
    # A provider that cannot tell leaves it False.
    background: bool = False


ERROR_LIMIT = 160  # characters of an Event.error


def error_line(kind: str, details: str = "") -> str:
    """An Event.error: the error's kind and the first line of its details, cut short."""
    first = (details.strip().splitlines() or [""])[0].strip()
    text = f"{kind}: {first}" if first else kind
    return text if len(text) <= ERROR_LIMIT else text[: ERROR_LIMIT - 1] + "…"


@dataclass(frozen=True)
class McpServer:
    """A stdio MCP server: the command that starts it and its environment."""

    command: list[str]
    env: dict[str, str] = field(default_factory=dict)
    # The names of the agent's variables the server reads (lado.mcp_exec fills its env from
    # them): a CLI that starts a server with only some of its environment passes these on.
    env_vars: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class AgentSpec:
    """Everything an agent is given, independent of the CLI that runs it (see lado.kits)."""

    prompt: str  # the role, added to the system prompt
    skills: dict[str, Path] = field(default_factory=dict)  # name -> SKILL.md folder
    mcp: dict[str, McpServer] = field(default_factory=dict)  # name -> server, incl. "lado"
    # Folders the agent reads without asking, never loaded as skills (e.g. the skills a
    # lead skill names, lado.runtime).
    read: list[Path] = field(default_factory=list)
    # The agent's environment before LADO's and the provider's variables (lado.agent_env),
    # where a CLI that keeps the user's settings in its own home finds that home. Read only:
    # it holds the user's keys.
    environ: dict[str, str] = field(default_factory=dict, repr=False)
    # Its role changes nothing in the repository (lado.kits): the CLI's edit tools are taken
    # away. Only for a CLI with Capabilities.deny_edit_tools.
    read_only: bool = False


@dataclass(frozen=True)
class Launch:
    """How to start an agent: its argv and the environment its CLI needs on top of
    agent_env."""

    argv: list[str]
    env: dict[str, str] = field(default_factory=dict)
    # What the provider could not do as asked and did otherwise, told whoever starts the
    # agent (e.g. a user setting it could not read).
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Blocker:
    """What holds an agent before its first hook (Provider.first_hook_blocker)."""

    # Why the agent will wait for the human from its start, and what the human does about
    # it; None when nothing is known to hold it.
    reason: str | None = None
    # Why the provider cannot tell whether something holds it; None when it can.
    warning: str | None = None
    # What the provider did so that nothing holds it (e.g. recorded an answer in the CLI's
    # config), one line per write, told and logged as the reason is.
    notes: tuple[str, ...] = ()


# A CLI's login, as its own status command says (Provider.login_status).
YES, NO, UNKNOWN = "yes", "no", "unknown"
LOGIN_TIMEOUT = 10  # seconds a status command may take; then it is killed
NO_LOGIN_READER = "LADO cannot read this CLI's login"


@dataclass(frozen=True)
class LoginItem:
    """One login of a CLI that keeps several (OpenCode's and Kilo's credentials): the model
    provider it is for, and its kind (`api`, `oauth`, ...) or, for one a variable gives,
    that variable."""

    name: str
    kind: str
    variable: str = ""


@dataclass(frozen=True)
class LoginStatus:
    """Whether a CLI is logged in and how; never a secret's value."""

    state: str  # YES, NO or UNKNOWN
    method: str = ""  # for humans: "Subscription (Max)", "Pay per use (API key)", "2 credentials"
    file: str = ""  # the CLI's own login file (or "the login keychain"), when it names one
    # Where a login of `file` is, for the state line ("Claude Code's login file"); "" when
    # the line names no place for it.
    file_words: str = ""
    variable: str = ""  # the variable that logs it in, when one does
    items: tuple[LoginItem, ...] = ()
    problem: str = ""  # why UNKNOWN
    choice: str = ""  # the id of the LoginChoice this login is; "" for none


@dataclass(frozen=True)
class LoginChoice:
    """A way to log the CLI in that Settings offers (Provider.login_choices): a value of
    `variable`, one of the provider's login variables, pasted and kept as LADO's secret."""

    id: str
    title: str
    detail: str  # where the value comes from
    variable: str


@dataclass(frozen=True)
class LoginAction:
    """A command of the login window (lado.logins): its id in the API, its label, its argv."""

    id: str
    label: str
    argv: tuple[str, ...]


def run_status(argv: list[str], env: dict[str, str]) -> subprocess.CompletedProcess | str:
    """Run a CLI's login status command with `env` within LOGIN_TIMEOUT, from the home
    folder (no repository's config is read): its result, or why it has none, for an
    UNKNOWN status. Never prints or keeps the output."""
    path = env.get("PATH", os.defpath)
    found = shutil.which(argv[0], path=path)
    if found is None:
        return f"`{argv[0]}` is not on the agents' PATH"
    home = env.get("HOME")
    try:
        process = subprocess.Popen(
            [found, *argv[1:]],
            env=env,
            cwd=home if home and os.path.isdir(home) else None,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            errors="replace",
            # Its own group: a timeout kills what it started too, which holds its outputs.
            start_new_session=True,
        )
    except OSError as error:
        return f"`{shlex.join(argv)}` failed: {error.strerror or error}"
    try:
        out, err = process.communicate(timeout=LOGIN_TIMEOUT)
    except subprocess.TimeoutExpired:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGKILL)
        process.communicate()
        return f"`{shlex.join(argv)}` timed out after {LOGIN_TIMEOUT:g} s"
    return subprocess.CompletedProcess(argv, process.returncode, out, err)


class Provider(ABC):
    name: str  # stored in the state, e.g. "claude"
    title: str  # for humans, e.g. "Claude Code"
    command: str  # the CLI executable
    install_hint: str  # shown by `lado doctor` when the command is missing
    # The version LADO is tested with, e.g. "2.1.287", or a prefix, e.g. "7.8"; "" for any.
    tested_version: str = ""
    capabilities: Capabilities
    # The values of `lado start --permission-mode` this provider honours.
    permission_modes: tuple[str, ...]

    def check_permission_mode(self, mode: str | None) -> None:
        """Raise ValueError for a permission mode this provider cannot honour."""
        if mode and mode not in self.permission_modes:
            raise ValueError(
                f'permission mode "{mode}" is not supported by {self.title} ({self.name}); '
                f"supported: {', '.join(self.permission_modes)}"
            )

    @abstractmethod
    def launch_command(
        self,
        agent: state.Agent,
        session: state.Session,
        spec: AgentSpec,
        notice: str | None = None,
    ) -> Launch:
        """Write the agent's config files (MCP servers, skills, hooks) and return how to
        start it.

        `spec.prompt` is the agent's role, added to the system prompt in a way that keeps it
        off the command line, which `ps` shows to every user of the machine. The agent gets
        its first input through LADO's queue, as any message; only for a provider with
        `capabilities.notice_on_argv`, `notice` holds the lines of its first messages (never
        a body), which it takes as its first input. LADO checks `spec` against
        `capabilities` before the call.
        """

    @abstractmethod
    def parse_event(self, native: str, payload: str) -> Event | None:
        """Translate a native hook event and its input into a neutral event, or None to
        ignore it."""

    def first_hook_blocker(self, cwd: str, env: dict[str, str]) -> Blocker:
        """What the CLI, started in `cwd` with `env`, will ask the human before any hook
        runs (e.g. whether to trust the folder), read from the CLI's own files; by default
        nothing. It may first settle what LADO answers itself (Blocker.note). Called before
        the agent's window starts."""
        return Blocker()

    # A line about the login for the human, shown under its state in Settings (e.g. that
    # the CLI's agents do not get it); "" for none.
    login_note: str = ""
    # The variables that log the CLI in, which the human may set as LADO's secrets in
    # Settings (lado.project_secrets, LADO's folder); the first one is named in the reason
    # of an agent that waits for a login.
    login_variables: tuple[str, ...] = ()
    # What Settings asks to log the CLI in by a pasted value, and its answers; none for a
    # CLI that logs in by its own command (login_actions) or not from the page.
    login_question: str = ""
    login_choices: tuple[LoginChoice, ...] = ()

    def login_status(self, env: dict[str, str]) -> LoginStatus:
        """Whether the CLI, started with `env`, is logged in, as its own status command says
        (run_status); a failure, a timeout or output it cannot read is UNKNOWN with why,
        never NO. By default UNKNOWN."""
        return LoginStatus(UNKNOWN, problem=NO_LOGIN_READER)

    def login_actions(self) -> tuple[LoginAction, ...]:
        """The commands the login window runs for the human (the CLI's own login and, where
        it asks which one, logout); by default none."""
        return ()

    def keychain_login(self, env: dict[str, str]) -> str | None:
        """None when the CLI, started with `env`, does not read its login from the macOS
        login keychain, which only the graphical session opens (lado.gui_session); else
        how else to log it in, as the end of a sentence ("" when there is no other way).
        By default None."""
        return None

    def hook_limit(self, native: str) -> float | None:
        """The seconds the CLI gives LADO's hook of the native event `native` before it
        stops waiting for it; None when it waits with no limit. By default None."""
        return None

    def continue_output(self, text: str) -> str | None:
        """Hook output that makes the agent continue with `text` when its turn ends.

        Only called when capabilities.deliver_on_turn_end is set.
        """
        return None


def lado_command(*args: str) -> list[str]:
    # The same interpreter that runs this code, so agents use the same LADO install.
    return interpreter.run_module("lado.cli", *args)


# The names LADO sets for the agent CLIs (a provider's Launch.env), and those that would
# take the CLI's login or config from LADO's: reserved, so a project's variable never takes
# their place (lado.projects.RESERVED_NAMES). A provider that sets another name adds it here;
# tests/test_project_variables_core.py fails until it does.
CLI_VARIABLES = frozenset(
    {
        "CLAUDE_CONFIG_DIR",
        "CODEX_HOME",
        "OPENCODE_CONFIG",
        "OPENCODE_CONFIG_CONTENT",
        "OPENCODE_DISABLE_AUTOUPDATE",
        "KILO_CONFIG",
        "KILO_CONFIG_CONTENT",
        "KILO_DISABLE_AUTOUPDATE",
        "KILO_NO_DAEMON",
    }
)


def agent_env(agent: state.Agent) -> dict[str, str]:
    env = {
        "LADO_HOME": str(state.home()),
        "LADO_SESSION": agent.session,
        "LADO_AGENT": agent.name,
        # Hooks and the MCP server type messages into agents' windows on the same tmux server.
        "LADO_TMUX_SOCKET": tmux.socket(),
    }
    # A supervisor's `lado mcp` launches workers from the same outside folder, and starts
    # sessions in a project or refuses them inside projects/ by the same workspace
    # (lado.projects); its environment is its login shell's, which may name neither.
    for name in (outside_env.ENV_DIR_VAR, "LADO_REPOS"):
        if value := os.environ.get(name):
            env[name] = value
    return env


def configs_root() -> Path:
    """Where the agents' config folders are: one per running agent, <session>/<agent>.
    Each launch writes its folder anew; it is removed when the agent stops (lado.runtime)."""
    return state.home() / "agents"


def config_path(agent: state.Agent) -> Path:
    """The agent's config folder, not made."""
    return configs_root() / agent.session / agent.name


def config_dir(agent: state.Agent) -> Path:
    path = config_path(agent)
    path.mkdir(parents=True, exist_ok=True)
    return path


def remove_config_dir(agent: state.Agent) -> None:
    """Remove what launch_command wrote for an agent that does not run (any more)."""
    shutil.rmtree(config_path(agent), ignore_errors=True)


def remove_session_config_dirs(session: str) -> None:
    """Remove the config folders of all the session's agents, when none of them runs."""
    shutil.rmtree(configs_root() / session, ignore_errors=True)


# Seconds a turn-end hook may run before its CLI kills it, given explicitly where the CLI
# takes the hook's output once printed (Capabilities.output_taken_when_printed): a batch the
# hook never printed is typed in once this is over and a margin (lado.runtime
# HOOK_OUTPUT_WAIT). Both CLIs take it in seconds and kill a hook that runs longer, then go
# on (checked by hand with a Stop hook that sleeps 20 s under a limit of 3 s: Claude Code
# 2.1.296, `claude -p` on a local endpoint, and Codex CLI 0.162.0, `codex exec` on Ollama,
# each went on after 3 s and the hook never finished; Claude Code waited the 20 s under 30).
TURN_END_HOOK_TIMEOUT = 60


def hook_argv(agent: state.Agent, event: str) -> list[str]:
    """Command that reports a native hook event of `agent` to LADO."""
    return lado_command(
        "hook",
        event,
        "--session",
        agent.session,
        "--agent",
        agent.name,
        "--instance",
        agent.instance,
    )


def hook_command(agent: state.Agent, event: str) -> str:
    """hook_argv as a shell command."""
    return shlex.join(hook_argv(agent, event))


def mcp_server(agent: state.Agent) -> McpServer:
    """The LADO MCP server of the agent. It records which launch it serves when the CLI
    lists its tools (lado.hooks waits for that)."""
    return McpServer(lado_command("mcp"), {**agent_env(agent), "LADO_INSTANCE": agent.instance})


def link_skills(target: Path, skills: dict[str, Path]) -> Path:
    """Make `target` a folder of symlinks <name> -> skill folder, replacing what was there.

    A skill stays one folder (SKILL.md, scripts/, ...), so links keep its files and their
    modes as they are in the kit.
    """
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    for name, path in skills.items():
        (target / name).symlink_to(path, target_is_directory=True)
    return target
