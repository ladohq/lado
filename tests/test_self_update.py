"""lado.self_update: the update's lock, log, result file, lado.db's backup and the rollback,
with a fake install (its `bin/lado` a shell script) and tmux replaced by a recorder."""

import contextlib
import datetime
import fcntl
import json
import os
import shlex
import sqlite3
import stat
import sys
from pathlib import Path

import pytest
from agent_helpers import wheel

from lado import __version__, runtime, self_update, state, update
from lado.cli import main

NEW = "99.0.0"
TOKEN = "s3cret-t0ken"
LOGIN_LINK = f"http://127.0.0.1:8123/?token={TOKEN}"
BROKEN_NEW = f'$([ "$1" = "{NEW}" ] && echo "$1-broken" || echo "$1")'  # only NEW is wrong


class Install:
    """A fake install of LADO in a prefix of the test's: its `bin/lado` writes each call
    down, says the version a file holds for `--version` and fails the calls `fails` names;
    its installer writes the version it is given into that file, and the test says what
    else it does."""

    def __init__(self, folder, monkeypatch):
        self.prefix = folder / "prefix"
        (self.prefix / "bin").mkdir(parents=True)
        self.version_file = folder / "installed-version"
        self.version_file.write_text(__version__)
        self.calls = folder / "calls"
        self.failing = folder / "failing"
        self.failing.write_text("")
        lado = self.prefix / "bin" / "lado"
        lado.write_text(
            "#!/bin/sh\n"
            f'echo "$*" >> "{self.calls}"\n'
            'if [ "$1" = "--version" ]; then\n'
            f'  echo "lado $(cat "{self.version_file}")"; exit 0\n'
            "fi\n"
            f'if grep -qx "$1" "{self.failing}"; then echo "$1 failed here"; exit 1; fi\n'
            'echo "ran $1"\n'
            # `lado ui` prints its login link, token included.
            f'[ "$1" = "ui" ] && echo "{LOGIN_LINK}"\n'
            "exit 0\n"
        )
        lado.chmod(0o755)
        self.installer = folder / "installer"
        self.installs("")
        monkeypatch.setenv("LADO_UPDATE_PREFIX", str(self.prefix))
        monkeypatch.setenv("LADO_UPDATE_INSTALLER", str(self.installer))

    def installs(self, script: str, version: str = '"$1"') -> None:
        """The installer: `script`, then the installed version is `version` ($1 is the
        version it was given)."""
        self.installer.write_text(
            f'#!/bin/sh\necho "installing lado==$1"\n{script}\n'
            f'echo {version} > "{self.version_file}"\n'
        )
        self.installer.chmod(0o755)

    def fails(self, command: str) -> None:
        with open(self.failing, "a") as file:
            file.write(command + "\n")

    def called(self) -> list[str]:
        return self.calls.read_text().splitlines() if self.calls.exists() else []


@pytest.fixture
def install(tmp_path, monkeypatch, published):
    published(**{NEW: "2026-10-04", __version__: "2026-10-01"})
    return Install(tmp_path, monkeypatch)


@pytest.fixture
def session(repo, fake_tmux):
    assert main(["start", str(repo), "--provider", "claude", "--name", "s", "--no-attach"]) == 0
    return "s"


def migrate_like_the_new_version(copy: bool = True) -> str:
    """Installer lines that move lado.db's schema on as a new LADO's migration would: first
    its copy backups/lado.db.schema-<the schema before> (none without `copy`), then the
    schema."""
    db = state.home() / "lado.db"
    folder = state.home() / "backups"
    code = (
        "import os, sqlite3; "
        f"c = sqlite3.connect('{db}'); "
        f"v = c.execute('PRAGMA user_version').fetchone()[0]; "
        + (
            f"os.makedirs('{folder}', exist_ok=True); "
            f"b = sqlite3.connect(os.path.join('{folder}', 'lado.db.schema-%d' % v)); "
            "c.backup(b); b.close(); "
            if copy
            else ""
        )
        + "c.execute('PRAGMA user_version = 999'); c.close()"
    )
    return f'if [ "$1" = "{NEW}" ]; then "{sys.executable}" -c "{code}"; fi'


def copy_path() -> Path:
    """The copy the migration of the new version writes (migrate_like_the_new_version)."""
    return state.home() / "backups" / f"lado.db.schema-{state.SCHEMA_VERSION}"


