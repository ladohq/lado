"""lado.uninstall: the plan, the stops, the repositories by finish's rule, LADO_HOME's
deletion and the program's removal; real git, tmux and the UI server replaced."""

import fcntl
import os
import shutil
import sqlite3
import sys
from pathlib import Path

import agent_helpers
import pytest
from agent_helpers import init_repo

from lado import __version__, loop, runtime, self_update, state, tmux, uninstall
from lado.server import run as server_run


@pytest.fixture
def tmux_server(monkeypatch):
    """LADO's tmux server, recorded: `left` names the sessions still on its socket."""

    class Server:
        running = True
        left: list[str] = []
        killed = False

    server = Server()
    monkeypatch.setattr(tmux, "server_running", lambda sock=None: server.running)
    monkeypatch.setattr(tmux, "sessions_with", lambda *o: [[name] for name in server.left])

    def kill_server():
        server.killed = True

    monkeypatch.setattr(tmux, "kill_server", kill_server)
    return server


@pytest.fixture
def no_program(tmp_path, monkeypatch):
    """This LADO in a prefix of the test's with no installer's files."""
    prefix = tmp_path / "prefix"
    prefix.mkdir()
    monkeypatch.setenv("LADO_UPDATE_PREFIX", str(prefix))
    return prefix


@pytest.fixture
def ui_server(monkeypatch):
    """A UI server that runs until it is stopped."""
    info = {"host": "127.0.0.1", "port": 8123, "url": "http://127.0.0.1:8123", "pid": 1}
    calls = []
    server_run.lock_path().touch()
    monkeypatch.setattr(server_run, "running", lambda: None if calls else info)
    monkeypatch.setattr(server_run, "stop", lambda: calls.append("stop") or info)
    return calls


def said() -> tuple[list[str], callable]:
    lines: list[str] = []
    return lines, lambda text="", **_: lines.append(text)


def commit(worktree, name="work.txt"):
    Path(worktree, name).write_text("done\n")
    runtime.git(str(worktree), "add", name)
    runtime.git(str(worktree), "commit", "-q", "-m", f"add {name}")


def branches(repo) -> list[str]:
    return runtime.git(str(repo), "branch", "--format=%(refname:short)").split()


@pytest.fixture
def workers(repo, fake_tmux, no_program, tmux_server):
    """Session "s" in `repo` with a merged worker `dev` and an unmerged worker `rev`."""
    runtime.start_session(str(repo), "s", None, provider="claude")
    dev = runtime.spawn_worker("s", "task", name="dev")
    rev = runtime.spawn_worker("s", "task", name="rev")
    commit(dev.cwd, "dev.txt")
    runtime.git(str(repo), "merge", "-q", "--ff-only", dev.branch)
    commit(rev.cwd, "rev.txt")
    return dev, rev


def run(found: uninstall.Plan) -> tuple[int, list[str]]:
    lines, say = said()
    return uninstall.run(found, say), lines


# The plan


def test_the_plan_names_what_goes_and_what_stays(workers, repo, lado_home, ui_server, no_program):
    (no_program / "uv-receipt.toml").write_text('[tool]\nrequirements = [{ name = "lado" }]\n')
    lines, say = said()
    found = uninstall.plan()
    uninstall.print_plan(found, say)
    text = "\n".join(lines)
    assert text.startswith(
        f'LADO {__version__} will be uninstalled (tmux socket "{tmux.socket()}", '
        f"LADO_HOME {lado_home}):\n"
    )
    assert "Stop:\n  the UI server (http://127.0.0.1:8123)\n" in text
    assert '  session "s" (running: supervisor, dev, rev)\n' in text
    assert (
        f"Repositories:\n  {repo}\n"
        "    remove worktree .lado/worktrees/s/dev and branch lado/s/dev (merged)\n"
        "    keep   worktree .lado/worktrees/s/rev and branch lado/s/rev: not merged into main\n"
    ) in text
    assert f"Delete:\n  {lado_home} (" in text
    assert "Keep the program: LADO_HOME is not ~/.lado, which may still use it" in text
    assert text.endswith(
        "Agent CLIs keep their own records of these folders (e.g. Claude Code's "
        "~/.claude.json): see docs/install.md, Uninstall."
    )


