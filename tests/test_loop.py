import threading

from agent_helpers import previous_schema

from lado import loop, runtime, state, tmux


def _session(repo):
    runtime.start_session(str(repo), "s", None, provider="claude")


def test_the_loop_goes_on_while_the_session_runs(repo, fake_tmux):
    _session(repo)
    assert loop.why_stop("s") is None


def test_the_loop_stops_with_its_session(repo, fake_tmux):
    _session(repo)
    runtime.stop_session("s")
    assert loop.why_stop("s") == "the session is stopped"


def test_the_loop_stops_when_the_tmux_session_is_gone(repo, fake_tmux):
    _session(repo)
    tmux.kill_session("s")
    assert loop.why_stop("s") == "its tmux session is gone"


def test_the_loop_stops_for_an_unknown_session(lado_home):
    state.list_sessions()  # the database exists
    assert loop.why_stop("s") == "the session is gone"


def test_the_loop_stops_on_another_schema_and_does_not_migrate_it(repo, fake_tmux, lado_home):
    _session(repo)
    previous_schema()
    assert loop.run("s", interval=0) == 0
    last = (lado_home / "loop.log").read_text().splitlines()[-1]
    assert f"s: loop ended: {lado_home / 'lado.db'} has schema version" in last
    assert state.pending_migration() is not None  # still the old schema


def test_a_pass_that_meets_another_schema_ends_the_loop_and_migrates_nothing(
    repo, fake_tmux, monkeypatch, lado_home
):
    """The schema changes between why_stop and the sweep: the sweep's own connection
    refuses it, and the loop ends with the reason instead of going on."""
    _session(repo)
    sweep, passes = runtime.sweep, []

    def schema_changes_first(session):
        passes.append(session)
        previous_schema()
        sweep(session)

    monkeypatch.setattr(runtime, "sweep", schema_changes_first)
    assert loop.run("s", interval=0) == 0
    assert passes == ["s"]
    last = (lado_home / "loop.log").read_text().splitlines()[-1]
    assert "s: loop ended: " in last and "LADO was upgraded under a running session" in last
    assert state.pending_migration() is not None  # still the old schema


def test_a_session_has_one_loop(lado_home):
    assert not loop.running("s")  # no lock file yet
    first = loop.take_lock("s")
    assert first is not None
    assert loop.take_lock("s") is None
    assert loop.running("s")
    first.close()  # as when its process ends
    assert not loop.running("s")


def test_a_second_loop_exits_at_once(repo, fake_tmux, monkeypatch):
    _session(repo)
    swept = []
    monkeypatch.setattr(runtime, "sweep", swept.append)
    held = loop.take_lock("s")
    assert loop.run("s", interval=0) == 0
    assert swept == []
    held.close()


def test_the_loop_sweeps_until_its_session_stops(repo, fake_tmux, monkeypatch, lado_home):
    _session(repo)
    passes = []

    def sweep(session):
        passes.append(session)
        if len(passes) == 1:
            raise RuntimeError("database is locked")
        if len(passes) == 3:
            runtime.stop_session(session)

    monkeypatch.setattr(runtime, "sweep", sweep)
    assert loop.run("s", interval=0) == 0
    assert passes == ["s"] * 3  # an error in one pass does not stop it
    log = (lado_home / "loop.log").read_text()
    assert "RuntimeError: database is locked" in log
    assert log.splitlines()[-1].endswith("s: loop ended: the session is stopped")
    assert not loop.running("s")


def test_start_starts_the_loop_once_the_tmux_session_exists(
    repo, fake_tmux, loop_starts, monkeypatch
):
    def new_session(*args):
        sessions = [c for c in fake_tmux if c[0] == "new_session"]
        assert len(loop_starts) == len(sessions)  # not started before the tmux session
        fake_tmux.append(("new_session", *args))

    monkeypatch.setattr(tmux, "new_session", new_session)
    runtime.start_session(str(repo), "s", None, provider="claude")
    assert loop_starts == ["s"]
    runtime.stop_session("s")
    runtime.start_session(str(repo), "s", None)  # resumed
    assert loop_starts == ["s", "s"]


def test_forget_removes_the_lock_file(repo, fake_tmux):
    _session(repo)
    loop.take_lock("s").close()  # a loop ran
    runtime.stop_session("s")
    runtime.forget_session("s")
    assert not loop.lock_path("s").exists()


def test_a_loop_waits_for_a_lock_held_for_a_moment(repo, fake_tmux, monkeypatch):
    _session(repo)
    passes = []

    def sweep(session):
        passes.append(session)
        runtime.stop_session(session)

    monkeypatch.setattr(runtime, "sweep", sweep)
    held = loop.take_lock("s")  # as `loop.running()` from `lado ls` does
    threading.Timer(loop.LOCK_WAIT / 4, held.close).start()
    assert loop.run("s", interval=0) == 0
    assert passes == ["s"]


def test_a_repeating_error_is_logged_once(repo, fake_tmux, monkeypatch, lado_home):
    _session(repo)
    passes = []

    def sweep(session):
        passes.append(session)
        if len(passes) == 1000:
            runtime.stop_session(session)
        elif len(passes) >= 600:
            raise ValueError("another error")
        elif len(passes) != 500:
            raise RuntimeError("tmux not found")

    monkeypatch.setattr(runtime, "sweep", sweep)
    assert loop.run("s", interval=0) == 0
    log = (lado_home / "loop.log").read_text()
    assert log.count("RuntimeError: tmux not found") == 2  # first, and again after pass 500
    assert log.count("ValueError: another error") == 1
    assert "Traceback" in log
    assert "the same error repeated 498 more times" in log
    assert "passes work again" in log
    assert len(log.splitlines()) < 60


def test_a_repeating_error_gets_a_short_line_now_and_then(repo, fake_tmux, monkeypatch, lado_home):
    _session(repo)
    passes = []

    def sweep(session):
        passes.append(session)
        if len(passes) == 4:
            runtime.stop_session(session)
            return
        raise RuntimeError("tmux not found")

    monkeypatch.setattr(runtime, "sweep", sweep)
    monkeypatch.setattr(loop, "REPEAT_NOTE", 0)
    assert loop.run("s", interval=0) == 0
    log = (lado_home / "loop.log").read_text()
    assert log.count("RuntimeError: tmux not found") == 1
    assert log.count("the same error again") == 2


def test_a_stop_during_a_repeating_error_is_no_recovery(repo, fake_tmux, monkeypatch, lado_home):
    _session(repo)
    passes = []

    def sweep(session):
        passes.append(session)
        if len(passes) == 3:
            runtime.stop_session(session)
        raise RuntimeError("tmux not found")

    monkeypatch.setattr(runtime, "sweep", sweep)
    assert loop.run("s", interval=0) == 0
    log = (lado_home / "loop.log").read_text()
    assert "passes work again" not in log  # the last pass swept nothing
    assert "the same error repeated 2 more times" in log
    assert log.splitlines()[-1].endswith("s: loop ended: the session is stopped")


def test_wait_stopped_waits_for_the_loop_to_let_go_of_its_lock(lado_home):
    held = loop.take_lock("s")
    assert not loop.wait_stopped("s", timeout=0.2)
    threading.Timer(0.2, held.close).start()
    assert loop.wait_stopped("s", timeout=5)
    assert loop.wait_stopped("never-ran", timeout=0)