def listing() -> dict[str, bytes]:
    """backups/ by name and content: equal listings mean nothing was written there."""
    folder = state.home() / "backups"
    return {p.name: p.read_bytes() for p in folder.iterdir()} if folder.exists() else {}


def migrated(before: dict[str, bytes]) -> dict[str, bytes]:
    """backups/ as `before`, with only the copy the new version's migration wrote added."""
    return {**before, copy_path().name: copy_path().read_bytes()}


def plan_to(version: str = NEW) -> self_update.Plan:
    index = update.fetch_index()
    return self_update.plan(update.release(index, version), index)


def run(version: str = NEW, **kwargs) -> tuple[int, list[str]]:
    said = []
    code = self_update.run(plan_to(version), lambda text="", **_: said.append(text), **kwargs)
    return code, said


def result() -> update.Result:
    return update.read_result()


def test_a_cli_update_writes_its_log_and_a_result_with_its_own_tail(install, session, capsys):
    assert main(["update", "--yes"]) == 0
    out = capsys.readouterr().out
    log = (state.home() / "update.log").read_text()
    assert f"Upgrading: {install.installer} {NEW}\n" in out
    assert f"Upgrading: {install.installer} {NEW}\n" in log
    assert f"installing lado=={NEW}\n" in log  # the installer's output, also in the log
    assert "ran start\n" in log  # and the resumes'
    done = result()
    assert (done.outcome, done.from_, done.to, done.database) == ("ok", __version__, NEW, "kept")
    assert done.ended_at and done.started_at <= done.ended_at
    assert done.log == str(state.home() / "update.log")
    assert done.tail == log.splitlines()[-20:]
    assert done.tail[-1] == f"LADO {NEW} is ready."


def test_the_result_says_running_while_the_update_runs(install, session):
    seen = install.prefix.parent / "seen"
    install.installs(f'cp "{update.result_path()}" "{seen}"')
    assert run()[0] == 0
    during = json.loads(seen.read_text())
    assert (during["outcome"], during["ended_at"]) == ("running", None)
    assert during["started_at"] == result().started_at


def test_the_update_started_by_the_ui_keeps_its_id(install, session):
    assert run(id="u-1")[0] == 0
    assert result().id == "u-1"


def test_a_second_update_is_refused_and_keeps_the_first_ones_log_and_result(install, session):
    (state.home() / "update.log").write_text("the first update's log\n")
    update.write_result(update.Result("running", __version__, NEW, "2026-10-09T10:00:00+00:00"))
    with open(state.home() / "update.lock", "a") as held:
        fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
        held.write("4242")
        held.flush()
        assert self_update.refusal(update.installer()).why == "an update is running, pid 4242"
        with pytest.raises(self_update.UpdateRefused, match="an update is running, pid 4242"):
            run()
    assert (state.home() / "update.log").read_text() == "the first update's log\n"
    assert result().outcome == "running"
    assert install.called() == []
    assert not state.get_session(session).stopped_at


def test_the_cli_refuses_an_update_while_one_runs(install, session, capsys):
    with open(state.home() / "update.lock", "a") as held:
        fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
        held.write("4242")
        held.flush()
        assert main(["update", "--yes"]) == 1
    assert capsys.readouterr().err == "lado: an update is running, pid 4242\n"
    assert not state.get_session(session).stopped_at


def test_the_refusals_name_an_agent_and_another_install(install, tmp_path, monkeypatch):
    assert self_update.refusal(update.installer()) is None
    assert self_update.refusal(None).kind == self_update.NO_INSTALLER
    monkeypatch.setenv("LADO_AGENT", "w1")
    refused = self_update.refusal(update.installer())
    assert refused.why == 'lado update is for the human; agent "w1" cannot use it'


CONTAINER_LINE = "lado: LADO runs in a container: a new image updates it, not lado update\n"


def test_the_refusal_in_a_container_comes_after_an_agent_and_before_the_rest(install, monkeypatch):
    monkeypatch.setenv("LADO_CONTAINER", "1")
    for installer in (update.installer(), None):  # before NO_INSTALLER too
        refused = self_update.refusal(installer)
        assert refused.kind == self_update.CONTAINER
        assert refused.why == "LADO runs in a container: a new image updates it, not lado update"
    with open(state.home() / "update.lock", "a") as held:  # before RUNNING
        fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert self_update.refusal(update.installer()).kind == self_update.CONTAINER
    monkeypatch.setenv("LADO_AGENT", "w1")
    assert self_update.refusal(update.installer()).kind == self_update.AGENT


