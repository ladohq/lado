"""The OpenCode family: OpenCode and its forks (Kilo CLI) as LADO providers.

They have no command hooks, so LADO ships a small plugin (opencode_plugin.js) that runs
`lado hook <event>` for the CLI's own events. Each agent gets one config dict: it is written
to the agent's config folder and goes to the CLI through the environment (`env`).

Forks drift apart. This base holds only what is checked on every CLI of the family, with the
CLI and version it was checked on; what is checked on one CLI only lives in its subclass. A
subclass overrides a method where its CLI differs; once a subclass overrides more than half
of `launch_command`'s steps, split this base instead.
"""

import json
from abc import abstractmethod
from pathlib import Path

from lado import state
from lado.providers import base

PLUGIN = Path(__file__).with_name("opencode_plugin.js")

# Events the plugin reports and the neutral events they stand for, by the same names in Kilo
# 7.8.3 and OpenCode 1.18.34. A request for the human and its answer carry the request's id
# (the plugin's "id"), also a subagent's; a refused permission is "permission.replied" too
# (neither has a "permission.rejected"). Both can have several requests open at once (listed
# per session); LADO keeps one key, the latest request's (BACKLOG.md: a set of keys).
EVENTS = {
    "plugin.init": base.SESSION_START,
    "chat.message": base.PROMPT_SUBMIT,
    "session.idle": base.TURN_END,
    "permission.asked": base.WAITING,
    "permission.replied": base.RESUMED,
    "question.asked": base.WAITING,
    "question.replied": base.RESUMED,
    "question.rejected": base.RESUMED,
    "dispose": base.SESSION_END,
    # The plugin's own: it could not hand the turn-end hook's output on (promptAsync
    # failed), with the error as a "session.idle"'s.
    "plugin.error": base.HOOK_ERROR,
}
# A turn that ends on an error: the plugin passes the "session.error" before "session.idle"
# on with it (Kilo 7.8.3 and OpenCode 1.18.34 publish one, then the other, read in their
# bundles). The human's Esc is an error too, this one, which their TUIs do not show either.
# No error is Event.transient: the plugin gets only the error's class name and message (an
# overloaded API and a refused key are both an APIError), and which ones reach
# "session.error" is not checked (BACKLOG.md), so LADO resumes none of their agents.
ABORTED = "MessageAbortedError"


