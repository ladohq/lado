"""`lado stats` (lado.stats): the usage of a period, read from this machine only."""

import datetime
import json
import socket

import pytest

from lado import state, stats, telemetry
from lado.cli import main

NOW = datetime.datetime(2026, 10, 14, 12, 0, tzinfo=datetime.timezone.utc)


def _write(rows: list[tuple]) -> None:
    """Rows of the usage table as its triggers write them (tests/test_usage.py checks those):
    (kind, key, provider, agrees, created_at)."""
    with state.connect() as db:
        db.executemany(
            "INSERT INTO usage (kind, key, provider, agrees, created_at) VALUES (?, ?, ?, ?, ?)",
            rows,
        )


def _at(days_ago: float, now: datetime.datetime = NOW) -> str:
    return f"{now - datetime.timedelta(days=days_ago):%Y-%m-%d %H:%M:%S.000}"


def _times(n: int, kind: str, key=None, provider=None, agrees=None, days_ago=1.0) -> list[tuple]:
    return [(kind, key, provider, agrees, _at(days_ago))] * n


def _month() -> None:
    """A month of usage, the earliest row on 2026-10-01."""
    rows = [
        ("session", None, None, None, "2026-10-01 09:30:00"),
        *_times(7, "session", days_ago=5),
        *_times(4, "resume"),
        *_times(15, "agent", "developer@sdlc", "claude"),
        *_times(12, "agent", "supervisor@default", "claude"),
        *_times(3, "agent", "reviewer@sdlc", "claude"),
        *_times(8, "agent", "reviewer@sdlc", "codex"),
        *_times(1, "agent", "reviewer@sdlc", "kilo"),
        *_times(2, "agent", "developer@?", "kilo"),
        *_times(1, "agent_ended", provider="claude"),
        *_times(1, "agent_ended", provider="kilo"),
        *_times(2, "turn_error", "overloaded", "claude"),
        *_times(1, "turn_error", "rate_limit", "claude"),
        *_times(1, "turn_error", "APIError", "kilo"),
        *_times(7, "run_start", "task@sdlc"),
        *_times(2, "run_start", "hotfix@sdlc"),
        *_times(6, "run_end", "task@sdlc"),
        *_times(1, "run_cancel", "hotfix@sdlc"),
        *_times(15, "gate_open", "approval"),
        *_times(1, "gate_open", "choice"),
        *_times(1, "gate_open", "loop"),
        *_times(12, "gate_close", "approve", agrees=1),
        *_times(2, "gate_close", "reject", agrees=0),
        *_times(1, "gate_close", "reject"),
        *_times(1, "gate_close", "cancelled"),
        *_times(23, "question"),
        *_times(1, "message_failed"),
        *_times(5, "message_dropped"),
    ]
    _write(rows)


def _errors(*ats: str) -> None:
    telemetry.journal_path().write_text("".join(json.dumps({"at": at}) + "\n" for at in ats))


def test_the_lines_of_a_month(lado_home):
    _month()
    _errors("2026-10-10T08:00:00Z", "2026-10-12T08:00:00Z", "2026-08-01T08:00:00Z")
    assert stats.lines(30, NOW) == [
        "Usage from 2026-09-14 to 2026-10-14 (UTC, 30 days) on this machine; nothing is sent.",
        "Earliest record: 2026-10-01.",
        "",
        "Sessions",
        "  started                       8",
        "  resumed                       4",
        "Agents",
        "  started                      41  claude 30, codex 8, kilo 3",
        "  by role                          developer@sdlc 15, reviewer@sdlc 12,",
        "                                   supervisor@default 12, developer@? 2",
        "                                   (@?: kit not recorded, before 0.38.0)",
        "  ended by themselves           2  claude 1, kilo 1",
        "  turns ended on an error       4  claude 3 (overloaded 2, rate_limit 1),",
        "                                   kilo 1 (APIError 1)",
        "Flow runs",
        "  started                       9  task@sdlc 7, hotfix@sdlc 2",
        "  ended                         6",
        "  cancelled                     1",
        "Gates and questions",
        "  gates opened                 17  approval 15, choice 1, loop 1",
        "  gates closed                 16  approve 12, reject 3, cancelled 1",
        "  answered as the lead advised 12 of 14 with a recommended choice",
        "  questions to you             23",
        "Messages",
        "  failed to deliver             1",
        "  dropped                       5",
        "LADO",
        "  own errors                    2  (errors.jsonl keeps only its latest part)",
    ]


