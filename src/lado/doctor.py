"""`lado doctor`: check that the machine has what LADO needs."""

import os
import platform
import re
import shlex
import shutil
import subprocess
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

import lado
from lado import agent_env, artifacts, kits, providers, runtime, state, terminal, tmux, update

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


def check_config_folders() -> Check:
    """An agent's config folder lives only while the agent runs; one that is left may hold
    an older LADO's kit MCP secrets, or a Codex agent's config.toml with what LADO carried
    from the user's Codex config (its model providers may hold keys)."""
    name = "Agent config folders"
    try:
        stray = runtime.stray_config_dirs()
    except (state.SchemaError, tmux.TmuxError) as exc:
        return Check(name, INFO, f"not checked: {exc}")
    if not stray:
        return Check(name, OK, "only those of running agents")
    paths = ", ".join(map(str, stray))
    return Check(
        name,
        WARN,
        f"left by agents that do not run (they may hold secrets): {paths}",
        f"remove them: rm -rf {shlex.join(map(str, stray))}",
    )


def check_artifacts() -> Check:
    """What the artifact store holds, and its content no record refers to that a forget
    would remove (from a crash, or a forget that could not remove it yet)."""
    name = "Artifacts"
    if state.schema_version() is None:
        return Check(name, OK, "none")  # no lado.db: the check makes none
    try:
        usage = artifacts.store().usage()
    except state.SchemaError as exc:
        return Check(name, INFO, f"not checked: {exc}")
    detail = (
        f"{_count(usage.artifacts, 'artifact')}, {_count(usage.records, 'record')}, "
        f"{_megabytes(usage.bytes)}"
    )
    if not usage.orphans:
        return Check(name, OK, detail)
    files = "file" if usage.orphans == 1 else "files"
    return Check(
        name,
        WARN,
        f"{detail}; {usage.orphans} {files} no record refers to ({_megabytes(usage.orphan_bytes)})",
        "removed by the next lado forget",
    )


def _count(n: int, what: str) -> str:
    return f"{n} {what}{'' if n == 1 else 's'}"


def _megabytes(size: int) -> str:
    return f"{size / 2**20:.1f} MB"


def check_lado() -> Check:
    """This LADO's version and whether a newer one is out (update.check: once a day)."""
    checked = update.check()
    if checked is None:
        return Check("LADO", OK, f"{lado.__version__} (no update check: LADO_NO_UPDATE_CHECK=1)")
    hints = [h for h in (update.available_line(checked), checked.error) if h]
    if hints:
        return Check("LADO", WARN, lado.__version__, "; ".join(hints))
    return Check("LADO", OK, f"{lado.__version__}, the latest version")


@dataclass(frozen=True)
class KitFact:
    name: str
    version: str  # "" when it does not load
    origin: str  # "built-in", "<marketplace> marketplace", "git" or "folder": never a path


@dataclass
class System:
    """The facts of this machine and LADO the UI's system panel shows and `report` gives
    for an issue."""

    version: str
    python: str
    os: str
    machine: str
    installer: str | None  # update.Installer.kind, None without one
    home: str
    home_set: bool  # LADO_HOME is set
    schema: int | None  # lado.db's, None without one
    tmux: str  # its version, or why there is none
    tmux_socket: str
    providers: list[tuple[providers.Provider, ProviderStatus]]
    kits: list[KitFact]
    sessions: dict[str, int]  # running, stopped, gone
    check: update.Check | None
    last: update.Result | None


def _os_name() -> str:
    if platform.system() == "Darwin":
        return f"macOS {platform.mac_ver()[0]}"
    if platform.system() == "Linux":
        try:
            return platform.freedesktop_os_release()["PRETTY_NAME"]
        except (OSError, KeyError, AttributeError):  # AttributeError: Python 3.10
            return f"Linux {platform.release()}"
    return f"{platform.system()} {platform.release()}"


def _kit_facts() -> list[KitFact]:
    usable = state.schema_version() == state.SCHEMA_VERSION
    facts = []
    for found in [*(kits.installed_kits() if usable else []), *kits.builtin_kits()]:
        try:
            version = found.load().version or ""
        except kits.KitError:
            version = ""
        row = found.installed
        if row is None:
            origin = "built-in"
        elif row.marketplace:
            origin = f"{row.marketplace} marketplace"
        else:
            origin = "git" if row.address else "folder"
        facts.append(KitFact(found.name, version, origin))
    return facts


