"""The provider interface: what LADO needs from an agent CLI (Claude Code, Codex, ...)."""

import shlex
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from lado import state

# Neutral hook events. A provider maps its own hook events onto these; see lado.hooks.
SESSION_START = "session_start"
PROMPT_SUBMIT = "prompt_submit"  # the agent received input, e.g. a typed message
TURN_END = "turn_end"
WAITING = "waiting"  # the agent needs the human, e.g. a permission prompt
SESSION_END = "session_end"


@dataclass(frozen=True)
class Capabilities:
    status_events: bool  # hooks report when the agent starts, works and stops
    permission_event: bool  # a hook reports that the agent waits for the human
    deliver_on_turn_end: bool  # the turn-end hook can hand the agent its queued messages


@dataclass(frozen=True)
class Event:
    kind: str  # one of the neutral events above
    prompt: str = ""  # the input the agent received, for PROMPT_SUBMIT


class Provider(ABC):
    name: str  # stored in the state, e.g. "claude"
    title: str  # for humans, e.g. "Claude Code"
    command: str  # the CLI executable
    install_hint: str  # shown by `lado doctor` when the command is missing
    capabilities: Capabilities

    @abstractmethod
    def launch_command(
        self,
        agent: state.Agent,
        session: state.Session,
        prompt: str,
        first_message: str | None = None,
    ) -> list[str]:
        """Write the agent's config files (LADO MCP server, hooks) and return its argv.

        `prompt` is the agent's role, added to the system prompt; `first_message`, if any,
        is its first input.
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
    }


def config_dir(agent: state.Agent) -> Path:
    path = state.home() / "agents" / agent.session / agent.name
    path.mkdir(parents=True, exist_ok=True)
    return path


def hook_command(agent: state.Agent, event: str) -> str:
    """Shell command that reports a native hook event of `agent` to LADO."""
    command = lado_command(
        "hook",
        event,
        "--session",
        agent.session,
        "--agent",
        agent.name,
        "--instance",
        agent.instance,
    )
    return shlex.join(command)


def mcp_server(agent: state.Agent) -> dict:
    """The LADO MCP server entry for the agent's MCP config."""
    server = lado_command("mcp")
    return {"command": server[0], "args": server[1:], "env": agent_env(agent)}
