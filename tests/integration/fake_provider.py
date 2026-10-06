"""A fake agent CLI as a LADO provider, for integration tests. Not shipped with LADO.

The fake agent (fake_agent.py) runs its hooks and MCP server in their own processes, which
must know the fake providers too. So run as a script, this file is `lado` with them registered.
"""

import json
import sys
from pathlib import Path

from lado import cli, providers, state
from lado.providers import base

LADO = Path(__file__).resolve()
AGENT = LADO.with_name("fake_agent.py")

# The fake agent reports the neutral events under their own names.
EVENTS = (
    base.SESSION_START,
    base.PROMPT_SUBMIT,
    base.TURN_END,
    base.WAITING,
    base.RESUMED,
    base.SESSION_END,
    base.CONVERSATION_END,
    base.CONVERSATION_START,
)


# The errors of the fake agent's `fail` that pass by themselves (base.Event.transient), as
# Claude Code's overload.
TRANSIENT = frozenset({"overloaded"})


def lado_command(*args: str) -> list[str]:
    return [sys.executable, str(LADO), *args]


class FakeProvider(base.Provider):
    title = "Fake agent"
    command = sys.executable
    install_hint = "part of the LADO tests"
    permission_modes = ()  # the fake agent asks for no permissions

    def __init__(self, name: str, deliver_on_turn_end: bool, says_continued: bool = False):
        self.name = name
        # Like Claude Code: no prompt-submit hook for the turn-end hook's output, and the
        # turn's end says the turn went on from it (Event.continued).
        self.says_continued = says_continued
        self.capabilities = base.Capabilities(
            status_events=True,
            permission_event=False,
            deliver_on_turn_end=deliver_on_turn_end,
            skills=True,
            hold_first_turn=True,
        )

    def launch_command(
        self,
        agent: state.Agent,
        session: state.Session,
        spec: base.AgentSpec,
        first_message: str | None = None,
    ) -> base.Launch:
        config_dir = base.config_dir(agent)
        # Its own logs outlive it, for the tests (agent_helpers.fake_logs): LADO removes
        # the config folder when the agent stops.
        logs = state.home() / "fake-agents" / agent.session / agent.name
        logs.mkdir(parents=True, exist_ok=True)
        hook = ["--session", agent.session, "--agent", agent.name, "--instance", agent.instance]
        # The LADO MCP server has to know the fake providers too.
        lado = base.McpServer(lado_command("mcp"), spec.mcp["lado"].env)
        config = {
            "hooks": {e: lado_command("hook", e, *hook) for e in EVENTS},
            "prompt": spec.prompt,
            "skills": str(base.link_skills(config_dir / "skills", spec.skills)),
            "mcp": {
                name: {"command": s.command, "env": s.env}
                for name, s in {**spec.mcp, "lado": lado}.items()
            },
            "continue_on_turn_end": self.capabilities.deliver_on_turn_end,
            "says_continued": self.says_continued,
            "inputs": str(logs / "inputs.jsonl"),
            "seen": str(logs / "seen.json"),
        }
        config_file = config_dir / "fake.json"
        config_file.write_text(json.dumps(config, indent=2))
        # On the command line, like the real CLIs: tmux's limit on its length applies.
        first = [first_message] if first_message else []
        return base.Launch([sys.executable, str(AGENT), str(config_file), *first])

    def parse_event(self, native: str, payload: str) -> base.Event | None:
        if native not in EVENTS:
            return None
        data = json.loads(payload) if payload.strip() else {}
        error = data.get("error", "")
        return base.Event(
            native,
            data.get("prompt", ""),
            data.get("key", ""),
            error=error,
            transient=error.split(":")[0] in TRANSIENT,
            output_ignored=data.get("output_ignored", False),
            continued=data.get("continued", False),
        )

    def first_hook_blocker(self, cwd: str, env: dict[str, str]) -> base.Blocker:
        # The fake agent asks first when its environment says so (fake_agent.py).
        if env.get("FAKE_AGENT_ASKS_FIRST") == "1":
            return base.Blocker(reason=ASKS_FIRST)
        return base.Blocker()

    def continue_output(self, text: str) -> str | None:
        return text


ASKS_FIRST = 'Fake agent asks a question first: type "yes" in its terminal'


# "fake" gets queued messages from its turn-end hook and confirms them by its prompt-submit
# hook, like OpenCode and Kilo; "fake-stop" by the next turn's end, like Claude Code;
# "fake-paste" has them typed into its window.
FAKES = (
    FakeProvider("fake", True),
    FakeProvider("fake-stop", True, says_continued=True),
    FakeProvider("fake-paste", False),
)


def register(registry: dict[str, base.Provider]) -> None:
    registry.update({p.name: p for p in FAKES})


if __name__ == "__main__":
    register(providers._PROVIDERS)
    sys.exit(cli.main())
