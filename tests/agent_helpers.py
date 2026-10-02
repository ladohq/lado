"""Helpers for tests that run real agent processes: integration (fake agent) and live tests."""

import atexit
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

import pytest

from lado import log, loop, state, tmux

_template: Path | None = None  # the first repo made by this process, copied for the next ones

# git config that keeps git from starting gc or maintenance in the background after a command.
NO_MAINTENANCE = {"gc.auto": "0", "maintenance.auto": "false"}


def no_maintenance_env(environ: dict[str, str]) -> dict[str, str]:
    """`environ` plus GIT_CONFIG_* entries that apply NO_MAINTENANCE to every git command."""
    env = dict(environ)
    count = int(env.get("GIT_CONFIG_COUNT", "0"))
    for key, value in NO_MAINTENANCE.items():
        env[f"GIT_CONFIG_KEY_{count}"], env[f"GIT_CONFIG_VALUE_{count}"] = key, value
        count += 1
    env["GIT_CONFIG_COUNT"] = str(count)
    return env


def init_repo(path: Path) -> Path:
    """A git repo with one empty commit on main, and a committer for agents that commit.

    Most tests need one; git runs only for the first, the others are copies of it."""
    global _template
    if _template is None:
        _template = Path(tempfile.mkdtemp(prefix="lado-test-repo-"), "repo")
        atexit.register(shutil.rmtree, _template.parent, ignore_errors=True)
        _template.mkdir()
        git = ["git", "-C", str(_template)]
        subprocess.run([*git, "init", "-q", "-b", "main"], check=True)
        subprocess.run([*git, "config", "user.name", "LADO test"], check=True)
        subprocess.run([*git, "config", "user.email", "test@lado.invalid"], check=True)
        # No background gc or maintenance: it would hold lock files while we copy the repo.
        for key, value in NO_MAINTENANCE.items():
            subprocess.run([*git, "config", key, value], check=True)
        subprocess.run([*git, "commit", "-q", "--allow-empty", "-m", "init"], check=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    # A lock file is a git process at work, gone by the time a copy would need it.
    shutil.copytree(_template, path, symlinks=True, ignore=shutil.ignore_patterns("*.lock"))
    return path


def publish(work: Path, files: dict[str, str], tag: str | None = None) -> str:
    """Commit `files` in the repo `work` (made by init_repo), tag the commit, push it to a
    bare repo beside it (created on first use) and return the bare repo's file:// URL."""
    git = ["git", "-C", str(work)]
    for name, text in files.items():
        (work / name).parent.mkdir(parents=True, exist_ok=True)
        (work / name).write_text(text)
    subprocess.run([*git, "add", "-A"], check=True)
    subprocess.run([*git, "commit", "-q", "-m", "publish"], check=True)
    if tag:
        subprocess.run([*git, "tag", tag], check=True)
    remote = work.with_name(work.name + ".git")
    if not remote.exists():
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(remote)], check=True)
    subprocess.run([*git, "push", "-q", "--tags", str(remote), "main"], check=True)
    return remote.as_uri()


def previous_schema() -> None:
    """Turn the LADO_HOME database back to SCHEMA_VERSION - 1, as an older LADO left it.
    Undoes the last step of state.MIGRATIONS: change it with each new migration."""
    assert state.MIGRATIONS[state.SCHEMA_VERSION - 1] == [state.NOTES]
    with state.connect() as db:
        db.execute("DROP TABLE notes")
        db.execute(f"PRAGMA user_version = {state.SCHEMA_VERSION - 1}")


def refuse_unless_isolated() -> None:
    """These tests start and kill tmux servers and agents: never let them near a live LADO."""
    home = state.home().resolve()
    if not home.is_relative_to(Path(tempfile.gettempdir()).resolve()):
        pytest.exit(f"agent tests need LADO_HOME in a temp dir, not {home}", returncode=2)
    if not re.fullmatch(r"lado-test-[0-9a-f]{8}", tmux.socket()):
        pytest.exit(f"agent tests need a test tmux socket, not {tmux.socket()}", returncode=2)