def snapshot(*folders: Path) -> dict:
    """Each file's and folder's bytes and mode, under the folders: what a dry run must not
    change (SQLite's -shm of a read is its own)."""
    found = {}
    for folder in folders:
        for root, dirs, files in os.walk(folder):
            for name in dirs + files:
                path = Path(root, name)
                if name.endswith("-shm"):
                    continue
                found[str(path)] = path.read_bytes() if path.is_file() else path.stat().st_mode
    return found


def test_a_dry_runs_plan_changes_nothing(workers, repo, lado_home, ui_server, capsys):
    from lado.cli import main

    before = snapshot(lado_home, repo)
    git_before = (branches(repo), runtime.git(str(repo), "worktree", "list"))
    assert main(["uninstall", "--dry-run"]) == 0
    assert "Uninstall?" not in capsys.readouterr().out
    assert snapshot(lado_home, repo) == before
    assert (branches(repo), runtime.git(str(repo), "worktree", "list")) == git_before
    assert ui_server == [] and not state.get_session("s").stopped_at


def test_a_newer_database_is_refused_before_the_plan(lado_home, no_program):
    lado_home.mkdir(exist_ok=True)
    with sqlite3.connect(lado_home / "lado.db") as db:
        db.execute(f"PRAGMA user_version = {state.SCHEMA_VERSION + 1}")
    with pytest.raises(runtime.LadoError, match="made by a newer LADO.*docs/install.md"):
        uninstall.plan()


def test_an_older_database_is_shown_read_only_and_upgraded_by_the_stop(
    repo, fake_tmux, no_program, tmux_server, lado_home
):
    runtime.start_session(str(repo), "s", None, provider="claude")
    agent_helpers.previous_schema()
    with sqlite3.connect(lado_home / "lado.db") as db:
        db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    before = (lado_home / "lado.db").read_bytes()
    lines, say = said()
    found = uninstall.plan(keep_data=True)
    uninstall.print_plan(found, say)
    assert (lado_home / "lado.db").read_bytes() == before
    older = state.SCHEMA_VERSION - 1
    assert f"lado.db (schema {older}) is upgraded first, as lado stop --all does" in lines
    assert '  session "s" (running)' in lines
    assert run(found)[0] == 0
    assert state.schema_version() == state.SCHEMA_VERSION  # the stop migrated it
    assert state.get_session("s").stopped_at


def test_without_a_database_the_plan_has_the_folder_and_the_program(
    lado_home, no_program, tmux_server
):
    lines, say = said()
    found = uninstall.plan()
    uninstall.print_plan(found, say)
    assert found.sessions == [] and found.repos == []
    assert "Stop:\n  nothing runs" in "\n".join(lines)
    assert not (lado_home / "lado.db").exists()


@pytest.fixture
def user_home(tmp_path, monkeypatch, no_program):
    """HOME at a folder of the test's, LADO_HOME not set: ~/.lado is the default home."""
    home = tmp_path / "user"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("LADO_HOME")
    return home


def test_the_default_home_is_lado_home_unset_or_at_lado_by_its_real_path(
    user_home, monkeypatch, tmp_path
):
    assert uninstall.plan().default_home
    link = tmp_path / "link"
    link.symlink_to(user_home)
    monkeypatch.setenv("LADO_HOME", str(link / ".lado"))
    assert uninstall.plan().default_home
    monkeypatch.setenv("LADO_HOME", str(tmp_path / "try"))
    assert not uninstall.plan().default_home


@pytest.mark.parametrize(
    "where, why",
    [
        ("home", "it is your home folder"),
        ("root", "it is / or a folder above your home folder"),
        ("above", "it is / or a folder above your home folder"),
        ("empty", "it holds no lado.db"),
    ],
)
def test_a_guarded_lado_home_is_planned_as_kept(user_home, monkeypatch, tmp_path, where, why):
    folder = {
        "home": user_home,
        "root": Path("/"),
        "above": user_home.parent,
        "empty": tmp_path / "other",
    }[where]
    monkeypatch.setenv("LADO_HOME", str(folder))
    monkeypatch.setattr(state, "home", lambda: folder)  # never made or written
    found = uninstall.plan()
    assert (found.home_kept, found.size) == (why, 0)  # never walked


# The run


