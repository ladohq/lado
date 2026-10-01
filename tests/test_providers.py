import json

import pytest

from lado import hooks, providers, runtime, state
from lado.providers import Event


def test_registry():
    assert providers.DEFAULT in providers.names()
    claude = providers.get("claude")
    assert (claude.name, claude.command) == ("claude", "claude")
    assert claude.capabilities.deliver_on_turn_end
    with pytest.raises(ValueError, match='unknown provider "nope"; known: claude'):
        providers.get("nope")


@pytest.mark.parametrize(
    ("native", "payload", "expected"),
    [
        ("SessionStart", {"source": "startup"}, Event(providers.SESSION_START)),
        ("UserPromptSubmit", {"prompt": "hi"}, Event(providers.PROMPT_SUBMIT, "hi")),
        ("Stop", {}, Event(providers.TURN_END)),
        ("SessionEnd", {}, Event(providers.SESSION_END)),
        ("Notification", {"notification_type": "permission_prompt"}, Event(providers.WAITING)),
        ("Notification", {"message": "Claude needs your permission"}, Event(providers.WAITING)),
        ("Notification", {"notification_type": "idle_prompt"}, None),
        ("PreToolUse", {}, None),
    ],
)
def test_claude_maps_native_events(native, payload, expected):
    assert providers.get("claude").parse_event(native, json.dumps(payload)) == expected


def test_claude_continues_with_queued_messages():
    out = providers.get("claude").continue_output("[from w1] done")
    assert json.loads(out) == {"decision": "block", "reason": "[from w1] done"}


def test_agents_get_the_session_provider(repo, fake_tmux):
    runtime.start_session(str(repo), "s", None)
    runtime.spawn_worker("s", "task")
    assert state.get_session("s").provider == "claude"
    assert [a.provider for a in state.list_agents("s")] == ["claude", "claude"]


class _NoTurnEndDelivery(providers.Provider):
    name = "plain"
    capabilities = providers.Capabilities(
        status_events=True, permission_event=False, deliver_on_turn_end=False
    )

    def launch_command(self, agent, session, prompt, first_message=None):
        return []

    def parse_event(self, native, payload):
        return Event(native)


def test_turn_end_types_messages_when_provider_cannot_deliver_them(repo, fake_tmux):
    runtime.start_session(str(repo), "s", None)
    runtime.send_message("s", "w1", "supervisor", "done")  # supervisor is starting: queued
    out = hooks.handle(_NoTurnEndDelivery(), Event(providers.TURN_END), "s", "supervisor")
    assert out is None
    assert fake_tmux[-1] == ("send_text", "s", "supervisor", "[from w1] done")
    assert state.get_agent("s", "supervisor").status == state.BUSY
