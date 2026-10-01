"""`lado doctor`: check that the machine has what LADO needs."""

import platform
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass

from lado import providers


@dataclass
class Check:
    name: str
    ok: bool
    detail: str
    hint: str = ""


def _tool_version(path: str, flag: str) -> str:
    try:
        result = subprocess.run(
            [path, flag], capture_output=True, text=True, timeout=10, check=False
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f"found at {path}, but `{flag}` failed: {exc}"
    output = (result.stdout or result.stderr).strip().splitlines()
    return output[0] if output else f"found at {path}"


def check_tool(
    name: str, command: str, flag: str, hint: str, which: Callable[[str], str | None]
) -> Check:
    path = which(command)
    if path is None:
        return Check(name, False, f"`{command}` not found on PATH", hint)
    return Check(name, True, _tool_version(path, flag))


def run_checks(which: Callable[[str], str | None] = shutil.which) -> list[Check]:
    agent = providers.get(providers.DEFAULT)
    return [
        Check("Python", True, platform.python_version()),
        check_tool(
            "tmux",
            "tmux",
            "-V",
            "install it: `brew install tmux` or `sudo apt install tmux`",
            which,
        ),
        check_tool(agent.title, agent.command, "--version", agent.install_hint, which),
    ]


def main() -> int:
    checks = run_checks()
    for check in checks:
        mark = "ok  " if check.ok else "FAIL"
        print(f"[{mark}] {check.name}: {check.detail}")
        if check.hint:
            print(f"       {check.hint}")
    failed = [c for c in checks if not c.ok]
    if failed:
        print(f"\n{len(failed)} check(s) failed.")
        return 1
    print("\nAll checks passed.")
    return 0
