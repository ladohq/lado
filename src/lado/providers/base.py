"""The provider interface: what LADO needs from an agent CLI (Claude Code, Codex, ...)."""

import shlex
import shutil
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

from lado import state, tmux

# Neutral hook events. A provider maps its own hook events onto these; see lado.hooks.
SESSION_START = "session_start"
PROMPT_SUBMIT = "prompt_submit"  # the agent received input, e.g. a typed message
TURN_END = "turn_end"
WAITING = "waiting"  # the agent needs the human, e.g. a permission prompt
SESSION_END = "session_end"
# The agent leaves its conversation for another one and its process goes on (Claude Code's
# /clear and /resume): not ready until CONVERSATION_START, but not gone either.
CONVERSATION_END = "conversation_end"
CONVERSATION_START = "conversation_start"  # ready again, in the other conversation


@dataclass(frozen=True)
class Capabilities:
    status_events: bool  # hooks report when the agent starts, works and stops
    permission_event: bool  # a hook reports that the agent waits for the human
    deliver_on_turn_end: bool  # the turn-end hook can hand the agent its queued messages
    skills: bool  # the agent loads SKILL.md folders that LADO places for it
    # The session-start hook can hold the first turn until the CLI has listed LADO's MCP
    # tools (lado.hooks waits for it); False where that hook would hold the MCP server too.
    hold_first_turn: bool = False


@dataclass(frozen=True)
class Event:
    kind: str  # one of the neutral events above
    prompt: str = ""  # the input the agent received, for PROMPT_SUBMIT


@dataclass(frozen=True)
class McpServer:
    """A stdio MCP server: the command that starts it and its environment."""

    command: list[str]
    env: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class AgentSpec:
    """Everything an agent is given, independent of the CLI that runs it (see lado.kits)."""

    prompt: str  # the role, added to the system prompt
    skills: dict[str, Path] = field(default_factory=dict)  # name -> SKILL.md folder
    mcp: dict[str, McpServer] = field(default_factory=dict)  # name -> server, incl. "lado"


@dataclass(frozen=True)
class Launch:
    """How to start an agent: its argv and the environment its CLI needs on top of
    agent_env."""

    argv: list[str]
    env: dict[str, str] = field(default_factory=dict)


class Provider(ABC):
    name: str  # stored in the state, e.g. "claude"
    title: str  # for humans, e.g. "Claude Code"
    command: str  # the CLI executable
    install_hint: str  # shown by `lado doctor` when the command is missing
    # The version LADO is tested with, e.g. "2.1.287", or a prefix, e.g. "7.8"; "" for any.
    tested_version: str = ""
    capabilities: Capabilities

    @abstractmethod
    def launch_command(
        self,
        agent: state.Agent,
        session: state.Session,
        spec: AgentSpec,
        first_message: str | None = None,
    ) -> Launch:
        """Write the agent's config files (MCP servers, skills, hooks) and return how to
        start it.

        `spec.prompt` is the agent's role, added to the system prompt; `first_message`, if
        any, is its first input. LADO checks `spec` against `capabilities` before the call.
        """

    @abstractmethod
    def parse_event(self, native: str, payload: str) -> Event | None:
        """Translate a native hook event and its input into a neutral event, or None to
        ignore it."""

    def continue_output(self, text: str) -> str | None:
        """Hook output that makes the agent continue with `text` when its turn ends.

        Only called when capabilities.deliver_on_turn_end is set.
        """
        return None


def lado_command(*args: str) -> list[str]:
    # The same interpreter that runs this code, so agents use the same LADO install.
    return [sys.executable, "-m", "lado.cli", *args]


def agent_env(agent: state.Agent) -> dict[str, str]:
    return {
        "LADO_HOME": str(state.home()),
        "LADO_SESSION": agent.session,
        "LADO_AGENT": agent.name,
        # Hooks and the MCP server type messages into agents' windows on the same tmux server.
        "LADO_TMUX_SOCKET": tmux.socket(),
    }


def config_dir(agent: state.Agent) -> Path:
    path = state.home() / "agents" / agent.session / agent.name
    path.mkdir(parents=True, exist_ok=True)
    return path


def remove_config_dir(agent: state.Agent) -> None:
    """Remove what launch_command wrote for an agent that never started."""
    shutil.rmtree(state.home() / "agents" / agent.session / agent.name, ignore_errors=True)


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
