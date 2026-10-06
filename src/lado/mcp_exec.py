"""A kit's MCP server whose env refers to the agent's variables, started without them on disk.

A kit writes `${VAR}` in its MCP servers' env (kits.py). LADO does not put the values into
the agent's config: the CLI gets the server's command as
`python -m lado.mcp_exec --name <server> <templates> -- <command...>`, with only the
names in the config. The CLI starts it with its own environment, the agent's, which holds
the values; this fills the templates from it and execs the server.

The templates are one argument, JSON in base64, so that no CLI takes them for its own
substitution (Claude Code expands `${VAR}` in a server's args, OpenCode and Kilo
`{env:VAR}` and `{file:...}` anywhere in their config). Only the standard library: it runs
before every such server.
"""

import base64
import json
import os
import re
import sys
from collections.abc import Mapping

VARIABLE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


class Unset(Exception):
    def __init__(self, name: str):
        super().__init__(f"environment variable {name} is not set")
        self.name = name


def references(value: str) -> list[str]:
    """The variables `value` refers to as ${NAME}, in order."""
    return VARIABLE.findall(value)


def expand(templates: Mapping[str, str], environ: Mapping[str, str]) -> dict[str, str]:
    """`templates` with each ${NAME} taken from `environ`; Unset for one it lacks."""

    def replace(match: re.Match) -> str:
        name = match.group(1)
        if name not in environ:
            raise Unset(name)
        return environ[name]

    return {key: VARIABLE.sub(replace, value) for key, value in templates.items()}


def wrap(name: str, command: list[str], templates: Mapping[str, str]) -> list[str]:
    """The command that starts MCP server `name` with `templates` filled in its env."""
    encoded = base64.b64encode(json.dumps(dict(templates)).encode()).decode()
    return [sys.executable, "-m", "lado.mcp_exec", "--name", name, encoded, "--", *command]


def main(args: list[str]) -> None:
    if len(args) < 5 or args[0] != "--name" or args[3] != "--":
        sys.exit("usage: python -m lado.mcp_exec --name <server> <templates> -- <command...>")
    name, encoded, command = args[1], args[2], args[4:]
    templates = json.loads(base64.b64decode(encoded))
    try:
        values = expand(templates, os.environ)
    except Unset as exc:
        print(f"LADO: {exc} for MCP server {name}", file=sys.stderr)
        sys.exit(1)
    os.execvpe(command[0], command, {**os.environ, **values})


if __name__ == "__main__":
    main(sys.argv[1:])
