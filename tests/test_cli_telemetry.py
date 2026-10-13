"""`lado telemetry` and the question of `lado start` and `lado ui` (lado.telemetry)."""

import io
import json

import pytest

from lado import cli, runtime, state, telemetry


class _Tty(io.StringIO):
    def isatty(self):
        return True


def _stored():
    path = state.home() / "telemetry" / "consent.json"
    return json.loads(path.read_text())["choice"] if path.exists() else None


@pytest.fixture
def not_chosen(telemetry_on):
    (state.home() / "telemetry" / "consent.json").unlink()


def _raise(exc):
    try:
        raise exc
    except type(exc) as caught:
        return caught


# status


def test_status_lines(telemetry_on, monkeypatch):
    monkeypatch.setattr(telemetry, "now", lambda: telemetry.parse_time("2026-10-13T09:00:00Z"))
    telemetry.choose("on")
    assert telemetry.status_lines()[0] == "statistics: on (chosen 2026-10-13)"
    assert telemetry.status_lines()[1] == "last sent: never · waiting: 1 report, 0 errors"
    telemetry.record("loop", _raise(KeyError("x")))
    folder = state.home() / "telemetry"
    (folder / "sent.json").write_text(
        json.dumps({"sent_at": "2026-10-13T08:00:00Z", "report_at": "2026-10-13T08:00:00Z"})
    )
    lines = telemetry.status_lines()
    assert lines[1].startswith("last sent: 2026-10-13 ")
    assert lines[1].endswith(" · waiting: 0 reports, 1 error")
    (folder / "sent.json").write_text(json.dumps({"error": "HTTP 403"}))
    assert telemetry.status_lines()[2] == "last try failed: HTTP 403"
    telemetry.choose("off")
    assert telemetry.status_lines() == ["statistics: off"]
    (folder / "consent.json").unlink()
    assert telemetry.status_lines() == ["statistics: not chosen (lado telemetry on|off)"]


def test_status_off_by_the_environment(telemetry_on, monkeypatch, capsys):
    monkeypatch.setenv("DO_NOT_TRACK", "1")
    assert cli.main(["telemetry", "status"]) == 0
    out = capsys.readouterr().out
    assert out == "statistics: off: DO_NOT_TRACK=1 is set (your choice: on)\n"


def test_status_without_an_endpoint(monkeypatch, capsys):
    monkeypatch.delenv("LADO_TELEMETRY")
    monkeypatch.setattr(telemetry, "PROJECT_TOKEN", "")
    assert cli.main(["telemetry"]) == 0
    assert capsys.readouterr().out == "statistics: off: this LADO has no statistics endpoint\n"


# on, off


def test_on_and_off(not_chosen, capsys):
    assert cli.main(["telemetry", "on"]) == 0
    assert _stored() == "on"
    assert capsys.readouterr().out == "statistics: on (lado telemetry off to stop)\n"
    telemetry.record("loop", _raise(KeyError("x")))
    assert cli.main(["telemetry", "off"]) == 0
    assert _stored() == "off"
    assert telemetry.queued() == []
    assert capsys.readouterr().out == "statistics: off\n"


@pytest.mark.parametrize("choice", ["on", "off"])
def test_on_off_refused_inside_agent(not_chosen, monkeypatch, capsys, choice):
    monkeypatch.setenv("LADO_AGENT", "w1")
    assert cli.main(["telemetry", choice]) == 1
    assert _stored() is None
    assert "lado telemetry on|off is for the human, not an agent" in capsys.readouterr().err


# show, send


def test_show_prints_the_report_and_the_errors(telemetry_on, monkeypatch, capsys):
    monkeypatch.setattr(telemetry, "_providers", dict)
    monkeypatch.setattr(telemetry, "now", lambda: telemetry.parse_time("2026-10-13T09:00:00Z"))
    telemetry.record("loop", _raise(KeyError("x")))
    assert cli.main(["telemetry", "show"]) == 0
    out = capsys.readouterr().out
    shown = telemetry.preview()
    assert out.startswith("the next daily report:\n")
    assert json.dumps(shown["report"], indent=2) in out
    assert "errors waiting to be sent:\n" in out
    assert json.dumps(shown["errors"][0], indent=2) in out
    assert telemetry.TEST_TOKEN not in out and telemetry.PROJECT_TOKEN not in out


def test_send_is_hidden_and_posts(telemetry_endpoint, monkeypatch, capsys):
    monkeypatch.setattr(telemetry, "_providers", dict)
    assert cli.main(["telemetry", "send"]) == 0
    assert len(telemetry_endpoint.requests) == 1
    assert capsys.readouterr() == ("", "")
    with pytest.raises(SystemExit):
        cli.main(["telemetry", "--help"])
    listed = [
        line.split()[0] for line in capsys.readouterr().out.splitlines() if line[:4] == " " * 4
    ]
    assert listed == ["status", "on", "off", "show"]