class OpenCodeFamily(base.Provider):
    plugin = PLUGIN
    config_file_name: str  # the agent's config in its config folder, e.g. "opencode.json"
    capabilities = base.Capabilities(
        status_events=True, permission_event=True, deliver_on_turn_end=True, skills=True
    )
    permission_modes = ("default", "acceptEdits", "bypassPermissions", "plan")

    def launch_command(
        self,
        agent: state.Agent,
        session: state.Session,
        spec: base.AgentSpec,
    ) -> base.Launch:
        config_dir = base.config_dir(agent)
        role = config_dir / "role.md"
        role.write_text(spec.prompt)
        config = self.config(agent, session.permission_mode, spec, role)
        text = json.dumps(config, indent=2)
        config_file = config_dir / self.config_file_name
        config_file.write_text(text)
        return base.Launch(self.argv(session.permission_mode), self.env(config_file, text))

    def config(
        self, agent: state.Agent, mode: str | None, spec: base.AgentSpec, role: Path
    ) -> dict:
        events = list(EVENTS)
        if mode == "bypassPermissions":
            # --auto approves each permission at once, with no dialog: not a wait (Kilo
            # 7.8.3, which still announces them; OpenCode 1.18.34, checked by hand in a
            # session of mode bypassPermissions, see opencode.py).
            events.remove("permission.asked")
            events.remove("permission.replied")
        config = {
            "instructions": [str(role)],
            # A local server gets the CLI's whole environment, the agent's, also names
            # `environment` does not list, AWS_SECRET_ACCESS_KEY included: a kit's secrets
            # reach it through lado.mcp_exec, never through this config. Both expand
            # {env:VAR} in the command, so the wrapper's args hold none (checked by hand
            # with Kilo 7.8.3 and OpenCode 1.18.34, `run` with the config in the env).
            "mcp": {
                name: {"type": "local", "command": s.command, "environment": s.env}
                for name, s in spec.mcp.items()
            },
            # Both find every **/SKILL.md under each path, at any depth (`kilo debug skill`,
            # Kilo 7.8.3, symlinks included; `opencode debug skill`, OpenCode 1.18.34): a
            # skill folder must hold no other skill. The links live under LADO_HOME, which
            # external_directory allows, so the agent can also read and run a skill's other
            # files.
            "skills": {
                "paths": [str(base.link_skills(base.config_dir(agent) / "skills", spec.skills))]
            },
            # The plugin gets the entry's options as its second argument (Kilo 7.8.3,
            # OpenCode 1.18.34).
            "plugin": [
                [self.plugin.as_uri(), {"hooks": {e: base.hook_argv(agent, e) for e in events}}]
            ],
            "permission": self.permission(mode, spec),
            # An update during a session can break the global install (Kilo 7.8.3 emptied it
            # once) and the plugin API: the agent's CLI must not update itself.
            "autoupdate": False,
            # Snapshots are the CLI's undo; git keeps the history in LADO's worktrees. On a
            # slow repo their setup asks "Continue with snapshots / Disable for this project"
            # and the agent waits for the human. The top-level boolean `snapshot` is in the
            # config schema of Kilo 7.8.1 and OpenCode 1.18.34; Kilo's Snapshot.track returns
            # before that dialog when it is false (read in the binary).
            "snapshot": False,
        }
        if mode == "plan":
            # The plan agent denies every tool it does not list, LADO's MCP tools too (Kilo
            # 7.8.1); its own rules come after the global ones (`opencode debug agent plan`,
            # OpenCode 1.18.34), so this allow wins.
            config["agent"] = {"plan": {"permission": self.plan_permission()}}
        return config

    def plan_permission(self) -> dict:
        """The plan agent's own rules; a subclass adds what its plan agent lacks."""
        return {"lado_*": "allow"}

    def permission(self, mode: str | None, spec: base.AgentSpec) -> dict:
        """The agent's `permission` rules; a subclass adds what its modes ask."""
        # spec.read is read without asking too; it is not in skills.paths.
        readable = [state.home(), *spec.read]
        return {"external_directory": {f"{p}/**": "allow" for p in readable}}

    def argv(self, mode: str | None) -> list[str]:
        argv = [self.command]
        if mode == "bypassPermissions":
            argv += self.bypass_argv()
        elif mode == "plan":
            argv += ["--agent", "plan"]
        return argv

    @abstractmethod
    def bypass_argv(self) -> list[str]:
        """The arguments for bypassPermissions."""

    @abstractmethod
    def env(self, config_file: Path, config_text: str) -> dict[str, str]:
        """The CLI's environment: its config (the file or its text) and its switches."""

    def parse_event(self, native: str, payload: str) -> base.Event | None:
        if native not in EVENTS:
            return None
        data = json.loads(payload) if payload.strip() else {}
        error = data.get("error") or {}
        if error and error.get("name") != ABORTED:
            text = base.error_line(error.get("name") or "UnknownError", error.get("message", ""))
            return base.Event(EVENTS[native], error=text)
        return base.Event(EVENTS[native], data.get("prompt", ""), data.get("id") or "")

    def continue_output(self, text: str) -> str | None:
        # The plugin sends whatever the turn-end hook prints as the next user message
        # (promptAsync), for which "chat.message" runs as for typed text, so its lines
        # confirm the messages (Kilo 7.8.3 and OpenCode 1.18.34, read in their bundles; the
        # live test checks it). No turn end says it went on from the output (no
        # Event.continued).
        return text