def test_the_run_stops_everything_cleans_the_repository_and_deletes_the_home(
    workers, repo, lado_home, ui_server, tmux_server, fake_tmux
):
    dev, rev = workers
    (repo / ".lado" / "sdlc.md").write_text("# settings\n")
    code, lines = run(uninstall.plan())
    assert code == 0
    assert ui_server == ["stop"]
    assert ("kill_session", "s") in fake_tmux
    assert tmux_server.killed
    assert not Path(dev.cwd).exists() and "lado/s/dev" not in branches(repo)
    assert Path(rev.cwd).exists() and "lado/s/rev" in branches(repo)
    assert (repo / ".lado" / "sdlc.md").read_text() == "# settings\n"
    assert "/.lado/worktrees/" in (repo / ".git" / "info" / "exclude").read_text()
    assert not lado_home.exists()
    assert lines[:3] == ["Stopped the UI server", 'Stopped session "s"', "Ended LADO's tmux server"]
    assert f"Removed worktree {dev.cwd} and branch lado/s/dev" in lines
    assert f"Kept worktree {rev.cwd} and branch lado/s/rev: not merged into main" in lines
    assert f"Deleted {lado_home}" in lines
    left = lines[lines.index("Left on this machine:") :]
    assert left[1:4] == [
        f"  {repo}: worktree .lado/worktrees/s/rev, branch lado/s/rev",
        f"    git -C '{repo}' worktree remove --force '{rev.cwd}'",
        f"    git -C '{repo}' branch -D lado/s/rev",
    ]


def test_the_repository_without_worktrees_loses_lados_folder_and_line(
    repo, fake_tmux, no_program, tmux_server, lado_home
):
    runtime.start_session(str(repo), "s", None, provider="claude")
    runtime.spawn_worker("s", "task", name="dev")
    (repo / ".lado" / "sdlc.md").write_text("# settings\n")
    assert run(uninstall.plan())[0] == 0
    assert not (repo / ".lado" / "worktrees").exists()
    assert (repo / ".lado" / "sdlc.md").read_text() == "# settings\n"
    assert "/.lado/worktrees/" not in (repo / ".git" / "info" / "exclude").read_text()
    assert branches(repo) == ["main"]
    assert runtime.git(str(repo), "worktree", "list").count("\n") == 0


def test_an_empty_lado_folder_goes_too(repo, fake_tmux, no_program, tmux_server):
    runtime.start_session(str(repo), "s", None, provider="claude")
    runtime.spawn_worker("s", "task", name="dev")
    assert run(uninstall.plan())[0] == 0
    assert not (repo / ".lado").exists()


def test_another_homes_worktrees_keep_lados_folder_and_line(
    repo, fake_tmux, no_program, tmux_server
):
    runtime.start_session(str(repo), "s", None, provider="claude")
    runtime.spawn_worker("s", "task", name="dev")
    other = repo / ".lado" / "worktrees" / "other" / "w"
    runtime.git(str(repo), "worktree", "add", "-q", "-b", "lado/other/w", str(other))
    assert run(uninstall.plan())[0] == 0
    assert other.exists() and "lado/other/w" in branches(repo)
    assert not (repo / ".lado" / "worktrees" / "s").exists()
    assert "/.lado/worktrees/" in (repo / ".git" / "info" / "exclude").read_text()


def test_a_branch_without_worktree_and_dirty_work_are_judged_alike(
    repo, fake_tmux, no_program, tmux_server
):
    runtime.start_session(str(repo), "s", None, provider="claude")
    dirty = runtime.spawn_worker("s", "task", name="dirty")
    Path(dirty.cwd, "draft.txt").write_text("x")
    runtime.git(str(repo), "branch", "lado/s/merged")
    runtime.git(str(repo), "branch", "lado/s/ahead")
    runtime.git(str(repo), "checkout", "-q", "lado/s/ahead")
    commit(repo, "ahead.txt")
    runtime.git(str(repo), "checkout", "-q", "main")
    code, lines = run(uninstall.plan())
    assert code == 0
    assert f"Kept worktree {dirty.cwd} and branch lado/s/dirty: uncommitted changes" in lines
    assert "Removed branch lado/s/merged" in lines
    assert "Kept branch lado/s/ahead: not merged into main" in lines
    assert sorted(branches(repo)) == ["lado/s/ahead", "lado/s/dirty", "main"]