def test_an_empty_history_prints_zeros_and_no_record(lado_home):
    out = stats.lines(30, NOW)
    assert out[1] == "Earliest record: none yet."
    assert "  started                       0" in out
    assert "  answered as the lead advised     no recommended choice" in out
    assert "  own errors                    0  (errors.jsonl keeps only its latest part)" in out
    assert not any("@?" in line for line in out)


def test_a_breakdown_lists_the_larger_first_then_by_name(lado_home):
    _write(
        _times(1, "agent", "b@k", "codex")
        + _times(2, "agent", "a@k", "claude")
        + _times(1, "agent", "a@j", "kilo")
    )
    out = stats.lines(30, NOW)
    assert "  started                       4  claude 2, codex 1, kilo 1" in out
    assert "  by role                          a@k 2, a@j 1, b@k 1" in out


def _run_stats(capsys, *args: str) -> str:
    capsys.readouterr()
    assert main(["stats", *args]) == 0
    return capsys.readouterr().out


def _two_sessions() -> datetime.datetime:
    """Sessions started 3 and 40 days ago, the first with three claude agents and one
    codex agent."""
    now = telemetry.now()
    rows = [
        ("session", None, None, None, _at(3, now)),
        ("session", None, None, None, _at(40, now)),
        *[("agent", "worker@default", "claude", None, _at(3, now))] * 3,
        ("agent", "worker@default", "codex", None, _at(3, now)),
    ]
    _write(rows)
    return now


def test_the_default_period_is_30_days(lado_home, capsys):
    now = _two_sessions()
    out = _run_stats(capsys)
    start = now - datetime.timedelta(days=30)
    assert out.startswith(f"Usage from {start:%Y-%m-%d} to {now:%Y-%m-%d} (UTC, 30 days)")
    assert "Earliest record" not in out
    assert "  started                       1\n" in out
    assert "  started                       4  claude 3, codex 1\n" in out


def test_all_counts_everything_kept_and_names_the_earliest_record(lado_home, capsys):
    now = _two_sessions()
    out = _run_stats(capsys, "--all")
    assert out.startswith(f"Usage of everything kept, to {now:%Y-%m-%d} (UTC) on this machine")
    first = now - datetime.timedelta(days=40)
    assert f"Earliest record: {first:%Y-%m-%d}." in out
    assert "  started                       2\n" in out


def test_a_period_longer_than_the_history_names_its_earliest_record(lado_home, capsys):
    now = telemetry.now()
    _write([("question", None, None, None, _at(5, now))])
    out = _run_stats(capsys, "--days", "90")
    assert "(UTC, 90 days)" in out.splitlines()[0]
    assert f"Earliest record: {now - datetime.timedelta(days=5):%Y-%m-%d}." in out


def test_the_agreement_counts_only_the_closes_with_a_recommended_choice(lado_home):
    _write(
        _times(2, "gate_close", "approve", agrees=1)
        + _times(1, "gate_close", "approve", agrees=0)
        + _times(1, "gate_close", "reject")
        + _times(1, "gate_close", "cancelled")  # closed by no answer: no agreement
        + _times(1, "gate_close", "overridden")
    )
    out = stats.lines(30, NOW)
    assert "  answered as the lead advised  2 of 3 with a recommended choice" in out
    at = out.index("  gates closed                  6  approve 3, cancelled 1, overridden 1,")
    assert out[at + 1] == " " * stats.BREAKDOWN + "reject 1"  # still counted as closed


@pytest.mark.parametrize("args", [["--days", "0"], ["--days", "x"], ["--days", "7", "--all"]])
def test_bad_options_exit_2(lado_home, capsys, args):
    with pytest.raises(SystemExit) as exited:
        main(["stats", *args])
    assert exited.value.code == 2
    assert "usage: lado stats" in capsys.readouterr().err


def test_stats_opens_no_socket_and_starts_no_sender(telemetry_on, monkeypatch, capsys):
    """Statistics on and a report due: still nothing goes out."""

    def refused(*args, **kwargs):
        raise AssertionError("lado stats opened a connection")

    monkeypatch.setattr(socket.socket, "connect", refused)
    monkeypatch.setattr(socket, "create_connection", refused)
    started = []
    monkeypatch.setattr(telemetry, "kick", lambda: started.append("kick"))
    telemetry.record("loop", KeyError("x"))
    folder = state.home() / "telemetry"
    before = sorted((p.name, p.read_bytes()) for p in folder.rglob("*") if p.is_file())
    assert telemetry.state().on
    out = _run_stats(capsys)
    assert "nothing is sent" in out
    assert started == []
    assert sorted((p.name, p.read_bytes()) for p in folder.rglob("*") if p.is_file()) == before
