"""The UI server's end and start in LADO's container: it stops the sessions first and
resumes them in the background (openspec change container-session-restart)."""

import asyncio
import sqlite3
import threading

import pytest
import uvicorn

from lado import runtime, telemetry
from lado.server import app as server_app
from lado.server import auth, run

PORT = 8765


@pytest.fixture
def application(lado_home):
    return server_app.create_app(auth.token(), PORT)


@pytest.fixture
def order(application, monkeypatch):
    """What the shutdown called, in order; uvicorn's own shutdown replaced."""
    calls = []

    async def uvicorns_own(self, sockets=None):
        calls.append("uvicorn")

    monkeypatch.setattr(uvicorn.Server, "shutdown", uvicorns_own)
    close = application.state.hub.close
    monkeypatch.setattr(application.state.hub, "close", lambda: calls.append("hub") or close())
    return calls


def _shutdown(application) -> None:
    asyncio.run(server_app.Server(uvicorn.Config(application)).shutdown())


def test_in_a_container_the_shutdown_stops_the_sessions_before_the_streams(
    application, order, monkeypatch, capsys
):
    monkeypatch.setenv("LADO_CONTAINER", "1")
    monkeypatch.setattr(
        runtime, "stop_for_container", lambda: order.append("sessions") or ["app", "docs"]
    )
    _shutdown(application)
    assert order == ["sessions", "hub", "uvicorn"]
    assert application.state.stopping.is_set()
    assert capsys.readouterr().err == (
        'lado: the container stops: stopped sessions "app", "docs"; they resume at its start\n'
    )


def test_in_a_container_with_no_session_the_shutdown_says_nothing(
    application, order, monkeypatch, capsys
):
    monkeypatch.setenv("LADO_CONTAINER", "1")
    monkeypatch.setattr(runtime, "stop_for_container", lambda: [])
    _shutdown(application)
    assert order == ["hub", "uvicorn"]
    assert capsys.readouterr().err == ""


def test_a_stop_that_fails_does_not_keep_the_server_from_shutting_down(
    application, order, monkeypatch, capsys
):
    monkeypatch.setenv("LADO_CONTAINER", "1")
    recorded = []
    monkeypatch.setattr(telemetry, "record", lambda where, exc, **k: recorded.append(where))

    def locked():
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(runtime, "stop_for_container", locked)
    _shutdown(application)
    assert order == ["hub", "uvicorn"]
    assert recorded == ["server:stop"]
    assert capsys.readouterr().err == (
        "lado: could not stop the sessions at the container's stop: "
        "OperationalError: database is locked\n"
    )


def test_outside_a_container_the_shutdown_leaves_the_sessions(application, order, monkeypatch):
    monkeypatch.delenv("LADO_CONTAINER", raising=False)
    monkeypatch.setattr(runtime, "stop_for_container", lambda: order.append("sessions") or [])
    _shutdown(application)
    assert order == ["hub", "uvicorn"]


def test_in_a_container_the_start_resumes_in_the_background(application, monkeypatch, capsys):
    monkeypatch.setenv("LADO_CONTAINER", "1")
    got = []
    done = threading.Event()

    def resume(report, stopping):
        got.append(stopping)
        report("lado: resumed")
        done.set()

    monkeypatch.setattr(runtime, "resume_at_start", resume)
    thread = run.resume_sessions(application)
    assert thread is not None and thread.daemon
    assert done.wait(5)
    thread.join(5)
    assert got == [application.state.stopping]
    assert capsys.readouterr().err == "lado: resumed\n"


def test_a_resume_that_breaks_off_is_one_line(application, monkeypatch, capsys):
    monkeypatch.setenv("LADO_CONTAINER", "1")
    recorded = []
    monkeypatch.setattr(telemetry, "record", lambda where, exc, **k: recorded.append(where))

    def locked(report, stopping):
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(runtime, "resume_at_start", locked)
    run.resume_sessions(application).join(5)
    assert recorded == ["server:resume"]
    assert capsys.readouterr().err == (
        "lado: could not resume the sessions: OperationalError: database is locked\n"
    )


def test_outside_a_container_the_start_resumes_nothing(application, monkeypatch):
    monkeypatch.delenv("LADO_CONTAINER", raising=False)
    monkeypatch.setattr(runtime, "resume_at_start", lambda *a: pytest.fail("resumed"))
    assert run.resume_sessions(application) is None
