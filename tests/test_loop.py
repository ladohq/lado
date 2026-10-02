from agent_helpers import previous_schema

from lado import loop, runtime, state, tmux


def _session(repo):
    runtime.start_session(str(repo), "s", None)


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


def test_the_loop_stops_on_another_schema_and_does_not_migrate_it(repo, fake_tmux):
    _session(repo)
    previous_schema()
    old = state.SCHEMA_VERSION - 1
    assert loop.why_stop("s") == (
        f"the database has schema version {old}, this loop knows {state.SCHEMA_VERSION}"
    )
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
    runtime.start_session(str(repo), "s", None)
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
