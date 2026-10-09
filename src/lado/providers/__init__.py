"""Agent CLIs that LADO can run, behind one interface (see lado.providers.base)."""

from collections.abc import Callable

from lado.providers.base import (
    CONVERSATION_END,
    CONVERSATION_START,
    HOOK_ERROR,
    PROMPT_SUBMIT,
    RESUMED,
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
from lado.providers.codex import CodexProvider
from lado.providers.kilo import KiloProvider
from lado.providers.opencode import OpenCodeProvider

__all__ = [
    "CONVERSATION_END",
    "CONVERSATION_START",
    "HOOK_ERROR",
    "PROMPT_SUBMIT",
    "RESUMED",
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
    "keychain_users",
    "lado_command",
    "names",
]

_PROVIDERS: dict[str, Provider] = {
    p.name: p for p in (ClaudeProvider(), CodexProvider(), KiloProvider(), OpenCodeProvider())
}


def get(name: str) -> Provider:
    try:
        return _PROVIDERS[name]
    except KeyError:
        raise ValueError(f'unknown provider "{name}"; known: {", ".join(names())}') from None


def names() -> list[str]:
    return list(_PROVIDERS)


def keychain_users(
    env: dict[str, str], which: Callable[[str], str | None]
) -> list[tuple[str, str]]:
    """The title and hint (Provider.keychain_login) of each provider installed (`which`) whose
    CLI, started with `env`, reads its login from the macOS keychain."""
    users = []
    for provider in _PROVIDERS.values():
        hint = provider.keychain_login(env)
        if hint is not None and which(provider.command):
            users.append((provider.title, hint))
    return users
