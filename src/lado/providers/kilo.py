"""Kilo CLI as a LADO provider.

Kilo has no command hooks, so LADO ships a small plugin (kilo_plugin.js) that runs
`lado hook <event>` for Kilo's own events. The agent's config goes in through KILO_CONFIG.
"""

import json
from pathlib import Path

from lado import state
from lado.providers import base

# The plugin API is Kilo-internal and changes between releases: `lado doctor` warns when the
# installed Kilo is not this version.
TESTED_VERSION = "7.8"

PLUGIN = Path(__file__).with_name("kilo_plugin.js")

# Events the plugin reports and the neutral events they stand for.
EVENTS = {
    "plugin.init": base.SESSION_START,
    "chat.message": base.PROMPT_SUBMIT,
    "session.idle": base.TURN_END,
    "permission.asked": base.WAITING,
    "question.asked": base.WAITING,
    "dispose": base.SESSION_END,
}


class KiloProvider(base.Provider):
    name = "kilo"
    title = "Kilo CLI"
    command = "kilo"
    install_hint = "install it: `npm install -g @kilocode/cli`"
    tested_version = TESTED_VERSION
    capabilities = base.Capabilities(
        status_events=True, permission_event=True, deliver_on_turn_end=True, skills=True
    )

    def launch_command(
        self,
        agent: state.Agent,
        session: state.Session,
        spec: base.AgentSpec,
        first_message: str | None = None,
    ) -> base.Launch:
        config_dir = base.config_dir(agent)
        role = config_dir / "role.md"
        role.write_text(spec.prompt)

        mode = session.permission_mode
        events = list(EVENTS)
        if mode == "bypassPermissions":
            # --auto still announces each permission and approves it at once: not a wait.
            events.remove("permission.asked")
        permission: dict = {"external_directory": {f"{state.home()}/**": "allow"}}
        if mode == "default":
            permission["edit"] = "ask"  # Kilo's default agent edits without asking

        config = {
            "instructions": [str(role)],
            "mcp": {
                name: {"type": "local", "command": s.command, "environment": s.env}
                for name, s in spec.mcp.items()
            },
            # Kilo finds <name>/SKILL.md under each path (checked with Kilo 7.8.1, symlinks
            # included). The links live under LADO_HOME, which external_directory allows, so
            # the agent can also read and run a skill's other files.
            "skills": {"paths": [str(base.link_skills(config_dir / "skills", spec.skills))]},
            "plugin": [[PLUGIN.as_uri(), {"hooks": {e: base.hook_argv(agent, e) for e in events}}]],
            "permission": permission,
            # An update during a session can break the global install (it emptied it once,
            # with 7.8.3) and the plugin API: the agent's Kilo must not update itself.
            "autoupdate": False,
        }
        config_file = config_dir / "kilo.json"
        config_file.write_text(json.dumps(config, indent=2))

        argv = [self.command]
        if first_message:
            argv += ["--prompt", first_message]
        if mode == "bypassPermissions":
            argv.append("--auto")
        elif mode == "plan":
            argv += ["--agent", "plan"]
        # A running `kilo daemon` would serve the agent with its own config, not this one.
        env = {
            "KILO_NO_DAEMON": "1",
            "KILO_CONFIG": str(config_file),
            "KILO_DISABLE_AUTOUPDATE": "1",
        }
        return base.Launch(argv, env)

    def parse_event(self, native: str, payload: str) -> base.Event | None:
        if native not in EVENTS:
            return None
        data = json.loads(payload) if payload.strip() else {}
        return base.Event(EVENTS[native], data.get("prompt", ""))

    def continue_output(self, text: str) -> str | None:
        # The plugin sends whatever the turn-end hook prints as the next user message.
        return text
