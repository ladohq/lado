"""`lado doctor`: check that the machine has what LADO needs."""

import os
import platform
import re
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass

from lado import __version__, agent_env, providers, terminal, tmux, update

OK = "ok"
INFO = "info"  # for the human to know; nothing to fix
WARN = "warn"  # worth a look, but LADO works
FAIL = "fail"  # LADO does not work until it is fixed


@dataclass
class Check:
    name: str
    level: str  # OK, INFO, WARN or FAIL
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
        return Check(name, FAIL, f"`{command}` not found on PATH", hint)
    return Check(name, OK, _tool_version(path, flag))


@dataclass
class ProviderStatus:
    """Whether a provider's CLI can run here, for `lado doctor` and the UI."""

    installed: bool
    version: str  # x.y.z from `<cli> --version`; "" when unknown
    detail: str  # that command's first line, or why there is none
    tested_version: str  # the version (or prefix) LADO is tested with; "" any
    warning: str  # "" unless the version is not the tested one


def provider_status(
    provider: providers.Provider, which: Callable[[str], str | None]
) -> ProviderStatus:
    tool = check_tool(provider.title, provider.command, "--version", "", which)
    tested = provider.tested_version
    if tool.level == FAIL:
        return ProviderStatus(False, "", tool.detail, tested, "")
    found = re.search(r"\d+\.\d+\.\d+", tool.detail)
    version = found[0] if found else ""
    warning = ""
    if tested and not (version == tested or version.startswith(tested + ".")):
        # A prefix ("7.8") stands for its versions; a full version only for itself.
        shown = tested if tested.count(".") == 2 else f"{tested}.x"
        warning = (
            f"LADO is tested with {provider.title} {shown}; with other versions "
            "agent status and message delivery may break"
        )
    return ProviderStatus(True, version, tool.detail, tested, warning)


def check_providers(which: Callable[[str], str | None]) -> list[Check]:
    """No provider is required, but one is: a missing one is only `info`; with none
    installed there is one failed check with how to install each."""
    registry = [providers.get(name) for name in providers.names()]
    statuses = [provider_status(provider, which) for provider in registry]
    if not any(status.installed for status in statuses):
        hints = "; ".join(f"{p.title}: {p.install_hint}" for p in registry)
        return [Check("Agent CLI", FAIL, "no agent CLI installed", hints)]
    return [
        Check(p.title, INFO, s.detail, p.install_hint)
        if not s.installed
        else Check(p.title, WARN if s.warning else OK, s.detail, s.warning)
        for p, s in zip(registry, statuses, strict=True)
    ]


def check_tmux(which: Callable[[str], str | None]) -> Check:
    """tmux is required; an old one works without (bordered) gate popups and without agent
    terminals in the web UI."""
    hint = "install it: `brew install tmux` or `sudo apt install tmux`"
    check = check_tool("tmux", "tmux", "-V", hint, which)
    found = tmux.parse_version(check.detail) if check.level == OK else None
    missing = []
    if found and found < tmux.POPUP_VERSION:
        missing.append("no gate popups before tmux 3.2: gates show only in `lado ls`")
    if found and found < terminal.VERSION:
        missing.append("no agent terminals in the web UI before tmux 3.2 (attach -f ignore-size)")
    if missing:
        check.level = WARN
        check.hint = "; ".join(missing)
    elif found and found < tmux.POPUP_BORDER_VERSION:
        check.level = WARN
        check.hint = "gate popups have no coloured border before tmux 3.3"
    return check


def check_agent_env() -> Check:
    """Where agents' environment comes from; the login shell must give it, and soon."""
    name = "Agent environment"
    try:
        if agent_env.source() == agent_env.INHERIT:
            detail = f"from the process that starts each agent ({agent_env.SOURCE_VAR}=inherit)"
            return Check(name, OK, detail)
        _, seconds = agent_env.timed()
    except agent_env.AgentEnvError as exc:
        return Check(name, FAIL, str(exc))
    check = Check(
        name, OK, f"from your login shell {os.environ['SHELL']}, resolved in {seconds:.1f} s"
    )
    if seconds > agent_env.SLOW:
        check.level = WARN
        check.hint = (
            "each agent's start waits for your shell this long; make its startup files faster"
        )
    return check


def check_lado() -> Check:
    """This LADO's version and whether a newer one is out (update.check: once a day)."""
    checked = update.check()
    if checked is None:
        return Check("LADO", OK, f"{__version__} (no update check: LADO_NO_UPDATE_CHECK=1)")
    hints = [h for h in (update.available_line(checked), checked.error) if h]
    if hints:
        return Check("LADO", WARN, __version__, "; ".join(hints))
    return Check("LADO", OK, f"{__version__}, the latest version")


def run_checks(which: Callable[[str], str | None] = shutil.which) -> list[Check]:
    return [
        check_lado(),
        Check("Python", OK, platform.python_version()),
        check_tmux(which),
        check_agent_env(),
        *check_providers(which),
    ]


def main() -> int:
    checks = run_checks()
    for check in checks:
        mark = "FAIL" if check.level == FAIL else f"{check.level:<4}"
        print(f"[{mark}] {check.name}: {check.detail}")
        if check.hint:
            print(f"       {check.hint}")
    failed = [c for c in checks if c.level == FAIL]
    if failed:
        print(f"\n{len(failed)} check(s) failed.")
        return 1
    print("\nAll checks passed.")
    return 0