@pytest.mark.parametrize("args", [["--yes"], ["0.36.0"], ["--yes", NEW, "--id", "u-9"]])
def test_lado_update_in_a_container_refuses_at_once_and_stops_nothing(
    install, session, monkeypatch, tmp_path, capsys, args
):
    """The container's main process is the UI server: stopping it would kill the update.
    So the refusal comes before PyPI (a missing index would be another error), the lock,
    update.json, update.log and every stop."""
    monkeypatch.setenv("LADO_CONTAINER", "1")
    monkeypatch.setenv("LADO_UPDATE_INDEX", str(tmp_path / "missing.json"))
    stopped = []
    monkeypatch.setattr(self_update.runtime, "stop_session", lambda *a, **k: stopped.append(a))
    monkeypatch.setattr(self_update.server_run, "stop", lambda *a, **k: stopped.append(a))
    update.write_result(update.Result("ok", "0.1.0", __version__, "2026-10-09T10:00:00+00:00"))
    before = (state.home() / "update-result.json").read_text()
    capsys.readouterr()
    assert main(["update", *args]) == 1
    assert capsys.readouterr().err == CONTAINER_LINE
    assert stopped == [] and install.called() == []
    assert not state.get_session(session).stopped_at
    for name in ("update.json", "update.log"):
        assert not (state.home() / name).exists(), name
    lock = state.home() / "update.lock"  # `--id`'s result is written under the lock: no pid
    assert not lock.exists() or lock.read_text() == ""
    if "--id" in args:  # the UI's update learns why by its id
        done = result()
        assert (done.id, done.outcome, done.log) == ("u-9", "failed", None)
        assert done.reason.startswith("the update did not start: LADO runs in a container")
    else:
        assert (state.home() / "update-result.json").read_text() == before


def test_lado_update_inside_an_agent_in_a_container_is_the_agents_refusal(
    install, monkeypatch, capsys
):
    monkeypatch.setenv("LADO_CONTAINER", "1")
    monkeypatch.setenv("LADO_AGENT", "w1")
    assert main(["update", "--yes"]) == 1
    assert 'agent "w1" cannot use it' in capsys.readouterr().err


def test_the_update_writes_and_removes_nothing_in_backups(install, session):
    backups = state.home() / "backups"
    backups.mkdir()
    (backups / "lado.db.0.0.1").write_text("an older update's backup")
    (backups / f"lado.db.schema-{state.SCHEMA_VERSION - 1}").write_text("a migration's")
    before = listing()
    seen = install.prefix.parent / "seen"
    install.installs(f'ls "{backups}" > "{seen}"')
    code, said = run()
    assert code == 0
    assert seen.read_text().split() == sorted(before)  # nothing written before the installer
    assert listing() == before
    assert not any(line.startswith("Backed up") for line in said)


def test_a_wrong_version_rolls_back_and_restores_lado_db_when_its_schema_moved(install, session):
    install.installs(migrate_like_the_new_version(), version=BROKEN_NEW)
    before = listing()
    code, said = run()
    assert code == 1
    assert listing() == migrated(before)  # the copy stays
    # The old version again, with the same installer, then resumed on it.
    assert [c.split()[0] for c in install.called()] == ["--version", "--version", "start"]
    assert install.version_file.read_text().strip() == __version__
    done = result()
    assert done.outcome == "rolled_back"
    assert done.database == "restored"
    assert done.reason == f"LADO {NEW} did not install right: --version says {NEW}-broken"
    assert state.schema_version() == state.SCHEMA_VERSION
    assert f"Rolling back to LADO {__version__}: {done.reason}" in said
    assert f"Restored lado.db from {copy_path()}" in said
    with sqlite3.connect(state.home() / "lado.db") as db:
        assert db.execute("SELECT name FROM sessions").fetchall() == [("s",)]