def _session_counts() -> dict[str, int]:
    counts = {"running": 0, "stopped": 0, "gone": 0}
    if state.schema_version() != state.SCHEMA_VERSION:
        return counts
    for sess in state.list_sessions():
        status = runtime.session_status(sess)
        if status == runtime.SessionStatus.STOPPED:
            counts["stopped"] += 1
        elif status == runtime.SessionStatus.TMUX_GONE:
            counts["gone"] += 1
        else:
            counts["running"] += 1
    return counts


def system_info(which: Callable[[str], str | None] = shutil.which) -> System:
    registry = [providers.get(name) for name in providers.names()]
    with ThreadPoolExecutor(len(registry)) as pool:  # each runs its `--version`
        statuses = list(pool.map(lambda p: provider_status(p, which), registry))
    tmux_check = check_tmux(which)
    found = tmux.parse_version(tmux_check.detail) if tmux_check.level != FAIL else None
    installer = update.installer()
    return System(
        version=lado.__version__,
        python=platform.python_version(),
        os=_os_name(),
        machine=platform.machine(),
        installer=installer.kind if installer else None,
        home=str(state.home()),
        home_set=bool(os.environ.get("LADO_HOME")),
        schema=state.schema_version(),
        tmux=tmux_check.detail.removeprefix("tmux ") if found else tmux_check.detail,
        tmux_socket=tmux.socket(),
        providers=list(zip(registry, statuses, strict=True)),
        kits=_kit_facts(),
        sessions=_session_counts(),
        check=update.check(),
        last=update.read_result(),
    )


def report(system: System, open_to_network: bool, up_seconds: float) -> str:
    """The system info as Markdown for an issue: no address, path, repository, session
    name, token or message (the human's rule), only whether the server is open to the
    network and whether LADO_HOME is set."""
    installer = system.installer or "no uv tool or pipx install"
    lines = [
        "### LADO system info",
        f"- LADO {system.version} ({installer}), Python {system.python}",
        f"- OS: {system.os} ({system.machine})",
        f"- Update: {_update_line(system.check)}",
        f"- Server: {'open to the network' if open_to_network else 'loopback only'}, "
        f"up {_duration(up_seconds)}, schema {system.schema if system.schema else 'none'}",
        f"- Home: {'LADO_HOME set' if system.home_set else 'default home'}",
        f"- tmux: {system.tmux}, socket {system.tmux_socket}",
        "- Providers:",
    ]
    for provider, status in system.providers:
        if not status.installed:
            lines.append(f"  - {provider.name}: not installed")
            continue
        tested = f" (tested {status.tested_version})" if status.tested_version else ""
        untested = ": untested version" if status.warning else ""
        lines.append(f"  - {provider.name}: {status.version or status.detail}{tested}{untested}")
    kits = ", ".join(
        f"{k.name}{' ' + k.version if k.version else ''} ({k.origin})" for k in system.kits
    )
    lines.append(f"- Kits: {kits or 'none'}")
    counts = system.sessions
    sessions = f"{counts['running']} running, {counts['stopped']} stopped"
    lines.append(f"- Sessions: {sessions}" + (f", {counts['gone']} gone" if counts["gone"] else ""))
    last = system.last
    if last and last.problem:
        lines.append(f"- Last update: {last.problem}")
    elif last:
        day = (last.ended_at or last.started_at)[:10]
        lines.append(f"- Last update: {last.from_} → {last.to}, {last.outcome} ({day})")
    return "\n".join(lines) + "\n"


def _update_line(checked: update.Check | None) -> str:
    if checked is None:
        return "no check (LADO_NO_UPDATE_CHECK=1)"
    when = checked.checked_at[:16].replace("T", " ")
    if checked.error:
        return f"the check failed ({when})"
    if checked.available:
        return f"{checked.available} available (checked {when})"
    return f"up to date (checked {when})"


def _duration(seconds: float) -> str:
    minutes = max(0, int(seconds)) // 60
    if minutes < 60:
        return f"{minutes} min"
    if minutes < 24 * 60:
        return f"{minutes // 60} h {minutes % 60} min"
    return f"{minutes // (24 * 60)} d {minutes // 60 % 24} h"


def run_checks(which: Callable[[str], str | None] = shutil.which) -> list[Check]:
    return [
        check_lado(),
        Check("Python", OK, platform.python_version()),
        check_tmux(which),
        check_agent_env(),
        check_config_folders(),
        check_artifacts(),
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
