"""A fake agent CLI as a LADO provider, for integration tests. Not shipped with LADO.

The fake agent (fake_agent.py) runs its hooks and MCP server in their own processes, which
must know the fake providers too. So run as a script, this file is `lado` with them registered.
"""

import dataclasses
import json
import sys
import time
from pathlib import Path

from lado import cli, providers, state
from lado.providers import base, claude

LADO = Path(__file__).resolve()
AGENT = LADO.with_name("fake_agent.py")
HOLD_LIMIT = 30  # seconds a held login status waits at most (FAKE_AGENT_LOGIN_HOLD)

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

    def __init__(
        self,
        name: str,
        deliver_on_turn_end: bool,
        says_continued: bool = False,
        output_taken_when_printed: bool = False,
    ):
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
            output_taken_when_printed=output_taken_when_printed,
            # It has no edit tools to take away: read-only agents run on it for the
            # repository check and LADO's command tools.
            deny_edit_tools=True,
        )

    def launch_command(
        self,
        agent: state.Agent,
        session: state.Session,
        spec: base.AgentSpec,
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
        return base.Launch([sys.executable, str(AGENT), str(config_file)])

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
            background=data.get("background", False),
        )

    def first_hook_blocker(self, cwd: str, env: dict[str, str]) -> base.Blocker:
        # The fake agent asks first when its environment says so (fake_agent.py); under
        # FAKE_AGENT_TRUST it asks as Claude Code does, so LADO records the trust as for
        # Claude Code, in the test's CLAUDE_CONFIG_DIR, and its lines name the fake agent.
        if env.get("FAKE_AGENT_ASKS_FIRST") == "1":
            return base.Blocker(reason=ASKS_FIRST)
        if env.get("FAKE_AGENT_TRUST") == "1":
            return claude.ClaudeProvider.first_hook_blocker(self, cwd, env)
        return base.Blocker()

    def continue_output(self, text: str) -> str | None:
        return text


ASKS_FIRST = 'Fake agent asks a question first: type "yes" in its terminal'

# The login of "fake-login" (lado.logins, lado.login_wait), like Claude Code's: logged in
# while the file FAKE_AGENT_LOGIN names exists (its own login file), or with FAKE_AGENT_TOKEN
# or FAKE_AGENT_KEY, in Claude Code's order (the key first); unknown with
# FAKE_AGENT_LOGIN_STATUS=unknown. It runs no login command: the page offers its choices.
LOGIN_SCRIPT = LADO.with_name("fake_login.py")
TOKEN, KEY = "FAKE_AGENT_TOKEN", "FAKE_AGENT_KEY"
FILE_WORDS = "the fake CLI's login file"


def _file_login(env: dict[str, str]) -> base.LoginStatus:
    marker = env.get("FAKE_AGENT_LOGIN")
    if marker and Path(marker).exists():
        return base.LoginStatus(base.YES, "fake login", file=marker, file_words=FILE_WORDS)
    return base.LoginStatus(base.NO)


CODE_HELP = "This window closes by itself once you are signed in."
CODE, CODE_LINK = "FAKE-C0DE7", "https://login.example.invalid/device"  # fake_login.py's


# "fake-login" logs in like Claude Code by a pasted token or key, and like Codex by a
# sign-in code: its choice "code" runs `fake_login.py --code` in the login window, which
# prints a link and a code in Codex's words, read as Codex's are, and writes its login file
# once the code is entered; "logout" removes that file.
class FakeLoginProvider(FakeProvider):
    login_variables = (TOKEN, KEY)
    login_question = "How do you pay for the fake agent?"
    login_choices = (
        base.LoginChoice("token", "A token", "Paste a fake token.", TOKEN),
        base.LoginChoice("key", "A key", "Paste a fake key.", KEY),
        base.LoginChoice("code", "A sign-in code", "Get a fake code.", action="login"),
    )

    def login_actions(self) -> tuple[base.LoginAction, ...]:
        script = (sys.executable, str(LOGIN_SCRIPT))
        return (
            base.LoginAction(
                "login", "Get a sign-in code", (*script, "--code"), CODE_HELP, shows_code=True
            ),
            base.LoginAction("logout", "Log out…", (*script, "--logout")),
        )

    def login_prompt(self, text: str) -> base.LoginPrompt | None:
        return providers.get("codex").login_prompt(text)

    def __init__(self, name: str):
        super().__init__(name, True)
        self.capabilities = dataclasses.replace(self.capabilities, needs_login=True)

    def needs_login(self, env) -> bool:
        # As Codex's model decides: a "local model" in the agents' environment needs none.
        return not env.get("FAKE_AGENT_LOCAL_MODEL")

    def login_status(self, env: dict[str, str]) -> base.LoginStatus:
        # A slow status command: it answers once the file FAKE_AGENT_LOGIN_HOLD names is
        # gone (at most HOLD_LIMIT seconds).
        hold, deadline = env.get("FAKE_AGENT_LOGIN_HOLD"), time.monotonic() + HOLD_LIMIT
        while hold and Path(hold).exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        if env.get("FAKE_AGENT_LOGIN_STATUS") == "unknown":
            return base.LoginStatus(base.UNKNOWN, problem="`fake auth status` timed out")
        if env.get(KEY):
            return base.LoginStatus(base.YES, "key", variable=KEY, choice="key")
        if env.get(TOKEN):
            return base.LoginStatus(base.YES, "token", variable=TOKEN, choice="token")
        found = _file_login(env)  # its own file: the sign-in code's, as Codex's ChatGPT login
        return dataclasses.replace(found, choice="code") if found.state == base.YES else found


# "fake-window" logs in by its own command, like OpenCode and Kilo: its login action
# (fake_login.py) prints a link, reads one line and writes the file FAKE_AGENT_LOGIN names,
# which logs "fake-login" in too (its own login file). Its agents need no login.
class FakeWindowProvider(FakeProvider):
    title = "Fake window agent"

    def login_status(self, env: dict[str, str]) -> base.LoginStatus:
        return _file_login(env)

    def login_actions(self) -> tuple[base.LoginAction, ...]:
        return (base.LoginAction("login", "Add a login…", (sys.executable, str(LOGIN_SCRIPT))),)


# "fake" gets queued messages from its turn-end hook and confirms them by its prompt-submit
# hook, like OpenCode and Kilo; "fake-stop" by the next turn's end, like Claude Code;
# "fake-paste" has them typed into its window; "fake-printed" as "fake-stop", and its CLI
# takes what the hook printed (output_taken_when_printed), like Claude Code and Codex;
# "fake-login" as "fake", and its agents need a login, like Claude Code's; "fake-window" as
# "fake", with a login command, like OpenCode's.
FAKES = (
    FakeProvider("fake", True),
    FakeProvider("fake-stop", True, says_continued=True),
    FakeProvider("fake-printed", True, says_continued=True, output_taken_when_printed=True),
    FakeProvider("fake-paste", False),
    FakeLoginProvider("fake-login"),
    FakeWindowProvider("fake-window", True),
)


def register(registry: dict[str, base.Provider]) -> None:
    registry.update({p.name: p for p in FAKES})


if __name__ == "__main__":
    register(providers._PROVIDERS)
    sys.exit(cli.main())
