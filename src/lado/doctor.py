"""`lado doctor`: check that the machine has what LADO needs."""

import platform
import re
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass

from lado import providers, terminal, tmux


@dataclass
class Check:
    name: str
    ok: bool
    detail: str
    hint: str = ""
    warning: bool = False  # worth a look, but LADO works


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


def check_provider(provider: providers.Provider, which: Callable[[str], str | None]) -> Check:
    """Only the default provider is required; the others are optional."""
    check = check_tool(provider.title, provider.command, "--version", provider.install_hint, which)
    if not check.ok:
        if provider.name != providers.DEFAULT:
            check.ok, check.warning = True, True
            check.hint += f" (needed only for --provider {provider.name})"
        return check
    found = re.search(r"\d+\.\d+\.\d+", check.detail)
    version = found[0] if found else ""
    tested = provider.tested_version
    if tested and not (version == tested or version.startswith(tested + ".")):
        # A prefix ("7.8") stands for its versions; a full version only for itself.
        shown = tested if tested.count(".") == 2 else f"{tested}.x"
        check.warning = True
        check.hint = (
            f"LADO is tested with {provider.title} {shown}; with other versions "
            "agent status and message delivery may break"
        )
    return check


def check_tmux(which: Callable[[str], str | None]) -> Check:
    """tmux is required; an old one works without (bordered) gate popups and without agent
    terminals in the web UI."""
    hint = "install it: `brew install tmux` or `sudo apt install tmux`"
    check = check_tool("tmux", "tmux", "-V", hint, which)
    found = tmux.parse_version(check.detail) if check.ok else None
    missing = []
    if found and found < tmux.POPUP_VERSION:
        missing.append("no gate popups before tmux 3.2: gates show only in `lado ls`")
    if found and found < terminal.VERSION:
        missing.append("no agent terminals in the web UI before tmux 3.2 (attach -f ignore-size)")
    if missing:
        check.warning = True
        check.hint = "; ".join(missing)
    elif found and found < tmux.POPUP_BORDER_VERSION:
        check.warning = True
        check.hint = "gate popups have no coloured border before tmux 3.3"
    return check


def run_checks(which: Callable[[str], str | None] = shutil.which) -> list[Check]:
    return [
        Check("Python", True, platform.python_version()),
        check_tmux(which),
        *(check_provider(providers.get(name), which) for name in providers.names()),
    ]


def main() -> int:
    checks = run_checks()
    for check in checks:
        mark = "FAIL" if not check.ok else "warn" if check.warning else "ok  "
        print(f"[{mark}] {check.name}: {check.detail}")
        if check.hint:
            print(f"       {check.hint}")
    failed = [c for c in checks if not c.ok]
    if failed:
        print(f"\n{len(failed)} check(s) failed.")
        return 1
    print("\nAll checks passed.")
    return 0
