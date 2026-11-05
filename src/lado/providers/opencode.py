"""OpenCode (the `opencode` CLI) as a LADO provider (see lado.providers.opencode_family).

The agent's config goes in through OPENCODE_CONFIG_CONTENT, which OpenCode merges after the
user's global config and the repo's own opencode.json (`opencode debug config`, 1.18.34):
LADO's keys win, the user's other settings stay.
"""

from pathlib import Path

from lado.providers import opencode_family

# The plugin API changes between releases: `lado doctor` warns when the installed OpenCode
# is not this version. Checked by hand in the TUI with 1.18.34: the question tool and a
# bash permission (mode `default`) make the agent `waiting`, answering there makes it
# `busy` again (question.asked/replied, permission.asked/replied).
TESTED_VERSION = "1.18"
# Any `plugin` entry makes OpenCode 1.18.35 wait for the install of @opencode-ai/plugin in its
# config folders, which npm retries: 72 s to the first request on a fresh HOME with outside
# traffic refused, 2.3 s with these, 2.1 s with no switches once the package is there. LADO's
# plugin imports nothing from it, and the user's config folder is not LADO's to fill.
NPM_SWITCHES = {"npm_config_fetch_retries": "0", "npm_config_fetch_timeout": "5000"}
PLUGIN_PACKAGE = Path("opencode", "node_modules", "@opencode-ai", "plugin")


class OpenCodeProvider(opencode_family.OpenCodeFamily):
    name = "opencode"
    title = "OpenCode"
    command = "opencode"
    install_hint = "install it: `npm install -g opencode-ai`"
    tested_version = TESTED_VERSION
    config_file_name = "opencode.json"
    # The fixed part of an agent's request is about 21K tokens on a real model (role, skills,
    # tools; 1.18.35, measured in the human's check), plus room to work.
    min_context = 32768
    # `opencode agent list`, 1.18.35, but compaction, summary and title.
    BUILT_IN_AGENTS = ("build", "plan", "general", "explore")
    # How launch_command maps them, against OpenCode's own defaults (`opencode debug agent
    # build`, 1.18.34): its default agent allows everything but external_directory and
    # doom_loop, which it asks about, so bash and edits run without asking; the plan agent
    # denies edits (but its plans) and allows bash. No mode keeps OpenCode's own defaults, as
    # with Kilo. `default` asks before edits and bash, `acceptEdits` before bash. `plan`
    # adds no global rule (a global `edit: ask` would come after the plan agent's deny and
    # let it edit) but asks before bash in the plan agent, whose own rules come last: plan
    # changes nothing unasked, as in Claude Code. `--auto` ("auto-approve permissions that
    # are not explicitly denied") approves the rest: checked by hand with 1.18.34, mode
    # bypassPermissions, a read outside the repo (external_directory: ask by default) ran
    # with no dialog and the agent never `waiting`.

    def plan_permission(self) -> dict:
        return {**super().plan_permission(), "bash": "ask"}

    def permission(self, mode, spec):
        permission = super().permission(mode, spec)
        if mode == "default":
            permission["edit"] = "ask"
        if mode in ("default", "acceptEdits"):
            permission["bash"] = "ask"
        return permission

    def server_env(self, spec):
        """npm's switches, on a model of a server (a closed network is its case) while the
        package is not in the config folder; a value of the user's stays."""
        if not spec.model or self.on_server(spec.model) is None:
            return {}
        home = spec.environ.get("HOME")
        config = spec.environ.get("XDG_CONFIG_HOME") or (home and str(Path(home, ".config")))
        if config and Path(config, PLUGIN_PACKAGE).exists():
            return {}
        return {name: v for name, v in NPM_SWITCHES.items() if name not in spec.environ}

    def bypass_argv(self) -> list[str]:
        return ["--auto"]

    def env(self, config_file: Path, config_text: str) -> dict[str, str]:
        return {"OPENCODE_CONFIG_CONTENT": config_text, "OPENCODE_DISABLE_AUTOUPDATE": "1"}