def test_telemetry_commands_do_not_migrate(monkeypatch, capsys):
    migrated = []
    monkeypatch.setattr(runtime, "migrate_if_safe", lambda: migrated.append(1))
    for args in (["telemetry"], ["telemetry", "show"], ["telemetry", "off"]):
        cli.main(args)
    assert migrated == []


# The question of lado start and lado ui.


def test_start_asks_on_tty_and_stores(not_chosen):
    stderr = _Tty()
    telemetry.ask_if_needed(_Tty("y\n"), stderr)
    assert _stored() == "on"
    text = stderr.getvalue()
    assert text.startswith("LADO can send anonymous usage statistics")
    assert "Send them? [y/N] " in text
    assert text.endswith("statistics: on (lado telemetry off to stop)\n")


@pytest.mark.parametrize("answer", ["\n", "n\n", "no\n"])
def test_enter_or_no_is_off(not_chosen, answer):
    stderr = _Tty()
    telemetry.ask_if_needed(_Tty(answer), stderr)
    assert _stored() == "off"
    assert stderr.getvalue().endswith("statistics: off\n")


def test_eof_stores_nothing(not_chosen):
    telemetry.ask_if_needed(_Tty(""), _Tty())
    assert _stored() is None


def test_ctrl_c_stores_nothing(not_chosen):
    class Interrupted(_Tty):
        def readline(self, *args):
            raise KeyboardInterrupt

    telemetry.ask_if_needed(Interrupted(), _Tty())
    assert _stored() is None


def test_start_does_not_ask_without_tty(not_chosen):
    stderr = _Tty()
    telemetry.ask_if_needed(io.StringIO("y\n"), stderr)
    telemetry.ask_if_needed(_Tty("y\n"), io.StringIO())
    assert _stored() is None and stderr.getvalue() == ""


def test_start_does_not_ask_inside_agent(not_chosen, monkeypatch):
    monkeypatch.setenv("LADO_AGENT", "supervisor")
    stderr = _Tty()
    telemetry.ask_if_needed(_Tty("y\n"), stderr)
    assert _stored() is None and stderr.getvalue() == ""


def test_no_question_once_chosen_or_off(telemetry_on, monkeypatch):
    stderr = _Tty()
    telemetry.ask_if_needed(_Tty("n\n"), stderr)  # chosen: on
    monkeypatch.setenv("DO_NOT_TRACK", "1")
    (state.home() / "telemetry" / "consent.json").unlink()
    telemetry.ask_if_needed(_Tty("n\n"), stderr)
    assert stderr.getvalue() == "" and _stored() is None


def test_question_names_new_fields(telemetry_on, monkeypatch):
    monkeypatch.setattr(telemetry, "FIELDS", {**telemetry.FIELDS, "models": 2})
    monkeypatch.setattr(telemetry, "FIELDS_VERSION", 2)
    stderr = _Tty()
    telemetry.ask_if_needed(_Tty("y\n"), stderr)
    assert stderr.getvalue().startswith("LADO now also sends: models.\n")
    assert telemetry.state().on


@pytest.mark.parametrize("command", [["start", "/no/such/folder"], ["ui", "--no-open"]])
def test_start_and_ui_ask_first(not_chosen, monkeypatch, command):
    asked = []
    monkeypatch.setattr(telemetry, "ask_if_needed", lambda *a: asked.append(1))
    import lado.server.run as server_run

    def stop_here():
        raise runtime.LadoError("stopped by the test")

    monkeypatch.setattr(server_run, "running", stop_here)
    assert cli.main(command) == 1  # a folder that is not there, or the test's stop
    assert asked == [1]


def test_main_kicks_after_a_human_s_command(monkeypatch):
    kicked = []
    monkeypatch.setattr(telemetry, "kick", lambda: kicked.append(1))
    cli.main(["ls"])
    assert kicked == [1]
    cli.main(["telemetry", "send"])
    assert kicked == [1]


def test_doctor_kicks_too_and_migrates_nothing(monkeypatch, capsys):
    from lado import doctor

    kicked, migrated = [], []
    monkeypatch.setattr(telemetry, "kick", lambda: kicked.append(1))
    monkeypatch.setattr(runtime, "migrate_if_safe", lambda: migrated.append(1))
    monkeypatch.setattr(doctor, "main", lambda: 0)
    assert cli.main(["doctor"]) == 0
    assert (kicked, migrated) == ([1], [])


def test_update_starts_nothing_after_the_installer(monkeypatch):
    """After the installer the old process starts nothing of its own (self_update.py):
    no statistics sender either (F3)."""
    kicked = []
    monkeypatch.setattr(telemetry, "kick", lambda: kicked.append(1))
    monkeypatch.setattr(cli, "cmd_update", lambda args: 0)
    assert cli.main(["update", "--yes"]) == 0
    assert kicked == []
