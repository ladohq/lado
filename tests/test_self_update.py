"""lado.self_update: the update's lock, log, result file, lado.db's backup and the rollback,
with a fake install (its `bin/lado` a shell script) and tmux replaced by a recorder."""

import fcntl
import json
import sqlite3
import stat
import sys

import pytest

from lado import __version__, self_update, state, update
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


def bump_schema() -> str:
    """Installer lines that move lado.db's schema on, as a new LADO's migration would."""
    db = state.home() / "lado.db"
    code = f"import sqlite3; c = sqlite3.connect('{db}'); c.execute('PRAGMA user_version = 999')"
    return f'if [ "$1" = "{NEW}" ]; then "{sys.executable}" -c "{code}"; fi'


def plan_to(version: str = NEW) -> self_update.Plan:
    return self_update.plan(update.release(update.fetch_index(), version))


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


def test_lado_db_is_backed_up_before_the_installer_and_only_one_backup_is_kept(install, session):
    backups = state.home() / "backups"
    backups.mkdir()
    (backups / "lado.db.0.0.1").write_text("an older backup")
    seen = install.prefix.parent / "seen"
    install.installs(f'ls "{backups}" > "{seen}"')
    code, said = run()
    assert code == 0
    assert seen.read_text().split() == [f"lado.db.{__version__}"]
    assert [p.name for p in backups.iterdir()] == [f"lado.db.{__version__}"]
    assert f"Backed up lado.db to {backups / f'lado.db.{__version__}'}" in said
    with sqlite3.connect(backups / f"lado.db.{__version__}") as db:
        assert db.execute("SELECT name FROM sessions").fetchall() == [("s",)]


def test_a_wrong_version_rolls_back_and_restores_lado_db_when_its_schema_moved(install, session):
    install.installs(bump_schema(), version=BROKEN_NEW)
    code, said = run()
    assert code == 1
    # The old version again, with the same installer, then resumed on it.
    assert [c.split()[0] for c in install.called()] == ["--version", "--version", "start"]
    assert install.version_file.read_text().strip() == __version__
    done = result()
    assert done.outcome == "rolled_back"
    assert done.database == "restored"
    assert done.reason == f"LADO {NEW} did not install right: --version says {NEW}-broken"
    assert state.schema_version() == state.SCHEMA_VERSION
    assert f"Rolling back to LADO {__version__}: {done.reason}" in said


def test_a_rollback_keeps_lado_db_when_its_schema_did_not_move(install, session):
    install.installs("", version=BROKEN_NEW)
    assert run()[0] == 1
    done = result()
    assert (done.outcome, done.database) == ("rolled_back", "kept")


def test_a_failed_reinstall_of_the_old_version_is_a_failed_rollback(install, session):
    install.installs(f'if [ "$1" = "{__version__}" ]; then exit 1; fi', version=BROKEN_NEW)
    assert run()[0] == 1
    done = result()
    assert done.outcome == "rollback_failed"
    assert done.reason.startswith(
        f"LADO {NEW} did not install right: --version says {NEW}-broken; "
        f"reinstalling LADO {__version__} failed (exit code 1)"
    )
    assert state.get_session(session).stopped_at  # nothing resumed on a broken install


def test_a_failed_installer_rolls_nothing_back_and_keeps_lado_db(install, session):
    install.installs("exit 3")
    assert run()[0] == 1
    done = result()
    assert (done.outcome, done.database) == ("failed", "kept")
    assert done.reason == "the installer failed (exit code 3)"
    assert [c.split()[0] for c in install.called()] == ["start"]  # resumed, no --version


def test_a_session_that_does_not_resume_is_partial_and_rolls_nothing_back(install, session):
    install.fails("start")
    code, said = run()
    assert code == 1
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
    install.installs(bump_schema())
    install.fails("ui")
    code, said = run()
    assert code == 1
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
    assert run()[0] == 1
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
    install.installs(bump_schema())
    install.fails("ui")
    assert run()[0] == 1
    done = result()
    backup = state.home() / "backups" / f"lado.db.{__version__}"
    assert done.outcome == "rollback_failed"
    assert done.database is None
    assert done.reason.endswith(
        f"lado.db not restored: the session loop of s did not end; its backup is {backup}"
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
    install.installs(bump_schema(), version=BROKEN_NEW)
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
