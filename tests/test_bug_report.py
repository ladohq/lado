import datetime
import json
from urllib.parse import parse_qs, urlsplit

import pytest

from lado import bug_report, doctor, telemetry

NOW = datetime.datetime(2026, 10, 14, 12, 0, tzinfo=datetime.timezone.utc)


def _at(days: float) -> str:
    return telemetry.format_time(NOW - datetime.timedelta(days=days))


def _line(days=0.0, **fields):
    line = {
        "at": _at(days),
        "lado": "0.38.0",
        "where": "hook:turn_end",
        "type": "KeyError",
        "message": "'w1'",
        "traceback": "Traceback ...",
        "session": "s",
        "agent": "w1",
        "chain": [],
        "stack": ["lado/hooks.py:handle:212", "<external>"],
        "fingerprint": "f1",
        "provider": "claude",
    }
    return {**line, **fields}


def _write(lines, name="errors.jsonl"):
    path = telemetry.journal_path().with_name(name)
    path.write_text("".join(json.dumps(line) + "\n" for line in lines))


@pytest.fixture(scope="module")
def system():
    return doctor.system_info(which=lambda cmd: None)


def _build(system, **kwargs):
    return bug_report.build(system, None, now=NOW, **kwargs)


def _query(url):
    query = parse_qs(urlsplit(url).query, keep_blank_values=True)
    return query["title"][0], query["body"][0]


# The journal's lines.


def test_errors_reads_both_files_within_the_window():
    _write([_line(31, type="Old"), _line(29, type="Kept")], "errors.jsonl.1")
    _write([_line(1, type="New")])
    assert [line["type"] for line in bug_report.errors(NOW)] == ["Kept", "New"]


def test_errors_skips_an_unreadable_line():
    path = telemetry.journal_path()
    path.write_text(f'not json\n[1]\n{{"at": 5}}\n{json.dumps(_line(1))}\n')
    assert len(bug_report.errors(NOW)) == 1


def test_errors_keeps_only_the_fields_a_report_may_read():
    _write([_line(1)])
    [line] = bug_report.errors(NOW)
    assert set(line) <= {"at", "lado", "where", "type", "chain", "stack", "fingerprint", "provider"}


def test_no_journal_no_errors():
    assert bug_report.errors(NOW) == []


# Kinds.


def test_the_same_error_three_times_is_one_kind(system):
    _write(
        [
            _line(2, lado="0.37.0"),
            _line(1, lado="0.37.0"),
            _line(0, lado="0.38.0"),
        ]
    )
    report = _build(system)
    assert "### LADO errors (last 30 days, 1 kind)\n" in report.text
    assert (
        "- KeyError at hook:turn_end (claude), 3 times, 2026-10-12 to 2026-10-14, "
        "LADO 0.37.0, 0.38.0\n"
        "  - lado/hooks.py:handle:212\n"
        "  - <external>\n"
    ) in report.text


def test_kinds_are_newest_first_and_once_on_one_day(system):
    _write(
        [
            _line(3, type="ValueError", where="loop", provider=None, fingerprint="f2"),
            _line(1),
        ]
    )
    text = _build(system).text
    assert text.index("- KeyError at") < text.index("- ValueError at")
    assert "- ValueError at loop, once, 2026-10-11, LADO 0.38.0\n" in text


def test_a_line_of_lado_0_37_is_grouped_by_type_and_where_with_no_frames(system):
    old = {k: v for k, v in _line(2).items() if k not in ("chain", "stack", "fingerprint")}
    old.pop("provider")
    _write([old, {**old, "at": _at(1)}, _line(0)])
    kinds = bug_report.kinds(bug_report.errors(NOW))
    assert [(k.count, k.stack) for k in kinds] == [
        (1, ["lado/hooks.py:handle:212", "<external>"]),
        (2, []),
    ]
    assert "- KeyError at hook:turn_end, 2 times, 2026-10-12 to 2026-10-13, LADO 0.38.0\n- " in (
        _build(system).text + "- "
    )


def test_at_most_twelve_frames_the_innermost_kept():
    stack = [f"lado/x.py:f{n}:{n}" for n in range(20)]
    _write([_line(1, stack=stack)])
    [kind] = bug_report.kinds(bug_report.errors(NOW))
    assert kind.stack == stack[-12:]


# Privacy.


def test_a_journal_line_full_of_names_leaves_none_of_them(system):
    _write(
        [
            _line(
                1,
                message="no such file: /Users/ann/acme/.lado/worktrees/billing/dev",
                traceback='File "/Users/ann/acme/x.py", line 1, in billing\n',
                session="billing",
                agent="dev",
            )
        ]
    )
    report = _build(system)
    title, body = _query(report.url)
    for text in (report.text, report.body, report.url, title, body):
        for name in ("/Users/ann", "acme", "billing"):
            assert name not in text
    # "dev" may be in a development version's number: only the errors' part is checked.
    for text in (report.text, report.body):
        assert "dev" not in text.partition("### LADO errors")[2]
    assert "dev" not in title
    assert "KeyError at hook:turn_end" in report.text
    assert "  - lado/hooks.py:handle:212\n" in report.text


def test_no_errors(system):
    report = _build(system)
    assert "No LADO errors in the last 30 days.\n" in report.text
    assert report.title == ""
    assert report.left_out == 0
    assert report.url.startswith(bug_report.ISSUES_NEW + "?title=&body=")


def test_the_text_starts_with_what_happened_then_the_system_info(system):
    text = _build(system).text
    assert text.startswith("### What happened\n\n<!-- ")
    assert text.index("### LADO system info") < text.index("### LADO errors")
    assert "- Server: not running, schema " in text


def test_the_browser_line_follows_the_system_info(system):
    text = _build(system, browser="- Browser: Chrome 141 on macOS").text
    info = doctor.report(system, None)
    assert info + "- Browser: Chrome 141 on macOS\n\n### LADO errors" in text


# The link.


def test_the_title_is_the_newest_kind_cut_to_120(system):
    _write([_line(2, type="Old"), _line(1, type="E" * 200, where="loop", fingerprint="f2")])
    report = _build(system)
    assert report.title == ("E" * 200 + " at loop")[:120]
    assert _query(report.url) == (report.title, report.body)


def test_forty_kinds_fit_the_bound(system):
    _write(
        [
            _line(
                n / 2,
                type=f"Error{n:02}",
                fingerprint=f"f{n}",
                stack=[f"lado/module_{n}.py:function_{m}:{m}" for m in range(12)],
            )
            for n in range(40)
        ]
    )
    report = _build(system)
    assert len(report.url) <= bug_report.MAX_URL
    assert "### LADO errors (last 30 days, 40 kinds)" in report.text
    assert all(f"- Error{n:02} at" in report.text for n in range(40))
    assert report.left_out > 0
    kept = 40 - report.left_out
    assert all(f"- Error{n:02} at" in report.body for n in range(kept))  # the newest
    assert all(f"- Error{n:02} at" not in report.body for n in range(kept, 40))
    assert report.body.endswith(
        f"- {report.left_out} more kinds of errors left out: lado bug-report prints them all\n"
    )
    assert "left out" not in report.text
    assert _query(report.url) == (report.title, report.body)


def test_a_report_that_fits_is_the_body_as_it_is(system):
    _write([_line(1)])
    report = _build(system)
    assert report.body == report.text
    assert report.left_out == 0
