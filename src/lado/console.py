"""The `lado` console script: refuses native Windows before `lado.cli` is imported.

`lado.cli` and the modules it imports need termios, fcntl and a pty, which native Windows
lacks, so the check runs here, in a module that imports nothing of LADO. LADO's own
processes (hooks, `lado mcp`, `lado loop`) run `lado.cli` directly
(`interpreter.run_module`): they never start on native Windows.
"""

import sys

NATIVE_WINDOWS = (
    "lado: native Windows is not supported; install and run LADO inside WSL2 "
    "(https://learn.microsoft.com/windows/wsl/install)"
)


def main(argv: list[str] | None = None) -> int:
    if sys.platform == "win32":
        print(NATIVE_WINDOWS, file=sys.stderr)
        return 1
    from lado import cli

    return cli.main(argv)
