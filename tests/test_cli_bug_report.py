"""`lado bug-report` (lado.bug_report, cli.cmd_bug_report)."""

import io
import json
import os
import sqlite3
import sys
import webbrowser

import pytest

from lado import bug_report, cli, state, telemetry
from lado.server import run as server_run


class _Tty(io.StringIO):
    def isatty(self):
        return True


@pytest.fixture
def opened(monkeypatch):
    """The links webbrowser.open was asked to open."""
    calls = []

    def fake_open(url, *args, **kwargs):
        calls.append(url)
        return True

    monkeypatch.setattr(webbrowser, "open", fake_open)
    return calls


@pytest.fixture
def terminal(monkeypatch, capsys):
    """`terminal(text)`: stdin and stdout as terminals where a browser can show, and `text`
    what the human types. Called in the test: capsys's stdout is the test's own there."""
    monkeypatch.setattr(bug_report, "can_show_browser", lambda: True)

    def answer(text, stdin=_Tty):
        monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
        monkeypatch.setattr(sys, "stdin", stdin(text))

    return answer


def _run():
    return cli.main(["bug-report"])


def test_the_test_run_never_opens_a_browser():
    """Like LADO_TELEMETRY=0: a test that forgot to replace webbrowser.open opens nothing."""
    assert os.environ.get("BROWSER") == "true"


def test_without_a_terminal_it_prints_and_asks_nothing(opened, capsys):
    assert _run() == 0
    out = capsys.readouterr().out
    assert out.startswith(bug_report.WARNING + "\n### What happened\n")
    assert "### LADO system info\n" in out
    assert "No LADO errors in the last 30 days.\n" in out
    assert f"\nOpen a new issue: {bug_report.ISSUES_NEW}?title=&body=" in out
    assert "Open it in the browser?" not in out
    assert opened == []


@pytest.mark.parametrize("typed", ["y\n", "yes\n", "Y\n"])
def test_yes_opens_the_link(terminal, opened, capsys, typed):
    terminal(typed)
    assert _run() == 0
    out = capsys.readouterr().out
    assert "Open it in the browser? [y/N] " in out
    [url] = opened
    assert url.startswith(bug_report.ISSUES_NEW + "?title=")
    assert f"Open a new issue: {url}\n" in out


@pytest.mark.parametrize("typed", ["\n", "n\n", ""])  # Enter, n, EOF
def test_anything_else_opens_nothing(terminal, opened, capsys, typed):
    terminal(typed)
    assert _run() == 0
    assert "Open it in the browser? [y/N] " in capsys.readouterr().out
    assert opened == []


def test_ctrl_c_opens_nothing(terminal, opened, capsys):
    class Interrupted(_Tty):
        def readline(self, *args):
            raise KeyboardInterrupt

    terminal("y\n", Interrupted)
    assert _run() == 0
    assert "Open it in the browser? [y/N] " in capsys.readouterr().out
    assert opened == []


@pytest.mark.parametrize("fails", ["false", "raises"])
def test_a_browser_that_does_not_open(terminal, monkeypatch, capsys, fails):
    terminal("y\n")

    def fake_open(url, *args, **kwargs):
        if fails == "raises":
            raise webbrowser.Error("could not locate runnable browser")
        return False

    monkeypatch.setattr(webbrowser, "open", fake_open)
    assert _run() == 0
    assert "could not open a browser: open the link above\n" in capsys.readouterr().out


def test_no_question_where_no_browser_can_show(terminal, opened, monkeypatch, capsys):
    monkeypatch.setattr(bug_report, "can_show_browser", lambda: False)
    terminal("y\n")
    assert _run() == 0
    assert "Open it in the browser?" not in capsys.readouterr().out
    assert opened == []


# Where a browser can show.


@pytest.mark.parametrize(
    ("environ", "shows"),
    [
        ({}, False),  # over ssh
        ({"DISPLAY": ":0"}, True),
        ({"WAYLAND_DISPLAY": "wayland-0"}, True),
        ({"BROWSER": "firefox"}, True),
        ({"DISPLAY": ""}, False),
    ],
)
def test_can_show_browser_on_linux(monkeypatch, environ, shows):
    monkeypatch.setattr(bug_report.sys, "platform", "linux")
    assert bug_report.can_show_browser(environ) is shows


@pytest.mark.parametrize(("place", "shows"), [("gui", True), ("remote", False), ("no-gui", False)])
def test_can_show_browser_on_a_mac(monkeypatch, place, shows):
    monkeypatch.setattr(bug_report.sys, "platform", "darwin")
    monkeypatch.setenv("LADO_MACOS_PLACE", place)
    assert bug_report.can_show_browser({"DISPLAY": ":0"}) is shows


# lado.db and the server.


def test_a_newer_lado_db_is_reported_and_left_as_it_is(capsys):
    with state.connect():
        pass
    path = state.home() / "lado.db"
    newer = state.SCHEMA_VERSION + 1
    with sqlite3.connect(path) as db:
        db.execute(f"PRAGMA user_version = {newer}")
    assert _run() == 0
    assert f", schema {newer}\n" in capsys.readouterr().out
    with sqlite3.connect(path) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == newer


def test_no_lado_db(capsys):
    assert _run() == 0
    assert "- Server: not running, schema none\n" in capsys.readouterr().out
    assert not (state.home() / "lado.db").exists()


def test_a_running_server_open_to_the_network(capsys):
    state.home()
    server_run.info_path().write_text(
        json.dumps({"url": "http://127.0.0.1:8040", "host": "0.0.0.0", "port": 8040, "pid": 1})
    )
    lock = server_run.take_lock()
    try:
        assert _run() == 0
    finally:
        lock.close()
    out = capsys.readouterr().out
    assert "- Server: running, open to the network, schema " in out
    assert "0.0.0.0" not in out and "8040" not in out


def test_the_errors_of_the_journal_are_in_it(capsys):
    try:
        raise KeyError("/Users/ann/acme")
    except KeyError as exc:
        telemetry.record("cli:ls", exc, None, session="billing", agent="dev")
    assert _run() == 0
    out = capsys.readouterr().out
    assert "- KeyError at cli:ls, once, " in out
    assert "acme" not in out and "billing" not in out
