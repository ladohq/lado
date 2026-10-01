"""Agent CLIs that LADO can run, behind one interface (see lado.providers.base)."""

from lado.providers.base import (
    PROMPT_SUBMIT,
    SESSION_END,
    SESSION_START,
    TURN_END,
    WAITING,
    AgentSpec,
    Capabilities,
    Event,
    Launch,
    McpServer,
    Provider,
    agent_env,
    lado_command,
)
from lado.providers.claude import ClaudeProvider
from lado.providers.kilo import KiloProvider

__all__ = [
    "PROMPT_SUBMIT",
    "SESSION_END",
    "SESSION_START",
    "TURN_END",
    "WAITING",
    "AgentSpec",
    "Capabilities",
    "Event",
    "Launch",
    "McpServer",
    "Provider",
    "agent_env",
    "get",
    "lado_command",
    "names",
]

DEFAULT = "claude"

_PROVIDERS: dict[str, Provider] = {p.name: p for p in (ClaudeProvider(), KiloProvider())}


def get(name: str) -> Provider:
    try:
        return _PROVIDERS[name]
    except KeyError:
        raise ValueError(f'unknown provider "{name}"; known: {", ".join(names())}') from None


def names() -> list[str]:
    return list(_PROVIDERS)