def test_a_rollback_without_the_migrations_copy_keeps_the_new_version(
    install, session, monkeypatch, capsys
):
    monkeypatch.setattr(
        self_update.server_run, "running", lambda: {"host": "127.0.0.1", "port": 8123, "url": "u"}
    )
    monkeypatch.setattr(self_update.server_run, "stop", lambda: None)
    install.installs(migrate_like_the_new_version(copy=False))
    install.fails("ui")
    before = listing()
    code = self_update.run(plan_to(), print)
    assert code == 1
    done = result()
    assert done.outcome == "rollback_failed"
    assert done.reason == (
        f"the UI server did not start on LADO {NEW} (exit code 1); not rolled back: lado.db "
        f"has schema 999 and backups/ holds no lado.db.schema-{state.SCHEMA_VERSION} for "
        f"LADO {__version__}, so LADO {NEW} stays installed"
    )
    assert done.reason in capsys.readouterr().err
    # Installed once; the resumed session is not stopped and nothing is reinstalled.
    assert [c.split()[0] for c in install.called()] == ["--version", "start", "ui"]
    assert install.version_file.read_text().strip() == NEW
    assert state.schema_version() == 999
    assert listing() == before


def test_a_rollback_keeps_lado_db_when_its_schema_did_not_move(install, session):
    install.installs("", version=BROKEN_NEW)
    before = listing()
    assert run()[0] == 1
    done = result()
    assert (done.outcome, done.database) == ("rolled_back", "kept")
    assert listing() == before


def test_a_failed_reinstall_of_the_old_version_is_a_failed_rollback(install, session):
    install.installs(f'if [ "$1" = "{__version__}" ]; then exit 1; fi', version=BROKEN_NEW)
    before = listing()
    assert run()[0] == 1
    assert listing() == before
    done = result()
    assert done.outcome == "rollback_failed"
    assert done.reason.startswith(
        f"LADO {NEW} did not install right: --version says {NEW}-broken; "
        f"reinstalling LADO {__version__} failed (exit code 1)"
    )
    assert state.get_session(session).stopped_at  # nothing resumed on a broken install


def test_a_failed_installer_rolls_nothing_back_and_keeps_lado_db(install, session):
    install.installs("exit 3")
    before = listing()
    assert run()[0] == 1
    assert listing() == before
    done = result()
    assert (done.outcome, done.database) == ("failed", "kept")
    assert done.reason == "the installer failed (exit code 3)"
    assert [c.split()[0] for c in install.called()] == ["start"]  # resumed, no --version


def test_a_session_that_does_not_resume_is_partial_and_rolls_nothing_back(install, session):
    install.fails("start")
    before = listing()
    code, said = run()
    assert code == 1
    assert listing() == before
    done = result()
    assert done.outcome == "partial"
    sess = state.get_session(session)
    assert done.sessions_failed == [{"name": "s", "command": f"lado start {sess.repo} --name s"}]
    assert done.reason == "1 session did not resume"
    assert install.version_file.read_text().strip() == NEW


def test_a_server_that_does_not_come_up_on_the_new_version_rolls_back(
    install, session, monkeypatch
):
    monkeypatch.setattr(
        self_update.server_run, "running", lambda: {"host": "127.0.0.1", "port": 8123, "url": "u"}
    )
    monkeypatch.setattr(self_update.server_run, "stop", lambda: None)
    install.installs(migrate_like_the_new_version())
    install.fails("ui")
    before = listing()
    code, said = run()
    assert code == 1
    assert listing() == migrated(before)
    done = result()
    assert done.outcome == "rolled_back"
    assert done.reason == f"the UI server did not start on LADO {NEW} (exit code 1)"
    assert done.database == "restored"
    assert state.schema_version() == state.SCHEMA_VERSION
    calls = [c.split()[0] for c in install.called()]
    # New: --version, start, ui; the rollback stops what it started, then the old one.
    assert calls == ["--version", "start", "ui", "stop", "server", "--version", "start", "ui"]


def test_a_new_server_that_answers_with_another_version_rolls_back(install, session, monkeypatch):
    monkeypatch.setattr(
        self_update.server_run, "running", lambda: {"host": "127.0.0.1", "port": 8123, "url": "u"}
    )
    monkeypatch.setattr(self_update.server_run, "stop", lambda: None)
    monkeypatch.setattr(self_update.server_run, "health", lambda url: {"version": __version__})
    before = listing()
    assert run()[0] == 1
    assert listing() == before
    assert result().reason == (
        f"the UI server did not come up on LADO {NEW}: /api/health says {__version__}"
    )