def test_work_is_judged_again_after_the_stop(workers, repo):
    dev, rev = workers
    found = uninstall.plan()
    commit(dev.cwd, "late.txt")  # the agent committed after the plan was shown
    code, lines = run(found)
    assert code == 1  # the plan meant to remove it
    assert f"Kept worktree {dev.cwd} and branch lado/s/dev: not merged into main" in lines
    assert Path(dev.cwd).exists()


def test_a_repository_that_is_gone_is_passed_over(
    repo, tmp_path, fake_tmux, no_program, tmux_server
):
    other = init_repo(tmp_path / "other")
    runtime.start_session(str(repo), "s", None, provider="claude")
    runtime.start_session(str(other), "t", None, provider="claude")
    runtime.spawn_worker("s", "task", name="dev")
    shutil.rmtree(other)
    lines, say = said()
    found = uninstall.plan()
    uninstall.print_plan(found, say)
    assert f"  {other}: no longer there, passed over" in lines
    code, done = run(found)
    assert code == 0
    assert f"Passed over {other}: no longer there" in done
    assert not (repo / ".lado" / "worktrees").exists()


def test_a_loop_that_does_not_end_stops_before_the_repositories(
    workers, repo, lado_home, monkeypatch
):
    dev, _ = workers
    monkeypatch.setattr(loop, "wait_stopped", lambda session, timeout=None: False)
    code, lines = run(uninstall.plan())
    assert code == 1
    assert lines[-1] == (
        'lado: the loop of session "s" did not end (LADO_HOME/loop/s.lock is held); no '
        "repository or file was touched: run lado uninstall again"
    )
    assert Path(dev.cwd).exists() and lado_home.exists()


def test_an_update_that_runs_refuses_the_uninstall(workers, lado_home):
    with open(self_update.lock_path(), "a+") as held:
        fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
        held.write("4242")
        held.flush()
        with pytest.raises(runtime.LadoError, match="an update is running, pid 4242"):
            uninstall.plan()
    found = uninstall.plan()
    with open(self_update.lock_path(), "a+") as held:
        fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(uninstall.UninstallRefused, match="an update is running"):
            run(found)
    assert not state.get_session("s").stopped_at and lado_home.exists()


def test_the_tmux_server_with_another_homes_sessions_is_kept(workers, tmux_server):
    tmux_server.left = ["elsewhere"]
    code, lines = run(uninstall.plan())
    assert code == 0 and not tmux_server.killed
    assert (
        f'Kept LADO\'s tmux server (socket "{tmux.socket()}"): sessions of another LADO_HOME '
        "run there: elsewhere"
    ) in lines


def test_a_file_that_cannot_be_deleted_is_named(workers, lado_home):
    locked = lado_home / "locked"
    locked.mkdir()
    (locked / "file").write_text("x")
    locked.chmod(0o500)
    try:
        code, lines = run(uninstall.plan())
    finally:
        locked.chmod(0o700)
    assert code == 1
    assert any(line.startswith(f"lado: could not delete {locked / 'file'}: ") for line in lines)


def hold_send_lock(seconds: float | None):
    """A statistics sender (`lado telemetry send`) that runs `seconds`, or on (None)."""
    import threading

    from lado import telemetry

    telemetry.folder().mkdir(parents=True, exist_ok=True)
    lock = open(telemetry.folder() / "send.lock", "a")
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    if seconds is not None:
        threading.Timer(seconds, lock.close).start()
    return lock


def test_a_running_statistics_sender_is_waited_for_before_the_home_goes(workers, lado_home):
    hold_send_lock(0.3)
    code, lines = run(uninstall.plan())
    assert code == 0 and not lado_home.exists()


def test_a_statistics_sender_that_does_not_end_keeps_the_home(workers, lado_home, monkeypatch):
    monkeypatch.setattr(uninstall, "SENDER_WAIT", 0.2)
    lock = hold_send_lock(None)
    try:
        code, lines = run(uninstall.plan())
    finally:
        lock.close()
    assert code == 1 and lado_home.exists()
    assert (
        f"lado: kept {lado_home}: LADO's statistics sender still runs "
        "(LADO_HOME/telemetry/send.lock is held); run lado uninstall again"
    ) in lines


def test_a_guarded_home_is_kept_with_exit_1(user_home, monkeypatch, tmux_server):
    monkeypatch.setenv("LADO_HOME", str(user_home))
    (user_home / "mine.txt").write_text("x")
    code, lines = run(uninstall.plan())
    assert code == 1
    assert f"lado: kept {user_home}: it is your home folder" in lines
    assert (user_home / "mine.txt").exists()


