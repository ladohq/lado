"""The provider interface: what LADO needs from an agent CLI (Claude Code, Codex, ...)."""

import shlex
import shutil
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

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
        nothing. Called before the agent's window starts."""
        return Blocker()

    def continue_output(self, text: str) -> str | None:
        """Hook output that makes the agent continue with `text` when its turn ends.

        Only called when capabilities.deliver_on_turn_end is set.
        """
        return None


def lado_command(*args: str) -> list[str]:
    # The same interpreter that runs this code, so agents use the same LADO install.
    return interpreter.run_module("lado.cli", *args)


def agent_env(agent: state.Agent) -> dict[str, str]:
    return {
        "LADO_HOME": str(state.home()),
        "LADO_SESSION": agent.session,
        "LADO_AGENT": agent.name,
        # Hooks and the MCP server type messages into agents' windows on the same tmux server.
        "LADO_TMUX_SOCKET": tmux.socket(),
    }


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