def test_a_loop_that_does_not_end_in_the_rollback_leaves_lado_db_as_it_is(
    install, session, monkeypatch
):
    monkeypatch.setattr(
        self_update.server_run, "running", lambda: {"host": "127.0.0.1", "port": 8123, "url": "u"}
    )
    monkeypatch.setattr(self_update.server_run, "stop", lambda: None)
    waits = iter([True, False])  # the update's own wait, then the rollback's
    monkeypatch.setattr(self_update.loop, "wait_stopped", lambda s, timeout=None: next(waits))
    install.installs(migrate_like_the_new_version())
    install.fails("ui")
    before = listing()
    assert run()[0] == 1
    assert listing() == migrated(before)
    done = result()
    assert done.outcome == "rollback_failed"
    assert done.database is None
    assert done.reason.endswith(
        f"lado.db not restored: the session loop of s did not end; its backup is {copy_path()}"
    )
    assert state.schema_version() == 999


def test_the_restore_goes_through_sqlite_while_another_connection_holds_a_wal_frame(tmp_path):
    live, backup = tmp_path / "live.db", tmp_path / "backup.db"
    with sqlite3.connect(backup) as db:
        db.execute("CREATE TABLE t (x)")
        db.execute("INSERT INTO t VALUES ('old')")
    other = sqlite3.connect(live)
    other.execute("PRAGMA journal_mode = WAL")
    other.execute("PRAGMA wal_autocheckpoint = 0")
    other.execute("CREATE TABLE t (x)")
    other.execute("INSERT INTO t VALUES ('new')")
    other.commit()  # in lado.db-wal only, and `other` stays open
    assert (tmp_path / "live.db-wal").stat().st_size > 0
    self_update.restore(backup, live)
    other.close()
    with sqlite3.connect(live) as db:
        assert db.execute("SELECT x FROM t").fetchall() == [("old",)]


def test_nothing_is_imported_after_the_installer(install, session, monkeypatch):
    """The installer replaces the package under the running update: the rollback, the restore
    and the result must need no import (a new module would be the new version's, or none)."""

    class NoImports:
        def find_spec(self, name, path=None, target=None):
            raise ImportError(f"imported after the installer: {name}")

    real = self_update._install

    def install_then_forbid(*args):
        done = real(*args)
        sys.meta_path.insert(0, NoImports())
        return done

    monkeypatch.setattr(self_update, "_install", install_then_forbid)
    install.installs(migrate_like_the_new_version(), version=BROKEN_NEW)
    try:
        assert run()[0] == 1
    finally:
        sys.meta_path[:] = [f for f in sys.meta_path if not isinstance(f, NoImports)]
    assert (result().outcome, result().database) == ("rolled_back", "restored")


def test_an_unfinished_updates_mark_goes_once_none_of_its_sessions_is_stopped(
    install, session, capsys
):
    sess = state.get_session(session)
    update.write_pending(update.Pending({"s": sess.repo}, None))
    assert self_update.unfinished() is None  # s runs
    assert not update.pending_path().exists()


def test_the_login_token_stays_out_of_the_log_and_the_result(install, session, monkeypatch):
    """`lado ui` prints its login link: neither update.log nor the result's tail (which the UI
    shows) keeps the token, and the result is the owner's only."""
    monkeypatch.setattr(
        self_update.server_run, "running", lambda: {"host": "127.0.0.1", "port": 8123, "url": "u"}
    )
    monkeypatch.setattr(self_update.server_run, "stop", lambda: None)
    monkeypatch.setattr(self_update.server_run, "health", lambda url: {"version": NEW})
    assert run()[0] == 0
    log = (state.home() / "update.log").read_text()
    assert "http://127.0.0.1:8123/?token=…" in log
    assert TOKEN not in log
    assert TOKEN not in "\n".join(result().tail)
    assert stat.S_IMODE(update.result_path().stat().st_mode) == 0o600


def test_a_check_at_the_same_time_is_no_running_update(install):
    """Two looks at the lock at once (two server threads, the detached update's own check)
    do not take each other for an update: a look shares the lock, only an update holds it."""
    with open(state.home() / "update.lock", "a") as looking:
        fcntl.flock(looking, fcntl.LOCK_SH | fcntl.LOCK_NB)  # another look, now
        assert self_update.running_pid() is None
        assert self_update.refusal(update.installer()) is None


def test_an_update_of_the_ui_that_does_not_start_says_so_in_its_result(install, session):
    """The page waits for its id: a detached update that ends before it starts (here PyPI
    has no such version) writes a failed result with no log, and stops nothing."""
    assert main(["update", "--yes", "98.0.0", "--id", "u-9"]) == 1
    done = result()
    assert (done.id, done.outcome, done.log, done.to) == ("u-9", "failed", None, "98.0.0")
    assert done.reason == ("the update did not start: PyPI has no LADO 98.0.0; nothing was stopped")
    assert done.ended_at
    assert not (state.home() / "update.log").exists()
    assert not state.get_session(session).stopped_at


