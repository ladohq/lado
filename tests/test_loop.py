import os
import subprocess
import sys
import threading
import time

import pytest
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


def test_the_loop_stops_when_the_tmux_session_is_gone(repo, fake_tmux, lado_home):
    _session(repo)
    tmux.kill_session("s")
    assert loop.run("s", interval=0) == 0
    last = (lado_home / "loop.log").read_text().splitlines()[-1]
    assert last.endswith("s: loop ended: its tmux session is gone")


# The real ones, before fake_tmux replaces them: the tests of a pass's tmux calls.
REAL_HAS_SESSION, REAL_LIST_WINDOWS = tmux.has_session, tmux.list_windows


@pytest.fixture
def tmux_server(fake_tmux, monkeypatch):
    """A stand-in tmux server under tmux's own calls: the commands run (their names, in
    `calls`), and what it answers (`alive`: the session is there; `fails`: why list-windows
    fails, or None; `missing`: tmux cannot run)."""
    monkeypatch.setattr(tmux, "has_session", REAL_HAS_SESSION)
    monkeypatch.setattr(tmux, "list_windows", REAL_LIST_WINDOWS)
    server = {"calls": [], "alive": True, "fails": None, "missing": False}

    def run_once(args, input):
        server["calls"].append(args[0])
        if server["missing"]:
            raise tmux.TmuxMissing("tmux is not installed or not on PATH ()")
        if not server["alive"]:
            raise tmux.TmuxError("can't find session: s")
        if args[0] == "list-windows":
            if server["fails"]:
                raise tmux.TmuxError(server["fails"])
            return "supervisor\n"
        assert args[0] == "has-session", args
        return ""

    monkeypatch.setattr(tmux, "_run_once", run_once)
    return server


def _stop_after(passes, monkeypatch, count):
    """Stop the session (in the database only) after `count` passes, counted by the loop's
    sleeps; each pass's tmux calls go to `passes`."""

    def sleep(seconds):
        passes.append(seconds)
        if len(passes) == count:
            state.stop_session("s")

    monkeypatch.setattr(loop.time, "sleep", sleep)


def test_a_pass_makes_one_tmux_call(repo, tmux_server, monkeypatch):
    _session(repo)
    swept = []
    monkeypatch.setattr(runtime, "sweep", swept.append)
    _stop_after([], monkeypatch, 2)
    assert loop.run("s", interval=0) == 0
    assert swept == ["s", "s"]
    assert tmux_server["calls"] == ["list-windows", "list-windows"]


def test_a_gone_tmux_session_ends_the_loop_with_its_reason(
    repo, tmux_server, monkeypatch, lado_home
):
    _session(repo)
    swept = []
    monkeypatch.setattr(runtime, "sweep", swept.append)
    tmux_server["alive"] = False
    assert loop.run("s", interval=0) == 0
    assert tmux_server["calls"] == ["list-windows", "has-session"]  # asked only on failure
    assert swept == []
    log = (lado_home / "loop.log").read_text()
    assert log.splitlines()[-1].endswith("s: loop ended: its tmux session is gone")
    assert "error in a pass" not in log


def test_a_failing_window_list_of_a_live_session_is_an_error_of_the_pass(
    repo, tmux_server, monkeypatch, lado_home
):
    _session(repo)
    swept = []
    monkeypatch.setattr(runtime, "sweep", swept.append)
    monkeypatch.setattr(loop, "INTERVAL", 0)  # the supervisor is no new agent: it may be found gone
    tmux_server["fails"] = "server busy"
    _stop_after([], monkeypatch, 3)
    assert loop.run("s", interval=0) == 0
    assert tmux_server["calls"] == ["list-windows", "has-session"] * 3
    assert swept == []
    log = (lado_home / "loop.log").read_text()
    assert "TmuxError: server busy" in log
    assert log.splitlines()[-1].endswith("s: loop ended: the session is stopped")
    assert {a.name for a in state.list_agents("s") if a.status == state.STOPPED} == set()
    assert not [e for e in state.list_events("s") if e.kind == "ended"]


