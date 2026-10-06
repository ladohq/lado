"""How LADO starts a process of its own with its own Python: never importing from its cwd.

LADO's processes (hooks, `lado mcp`, `lado loop`, the popup, an agent's window command, the
MCP secrets wrapper) run in the agent's cwd, a repository LADO does not control. `python -m`
puts that cwd first on sys.path, so a `json.py` or a `lado/` there would run inside LADO with
the user's environment and keys. `-P` drops it only from Python 3.11 on, and `-I` also drops
PYTHONPATH and the user site, where a user's LADO may be installed. So the module is run by a
loader under `-c`, which drops the cwd (`''`, sys.path's first entry under `-c`, unless
PYTHONSAFEPATH left it out) before it imports anything but the built-in `sys`.
"""

import sys

# One line, so that `ps` shows the module and its arguments on the same line.
LOADER = (
    "import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; "
    "runpy.run_module(sys.argv.pop(1), run_name='__main__', alter_sys=True)"
)


def run_module(module: str, *args: str) -> list[str]:
    """`python -m module args...` with LADO's Python, without the cwd on sys.path."""
    return [sys.executable, "-c", LOADER, module, *args]