def test_an_update_of_the_ui_refused_by_a_running_one_writes_no_result(install, session):
    update.write_result(update.Result("running", __version__, NEW, "2026-10-09T10:00:00+00:00"))
    with open(state.home() / "update.lock", "a") as held:
        fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert main(["update", "--yes", NEW, "--id", "u-9"]) == 1
    assert (result().outcome, result().id) == ("running", None)  # the running one's


@pytest.mark.parametrize(
    "current, releases, to",
    [
        ("0.36.0", ["0.36.0", "0.37.0rc1"], None),
        ("0.37.0rc1", ["0.36.0", "0.37.0rc1", "0.37.0rc2"], "0.37.0rc2"),
    ],
)
def test_the_latest_plan_offers_a_release_candidate_only_to_a_pre_release(
    install, published, monkeypatch, current, releases, to
):
    import lado

    monkeypatch.setattr(lado, "__version__", current, raising=False)
    published(**{version: "2026-10-01" for version in releases})
    found = self_update.latest_plan()
    assert (found.to.version if found else None) == to


OLD = "0.1.0"
OLD_SCHEMA = state.SCHEMA_VERSION - 4
MADE = datetime.datetime(2026, 10, 20, 14, 3).timestamp()  # local time


@pytest.fixture
def older(install, published, tmp_path):
    """The index also has OLD, whose wheel says `schema` (OLD_SCHEMA by default); its file's
    dict overridden by `file`."""

    def publish(schema: int | None = OLD_SCHEMA, **file):
        published(
            **{
                NEW: "2026-10-04",
                __version__: "2026-10-01",
                OLD: [wheel(tmp_path / "wheels", schema, OLD, **file)],
            }
        )

    publish()
    return publish


@pytest.fixture
def two_sessions(repo, fake_tmux):
    """Sessions `app` and `web2`; backups/lado.db.schema-<OLD_SCHEMA> is lado.db as it was
    before `web2` was made, at that schema, made at MADE."""
    assert main(["start", str(repo), "--provider", "claude", "--name", "app", "--no-attach"]) == 0
    copy = state.home() / "backups" / f"lado.db.schema-{OLD_SCHEMA}"
    copy.parent.mkdir()
    state.copy_db(state.home() / "lado.db", copy)
    with contextlib.closing(sqlite3.connect(copy)) as db:
        db.execute(f"PRAGMA user_version = {OLD_SCHEMA}")
    os.utime(copy, (MADE, MADE))
    assert main(["start", str(repo), "--provider", "claude", "--name", "web2", "--no-attach"]) == 0
    return copy


def warning(copy) -> str:
    return (
        f"lado: WARNING: LADO {OLD} knows lado.db up to schema {OLD_SCHEMA}; lado.db has "
        f"schema {state.SCHEMA_VERSION}.\n"
        f"  lado.db goes back to {copy}, made 2026-10-20 14:03\n"
        f"  by the upgrade from schema {OLD_SCHEMA}. Everything LADO recorded since then is "
        "lost: sessions,\n"
        "  runs, gates, messages, projects. Repositories, worktrees and project folders stay "
        "on disk.\n"
        "  Sessions not in that copy are not started again: web2\n"
    )


def schema_of(path) -> int:
    with contextlib.closing(sqlite3.connect(path)) as db:
        return db.execute("PRAGMA user_version").fetchone()[0]


def test_a_plan_to_an_older_schema_says_what_it_loses(older, two_sessions, capsys):
    found = plan_to(OLD)
    assert found.restore == self_update.Restore(
        two_sessions, OLD_SCHEMA, state.SCHEMA_VERSION, "2026-10-20 14:03", ["web2"]
    )
    capsys.readouterr()
    self_update.print_plan(found)
    err = capsys.readouterr().err
    assert warning(two_sessions) in err
    assert "may refuse" not in err


