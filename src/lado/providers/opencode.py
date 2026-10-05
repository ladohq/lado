"""OpenCode (the `opencode` CLI) as a LADO provider (see lado.providers.opencode_family).

The agent's config goes in through OPENCODE_CONFIG_CONTENT, which OpenCode merges after the
user's global config and the repo's own opencode.json (`opencode debug config`, 1.18.34):
LADO's keys win, the user's other settings stay.
"""

from pathlib import Path

from lado.providers import opencode_family

# The plugin API changes between releases: `lado doctor` warns when the installed OpenCode
# is not this version.
TESTED_VERSION = "1.18"


class OpenCodeProvider(opencode_family.OpenCodeFamily):
    name = "opencode"
    title = "OpenCode"
    command = "opencode"
    install_hint = "install it: `npm install -g opencode-ai`"
    tested_version = TESTED_VERSION
    config_file_name = "opencode.json"
    # How launch_command maps them, against OpenCode's own defaults (`opencode debug agent
    # build`, 1.18.34): its default agent allows everything but external_directory and
    # doom_loop, which it asks about, so bash and edits run without asking; the plan agent
    # denies edits (but its plans) and allows bash. No mode keeps OpenCode's own defaults, as
    # with Kilo. `default` asks before edits and bash,
    # `acceptEdits` before bash, `plan` adds nothing: a global `edit: ask` would come after
    # the plan agent's deny and let it edit. `--auto` (1.18.34: "auto-approve permissions
    # that are not explicitly denied") approves the rest.

    def permission(self, mode, spec):
        permission = super().permission(mode, spec)
        if mode == "default":
            permission["edit"] = "ask"
        if mode in ("default", "acceptEdits"):
            permission["bash"] = "ask"
        return permission

    def bypass_argv(self) -> list[str]:
        return ["--auto"]

    def env(self, config_file: Path, config_text: str) -> dict[str, str]:
        return {"OPENCODE_CONFIG_CONTENT": config_text, "OPENCODE_DISABLE_AUTOUPDATE": "1"}
