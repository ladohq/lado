"""Kilo CLI as a LADO provider, a fork of OpenCode (see lado.providers.opencode_family).

The agent's config goes in through KILO_CONFIG_CONTENT.
"""

from pathlib import Path

from lado.providers import opencode_family

# The plugin API is Kilo-internal and changes between releases: `lado doctor` warns when the
# installed Kilo is not this version. `kilo debug skill` (7.8.3, with a KILO_CONFIG of its
# own) finds **/SKILL.md at any depth under skills.paths: the lead's lead-files
# (AgentSpec.read, lado.runtime) are kept out of skills.paths and only readable.
TESTED_VERSION = "7.8"


class KiloProvider(opencode_family.OpenCodeFamily):
    name = "kilo"
    title = "Kilo CLI"
    command = "kilo"
    install_hint = "install it: `npm install -g @kilocode/cli`"
    tested_version = TESTED_VERSION
    config_file_name = "kilo.json"
    # How launch_command maps them (checked with `kilo agent list`, Kilo 7.8.1): Kilo's
    # default agent edits without asking and asks before bash, which is acceptEdits as is.

    def permission(self, mode, spec):
        permission = super().permission(mode, spec)
        if mode == "default":
            permission["edit"] = "ask"  # Kilo's default agent edits without asking
        return permission

    def bypass_argv(self) -> list[str]:
        return ["--auto"]

    def env(self, config_file: Path, config_text: str) -> dict[str, str]:
        # A running `kilo daemon` would serve the agent with its own config, not this one.
        # The config as text: a KILO_CONFIG file loses to the repo's own kilo.json, the text
        # wins over it (`kilo debug config`, Kilo 7.8.3).
        return {
            "KILO_NO_DAEMON": "1",
            "KILO_CONFIG_CONTENT": config_text,
            "KILO_DISABLE_AUTOUPDATE": "1",
        }