def by_hand_back(install, repo, copy) -> list[str]:
    """The commands by hand of the way back to OLD with sessions app and web2 (the copy
    has app only) and the UI server, from a venv with pip."""
    home = state.home()
    return [
        "lado stop app",
        "lado stop web2",
        "lado server stop",
        f"{install.prefix}/bin/pip install lado=={OLD}",
        f"rm -f {home}/lado.db-wal {home}/lado.db-shm && cp {copy} {home}/lado.db",
        f"lado start {shlex.quote(str(repo))} --name app",  # "My Repo"
        "lado ui",
    ]


@pytest.fixture
def by_hand(install, monkeypatch):
    """A venv's pip in the install's prefix, and a UI server."""
    pip = install.prefix / "bin" / "pip"
    pip.write_text("#!/bin/sh\n")
    pip.chmod(0o755)
    monkeypatch.setattr(self_update.server_run, "running", lambda: {"url": "u", "port": 8123})


def test_the_commands_by_hand_of_an_older_schema_put_the_copy_back(
    install, older, two_sessions, by_hand, repo
):
    assert plan_to(OLD).by_hand() == by_hand_back(install, repo, two_sessions)


def test_an_update_by_hand_to_an_older_schema_prints_the_way_back_and_stops_nothing(
    install, older, two_sessions, by_hand, repo, capsys, monkeypatch
):
    monkeypatch.delenv("LADO_UPDATE_INSTALLER")
    capsys.readouterr()
    assert main(["update", "--yes", OLD]) == 1
    out = capsys.readouterr().out
    lines = "".join(f"  {line}\n" for line in by_hand_back(install, repo, two_sessions))
    assert out.endswith("By hand:\n" + lines)
    assert install.called() == []
    assert not state.get_session("app").stopped_at
    assert schema_of(state.home() / "lado.db") == state.SCHEMA_VERSION


def test_a_plan_to_an_older_version_of_the_same_schema_warns_of_nothing(older, session, capsys):
    older(state.SCHEMA_VERSION)
    found = plan_to(OLD)
    assert found.restore is None
    capsys.readouterr()
    self_update.print_plan(found)
    assert "lado.db" not in capsys.readouterr().err


def test_the_commands_by_hand_of_the_same_schema_restore_nothing_and_start_all(
    install, older, two_sessions, by_hand, repo
):
    older(state.SCHEMA_VERSION)
    lines = plan_to(OLD).by_hand()
    assert not any(" cp " in line for line in lines)
    assert [line for line in lines if line.startswith("lado start")] == [
        f"lado start {shlex.quote(str(repo))} --name app",
        f"lado start {shlex.quote(str(repo))} --name web2",
    ]


def test_no_wheel_is_fetched_without_lado_db_or_for_an_update_forward(older, tmp_path):
    older(url=(tmp_path / "missing.whl").as_uri())
    assert state.schema_version() is None
    assert plan_to(OLD).restore is None  # no lado.db: the missing wheel is never asked for
    assert plan_to(NEW).restore is None


@pytest.mark.parametrize(
    "spoil, line",
    [
        (
            "copy",
            f"lado: LADO {OLD} needs lado.db at schema {OLD_SCHEMA}, and lado.db has schema "
            f"{state.SCHEMA_VERSION}; {{backups}} holds no lado.db.schema-{OLD_SCHEMA} to go back "
            "to (docs/install.md, Going back to an older version); nothing was stopped\n",
        ),
        (
            "wheel",
            f"lado: cannot learn which lado.db schema LADO {OLD} needs: lado-{OLD}-py3-none-any"
            ".whl does not match its sha256 on PyPI; nothing was stopped\n",
        ),
    ],
)
def test_an_update_to_an_older_schema_that_cannot_go_back_stops_nothing(
    install, older, two_sessions, capsys, monkeypatch, spoil, line
):
    if spoil == "copy":
        two_sessions.rename(two_sessions.with_name(f"lado.db.schema-{state.SCHEMA_VERSION}"))
    else:
        older(digests={"sha256": "0" * 64})
    stopped = []
    monkeypatch.setattr(self_update.runtime, "stop_session", lambda *a, **k: stopped.append(a))
    capsys.readouterr()
    assert main(["update", "--yes", OLD]) == 1
    assert capsys.readouterr().err == line.format(backups=state.home() / "backups")
    assert stopped == [] and install.called() == []
    assert not update.result_path().exists()
    with pytest.raises(runtime.LadoError):
        plan_to(OLD)