# How long to wait for an agent before failing. Generous: a wait ends as soon as its check is
# true, and the tests run in parallel, often beside other agents' checks on a loaded machine,
# where starting an agent (two Python processes that import the MCP library) can take seconds.
TIMEOUT = 30


def wait_for(check, what: str, session: str, timeout: float = TIMEOUT, interval: float = 0.05):
    """Poll `check` until it returns something true, and return that."""
    deadline = time.monotonic() + timeout
    while not (result := check()):
        if time.monotonic() > deadline:
            pytest.fail(
                f"timed out after {timeout:g}s waiting for {what}; {last_state(session)}\n"
                f"{diagnostics(session)}"
            )
        time.sleep(interval)
    return result


def check_loop_ended_by_stop(session: str) -> None:
    """The session's latest line in loop.log says its loop ended for `lado stop`. Either
    reason counts: stop kills the tmux session, then marks the session stopped, and the loop
    may see either first."""
    path = state.home() / "loop.log"
    prefix = f" {session}: "
    lines = [
        line.split(prefix, 1)[1]
        for line in (path.read_text().splitlines() if path.exists() else [])
        if prefix in line
    ]
    last = lines[-1] if lines else "nothing"
    if last not in [f"loop ended: {reason}" for reason in (loop.STOPPED, loop.TMUX_GONE)]:
        pytest.fail(f"loop.log, last line of {session}: {last}")


def last_state(session: str) -> str:
    """One line: each agent's status and the last messages with their delivery state."""
    agents = ", ".join(f"{a.name} {a.status}" for a in state.list_agents(session)) or "none"
    messages = ", ".join(
        f"{m.sender} → {m.recipient} [{m.state}] {m.title!r}"
        for m in state.list_messages(session)[-5:]
    )
    return f"agents: {agents}; messages: {messages or 'none'}"


def keep_evidence(session: str, folder: Path) -> Path:
    """Copy into `folder` what shows why an agent test failed: `lado log` of the session,
    hooks.log, each agent's config folder and where it worked, and each tmux window's screen
    with its scrollback. Takes what is still there: a stopped session has no windows left."""
    folder.mkdir(parents=True)
    feed = log.Feed(session).read() if state.get_session(session) else []
    (folder / "lado-log.txt").write_text("".join(f"{log.format_entry(e)}\n" for e in feed))
    hooks_log = state.home() / "hooks.log"
    if hooks_log.exists():
        shutil.copy(hooks_log, folder / "hooks.log")
    configs = state.home() / "agents" / session
    if configs.is_dir():
        shutil.copytree(configs, folder / "agents", symlinks=True)
    (folder / "agents.txt").write_text(
        "".join(
            f"{a.name} {a.role} {a.status} cwd {a.cwd} branch {a.branch} "
            f"provider {a.provider} config {configs / a.name}\n"
            for a in state.list_agents(session)
        )
    )
    screens = folder / "screens"
    screens.mkdir()
    try:
        windows = tmux.run("list-windows", "-t", f"={session}", "-F", "#{window_name}").split()
        for window in windows:
            screen = tmux.run("capture-pane", "-p", "-S", "-2000", "-t", f"{session}:{window}")
            (screens / f"{window}.txt").write_text(screen)
    except tmux.TmuxError as exc:
        (screens / "error.txt").write_text(f"{exc}\n")
    return folder


def diagnostics(session: str) -> str:
    """The agents' windows, the hook log and the messages, to see why a wait failed."""
    out = []
    for agent in state.list_agents(session):
        out.append(f"--- {agent.name} ({agent.status})")
        try:
            out.append(tmux.capture(session, agent.name).rstrip())
        except tmux.TmuxError as exc:
            out.append(str(exc))
    log = state.home() / "hooks.log"
    if log.exists():
        out += ["--- hooks.log", log.read_text()]
    out.append("--- messages")
    out += [
        f"{m.sender} -> {m.recipient} [{m.state}] {m.title!r} {m.body[:200]!r}"
        for m in state.list_messages(session)
    ]
    out.append("--- events")
    out += [f"{e.agent}: {e.kind} {e.detail}" for e in state.list_events(session)]
    return "\n".join(out)