# The program


@pytest.fixture
def remover(tmp_path, monkeypatch):
    """A remover that writes down its argv and whether ~/.lado was still there."""
    seen = tmp_path / "remover-seen"
    script = tmp_path / "remover"
    script.write_text(
        f'#!/bin/sh\necho "$* home=$([ -d "$HOME/.lado" ] && echo yes || echo no)" > "{seen}"\n'
        'echo "removed lado"\nexit "${REMOVER_EXIT:-0}"\n'
    )
    script.chmod(0o755)
    monkeypatch.setenv("LADO_UNINSTALL_REMOVER", f"{script} tool uninstall lado")
    return seen


def test_the_default_homes_program_goes_last(user_home, remover, tmux_server):
    state.home()  # ~/.lado made
    found = uninstall.plan()
    lines, say = said()
    uninstall.print_plan(found, say)
    assert "Remove the program:" in lines
    code, done = run(found)
    assert code == 0
    assert remover.read_text() == "tool uninstall lado home=no\n"
    assert done[-3:] == [
        f"Removing the program: {os.environ['LADO_UNINSTALL_REMOVER']}",
        "removed lado",
        "Uninstalled lado",
    ]


def test_a_uv_tool_install_is_removed_with_uv(user_home, tmux_server, no_program):
    (no_program / "uv-receipt.toml").write_text('[tool]\nrequirements = [{ name = "lado" }]\n')
    assert uninstall.plan().remover == ["uv", "tool", "uninstall", "lado"]


def test_another_homes_program_stays_with_its_command(workers, lado_home, no_program, monkeypatch):
    (no_program / "uv-receipt.toml").write_text('[tool]\nrequirements = [{ name = "lado" }]\n')
    code, lines = run(uninstall.plan())
    assert code == 0
    assert (
        "Kept the program: LADO_HOME is not ~/.lado, which may still use it; remove it with: "
        "uv tool uninstall lado"
    ) in lines
    assert "  uv tool uninstall lado" in lines[lines.index("Left on this machine:") :]


def test_a_working_copys_program_stays(user_home, no_program, tmux_server):
    code, lines = run(uninstall.plan())
    assert code == 0
    assert (
        f"Kept the program: LADO runs from {no_program}, not a uv tool or pipx install: "
        "remove it the way you installed it (pip uninstall lado in that environment)"
    ) in lines


def test_a_failing_remover_is_named_with_exit_1(user_home, remover, tmux_server, monkeypatch):
    monkeypatch.setenv("REMOVER_EXIT", "3")
    code, lines = run(uninstall.plan())
    assert code == 1
    command = os.environ["LADO_UNINSTALL_REMOVER"]
    assert lines[-1] == f"lado: the program was not removed (exit code 3): run {command}"


def test_nothing_is_imported_after_the_remover(user_home, remover, tmux_server, monkeypatch):
    """The remover deletes the package under the running uninstall: what follows it needs
    no import."""

    class NoImports:
        def find_spec(self, name, path=None, target=None):
            raise ImportError(f"imported after the remover: {name}")

    real = self_update.command

    def remove_then_forbid(argv, say):
        sys.meta_path.insert(0, NoImports())
        return real(argv, say)

    monkeypatch.setattr(self_update, "command", remove_then_forbid)
    try:
        code, lines = run(uninstall.plan())
    finally:
        sys.meta_path[:] = [f for f in sys.meta_path if not isinstance(f, NoImports)]
    assert code == 0 and lines[-1] == "Uninstalled lado"


def test_keep_data_stops_and_removes_the_program_but_keeps_the_data(
    user_home, remover, repo, fake_tmux, tmux_server
):
    runtime.start_session(str(repo), "s", None, provider="claude")
    dev = runtime.spawn_worker("s", "task", name="dev")
    found = uninstall.plan(keep_data=True)
    lines, say = said()
    uninstall.print_plan(found, say)
    assert "Keep (--keep-data): LADO_HOME and the repositories as they are" in lines
    code, done = run(found)
    assert code == 0
    assert state.get_session("s").stopped_at
    assert Path(dev.cwd).exists() and "lado/s/dev" in branches(repo)
    assert (user_home / ".lado" / "lado.db").exists()
    assert remover.read_text() == "tool uninstall lado home=yes\n"
