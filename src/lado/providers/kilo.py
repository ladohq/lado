"""Kilo CLI as a LADO provider.

Kilo has no command hooks, so LADO ships a small plugin (kilo_plugin.js) that runs
`lado hook <event>` for Kilo's own events. The agent's config goes in through KILO_CONFIG.
"""

import json
from pathlib import Path

from lado import state
from lado.providers import base

# The plugin API is Kilo-internal and changes between releases: `lado doctor` warns when the
# installed Kilo is not this version. `kilo debug skill` (7.8.3, with a KILO_CONFIG of its
# own) finds **/SKILL.md at any depth under skills.paths: the lead's lead-files
# (AgentSpec.read, lado.runtime) are kept out of skills.paths and only readable.
TESTED_VERSION = "7.8"

PLUGIN = Path(__file__).with_name("kilo_plugin.js")

# Events the plugin reports and the neutral events they stand for. A request for the human
# and its answer carry the request's id (the plugin's "id"), also a subagent's; a refused
# permission is "permission.replied" too (Kilo 7.8 has no "permission.rejected"). Kilo can
# have several requests open at once (it lists them per session); LADO keeps one key, the
# latest request's (BACKLOG.md: a set of keys).
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
    # How launch_command maps them (checked with `kilo agent list`, Kilo 7.8.1): Kilo's
    # default agent edits without asking and asks before bash, which is acceptEdits as is.
    permission_modes = ("default", "acceptEdits", "bypassPermissions", "plan")

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
            events.remove("permission.replied")
        # spec.read is read without asking too; it is not in skills.paths.
        readable = [state.home(), *spec.read]
        permission: dict = {"external_directory": {f"{p}/**": "allow" for p in readable}}
        if mode == "default":
            permission["edit"] = "ask"  # Kilo's default agent edits without asking

        config = {
            "instructions": [str(role)],
            "mcp": {
                name: {"type": "local", "command": s.command, "environment": s.env}
                for name, s in spec.mcp.items()
            },
            # Kilo finds every **/SKILL.md under each path, at any depth (checked with
            # `kilo debug skill`, Kilo 7.8.3; symlinks included, 7.8.1): a skill folder must
            # hold no other skill. The links live under LADO_HOME, which external_directory
            # allows, so the agent can also read and run a skill's other files.
            "skills": {"paths": [str(base.link_skills(config_dir / "skills", spec.skills))]},
            "plugin": [[PLUGIN.as_uri(), {"hooks": {e: base.hook_argv(agent, e) for e in events}}]],
            "permission": permission,
            # An update during a session can break the global install (it emptied it once,
            # with 7.8.3) and the plugin API: the agent's Kilo must not update itself.
            "autoupdate": False,
            # Snapshots are Kilo's undo; git keeps the history in LADO's worktrees. On a slow
            # repo their setup asks "Continue with snapshots / Disable for this project" and
            # the agent waits for the human. Kilo 7.8.1's config schema has the top-level
            # boolean `snapshot`; Snapshot.track returns before that dialog when it is false,
            # and the dialog's "Disable" itself writes `snapshot: false` (read in the binary).
            "snapshot": False,
        }
        if mode == "plan":
            # The plan agent denies every tool it does not list, LADO's MCP tools too; its
            # own permission rules come after the built-in ones, so this allow wins.
            config["agent"] = {"plan": {"permission": {"lado_*": "allow"}}}
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
        return base.Event(EVENTS[native], data.get("prompt", ""), data.get("id") or "")

    def continue_output(self, text: str) -> str | None:
        # The plugin sends whatever the turn-end hook prints as the next user message.
        return text
