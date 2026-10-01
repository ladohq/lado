"""Agent CLIs that LADO can run, behind one interface (see lado.providers.base)."""

from lado.providers.base import (
    PROMPT_SUBMIT,
    SESSION_END,
    SESSION_START,
    TURN_END,
    WAITING,
    Capabilities,
    Event,
    Provider,
    agent_env,
    lado_command,
)
from lado.providers.claude import ClaudeProvider

__all__ = [
    "PROMPT_SUBMIT",
    "SESSION_END",
    "SESSION_START",
    "TURN_END",
    "WAITING",
    "Capabilities",
    "Event",
    "Provider",
    "agent_env",
    "get",
    "lado_command",
    "names",
]

DEFAULT = "claude"

_PROVIDERS: dict[str, Provider] = {p.name: p for p in (ClaudeProvider(),)}


def get(name: str) -> Provider:
    try:
        return _PROVIDERS[name]
    except KeyError:
        raise ValueError(f'unknown provider "{name}"; known: {", ".join(names())}') from None


def names() -> list[str]:
    return list(_PROVIDERS)