def test_an_update_to_an_older_schema_puts_the_copy_back_and_resumes_what_it_has(
    install, older, two_sessions, capsys
):
    kept = two_sessions.read_bytes()
    assert main(["update", "--yes", OLD]) == 0
    out = capsys.readouterr().out
    assert f"Restored lado.db from {two_sessions} (schema {OLD_SCHEMA})" in out
    live = state.home() / "lado.db"
    assert schema_of(live) == OLD_SCHEMA
    with sqlite3.connect(live) as db:
        assert db.execute("SELECT name FROM sessions").fetchall() == [("app",)]
    assert two_sessions.read_bytes() == kept  # the copy stays
    starts = [c.split()[-2] for c in install.called() if c.startswith("start")]
    assert starts == ["app"]
    done = result()
    assert (done.outcome, done.database) == ("ok", "restored")


def test_a_restore_that_fails_rolls_back_with_lado_db_as_it_was(
    install, older, two_sessions, monkeypatch
):
    def broken(source, target):
        raise sqlite3.OperationalError("disk I/O error")

    monkeypatch.setattr(self_update, "restore", broken)
    assert main(["update", "--yes", OLD]) == 1
    done = result()
    assert (done.outcome, done.database) == ("rolled_back", "kept")
    assert "disk I/O error" in done.reason
    assert state.schema_version() == state.SCHEMA_VERSION
    assert install.version_file.read_text().strip() == __version__


def test_an_old_version_that_fails_after_the_restore_is_rolled_back_restoring_nothing(
    install, older, two_sessions, monkeypatch
):
    monkeypatch.setattr(
        self_update.server_run, "running", lambda: {"host": "127.0.0.1", "port": 8123, "url": "u"}
    )
    monkeypatch.setattr(self_update.server_run, "stop", lambda: None)
    install.fails("ui")
    before = listing()
    assert main(["update", "--yes", OLD]) == 1
    done = result()
    assert (done.outcome, done.database) == ("rolled_back", "kept")
    assert install.version_file.read_text().strip() == __version__
    assert state.schema_version() == OLD_SCHEMA  # the version before migrates it on resume
    assert listing() == before


def test_a_copy_gone_before_the_restore_leaves_lado_db_and_backups_as_they_were(
    install, older, two_sessions
):
    """The plan saw the copy; it is gone by the restore: lado.db is not replaced by an empty
    database, and no empty file is made where the copy was."""
    found = plan_to(OLD)
    two_sessions.unlink()
    before = listing()
    kept = schema_of(state.home() / "lado.db")
    assert self_update.run(found, lambda *a, **k: None) == 1
    done = result()
    assert (done.outcome, done.database) == ("rolled_back", "kept")
    assert state.schema_version() == kept == state.SCHEMA_VERSION
    with contextlib.closing(sqlite3.connect(state.home() / "lado.db")) as db:
        assert db.execute("SELECT name FROM sessions ORDER BY name").fetchall() == [
            ("app",),
            ("web2",),
        ]
    assert listing() == before


def test_a_copy_gone_before_the_rollbacks_restore_is_a_failed_rollback(
    install, session, monkeypatch
):
    monkeypatch.setattr(
        self_update.server_run, "running", lambda: {"host": "127.0.0.1", "port": 8123, "url": "u"}
    )
    monkeypatch.setattr(self_update.server_run, "stop", lambda: None)
    # The new version migrates; reinstalling the old one, the copy goes.
    install.installs(
        migrate_like_the_new_version()
        + f'\nif [ "$1" = "{__version__}" ]; then rm -f "{copy_path()}"; fi'
    )
    install.fails("ui")
    assert run()[0] == 1
    done = result()
    assert done.outcome == "rollback_failed"
    assert "lado.db not restored: " in done.reason
    assert state.schema_version() == 999  # not an empty database
    assert not copy_path().exists()


def test_a_loop_that_does_not_end_in_a_rollback_with_nothing_to_restore_names_no_backup(
    install, session, monkeypatch
):
    monkeypatch.setattr(
        self_update.server_run, "running", lambda: {"host": "127.0.0.1", "port": 8123, "url": "u"}
    )
    monkeypatch.setattr(self_update.server_run, "stop", lambda: None)
    waits = iter([True, False])
    monkeypatch.setattr(self_update.loop, "wait_stopped", lambda s, timeout=None: next(waits))
    install.fails("ui")
    assert run()[0] == 1
    done = result()
    assert done.outcome == "rollback_failed"
    assert done.reason.endswith("lado.db not restored: the session loop of s did not end")