def test_a_missing_tmux_is_an_error_of_the_pass(repo, tmux_server, monkeypatch, lado_home):
    _session(repo)
    tmux_server["missing"] = True
    _stop_after([], monkeypatch, 2)
    assert loop.run("s", interval=0) == 0
    log = (lado_home / "loop.log").read_text()
    assert tmux_server["calls"] == ["list-windows", "list-windows"]
    assert "TmuxMissing: tmux is not installed or not on PATH" in log
    assert log.splitlines()[-1].endswith("s: loop ended: the session is stopped")


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


def test_each_pass_looks_at_the_windows_with_what_the_one_before_missed(
    repo, fake_tmux, monkeypatch
):
    _session(repo)
    looks = []

    def check_windows(session, missing):
        looks.append(set(missing))
        if len(looks) == 3:
            runtime.stop_session(session)
        return {f"gone-{len(looks)}"}

    monkeypatch.setattr(runtime, "check_windows", check_windows)
    assert loop.run("s", interval=0) == 0
    assert looks == [set(), {"gone-1"}, {"gone-2"}]


def test_the_windows_are_looked_at_before_the_sweep(repo, fake_tmux, monkeypatch):
    """A message to an agent found ended is dropped and told, not typed into no window."""
    _session(repo)
    calls = []
    monkeypatch.setattr(runtime, "check_windows", lambda s, m: calls.append("check") or set())

    def sweep(session):
        calls.append("sweep")
        runtime.stop_session(session)

    monkeypatch.setattr(runtime, "sweep", sweep)
    loop.run("s", interval=0)
    assert calls == ["check", "sweep"]


@pytest.mark.parametrize(("value", "seconds"), [(None, 2.0), ("0.25", 0.25), (" 3 ", 3.0)])
def test_the_loop_interval_is_lado_loop_interval_else_two_seconds(value, seconds):
    assert loop.interval_from(value) == seconds


@pytest.mark.parametrize("value", ["", "fast", "0", "-1", "nan", "inf"])
def test_a_loop_interval_that_is_no_positive_number_is_refused(value):
    with pytest.raises(ValueError, match="LADO_LOOP_INTERVAL must be a positive number"):
        loop.interval_from(value)


def _interval_in_a_process(value: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "LADO_LOOP_INTERVAL": value}
    code = "from lado import loop; print(repr(loop.INTERVAL))"
    return subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True)


def test_lado_loop_interval_replaces_the_interval_in_the_processes_started_with_it():
    assert _interval_in_a_process("0.25").stdout.strip() == "0.25"


def test_an_invalid_lado_loop_interval_stops_the_process_loudly():
    started = _interval_in_a_process("fast")
    assert started.returncode != 0
    assert "LADO_LOOP_INTERVAL must be a positive number of seconds, not 'fast'" in started.stderr


def test_wait_stopped_waits_three_intervals_by_default(lado_home, monkeypatch):
    monkeypatch.setattr(loop, "INTERVAL", 0.05)
    held = loop.take_lock("s")
    begun = time.monotonic()
    assert not loop.wait_stopped("s")
    assert time.monotonic() - begun < 1
    held.close()


def test_the_loop_sweeps_every_interval_and_logs_it(repo, fake_tmux, monkeypatch, lado_home):
    _session(repo)
    monkeypatch.setattr(loop, "INTERVAL", 0.01)
    sleeps = []
    monkeypatch.setattr(runtime, "sweep", runtime.stop_session)
    monkeypatch.setattr(loop.time, "sleep", sleeps.append)
    assert loop.run("s") == 0
    assert sleeps == [0.01]
    log = (lado_home / "loop.log").read_text()
    assert f"s: loop started, pid {os.getpid()}, a pass every 0.01 s" in log
