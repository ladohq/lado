import json
import os
import stat

import pytest

from lado import state, telemetry


def _consent(choice, fields=telemetry.FIELDS_VERSION):
    folder = state.home() / "telemetry"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "consent.json").write_text(json.dumps({"choice": choice, "fields": fields}))


def _raise(exc):
    try:
        raise exc
    except type(exc) as caught:
        return caught


def _journal():
    path = state.home() / "errors.jsonl"
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


# The consent and when sending is on.


def test_state_not_chosen_asks(telemetry_on):
    (state.home() / "telemetry" / "consent.json").unlink()
    now = telemetry.state()
    assert now.choice is None
    assert now.ask and not now.on
    assert now.endpoint


def test_state_without_endpoint_never_asks(monkeypatch):
    monkeypatch.delenv("LADO_TELEMETRY", raising=False)
    monkeypatch.delenv("LADO_TELEMETRY_URL", raising=False)
    monkeypatch.setattr(telemetry, "PROJECT_TOKEN", "")
    now = telemetry.state({})
    assert not now.endpoint and not now.ask and not now.on
    _consent("on")
    assert not telemetry.state({}).on


def test_the_project_token_is_an_endpoint():
    assert telemetry.PROJECT_TOKEN.startswith("phc_")
    assert telemetry.state({}).endpoint


@pytest.mark.parametrize(
    ("value", "off"), [("1", True), ("true", True), ("yes", True), ("", False), ("0", False)]
)
def test_do_not_track_switches_off(telemetry_on, value, off):
    now = telemetry.state({"DO_NOT_TRACK": value, "LADO_TELEMETRY_URL": "http://x"})
    assert (now.off_by == f"DO_NOT_TRACK={value}") is off
    assert now.on is not off
    assert not now.ask


def test_lado_telemetry_0_switches_off(telemetry_on):
    now = telemetry.state({"LADO_TELEMETRY": "0", "LADO_TELEMETRY_URL": "http://x"})
    assert now.off_by == "LADO_TELEMETRY=0"
    assert not now.on and not now.ask
    assert now.choice == "on"


def test_old_fields_count_as_not_chosen(telemetry_on, monkeypatch):
    monkeypatch.setattr(telemetry, "FIELDS", {"a": 0, "b": 1})
    monkeypatch.setattr(telemetry, "FIELDS_VERSION", 1)
    _consent("on", fields=0)
    now = telemetry.state()
    assert now.choice == "on" and not now.fields_ok
    assert now.ask and not now.on
    assert now.new_fields == ["b"]


def test_an_unreadable_consent_is_no_choice(telemetry_on):
    (state.home() / "telemetry" / "consent.json").write_text("{not json")
    assert telemetry.state().choice is None


def test_choose_stores_the_fields_version_and_the_owner_only(telemetry_on):
    telemetry.choose("off")
    path = state.home() / "telemetry" / "consent.json"
    stored = json.loads(path.read_text())
    assert stored["choice"] == "off" and stored["fields"] == telemetry.FIELDS_VERSION
    assert stored["at"]
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_choose_off_clears_outbox(telemetry_on):
    telemetry.record("loop", _raise(KeyError("x")))
    telemetry.record("loop", _raise(ValueError("y")))
    assert len(telemetry.queued()) == 2
    telemetry.choose("off")
    assert telemetry.queued() == []
    assert telemetry.dropped() == 0


# The journal.


def test_record_writes_journal_line(monkeypatch):
    monkeypatch.setenv("LADO_TELEMETRY", "0")
    telemetry.record("hook:turn_end", _raise(KeyError("w1")), "claude", session="s", agent="w1")
    [line] = _journal()
    assert set(line) == {"at", "lado", "where", "type", "message", "traceback", "session", "agent"}
    assert line["where"] == "hook:turn_end"
    assert line["type"] == "KeyError"
    assert line["message"] == "'w1'"
    assert "Traceback" in line["traceback"]
    assert (line["session"], line["agent"]) == ("s", "w1")
    mode = (state.home() / "errors.jsonl").stat().st_mode
    assert stat.S_IMODE(mode) == 0o600


def test_record_queues_only_when_on(telemetry_on):
    (state.home() / "telemetry" / "consent.json").unlink()
    telemetry.record("loop", _raise(KeyError("x")))
    assert telemetry.queued() == []
    telemetry.choose("on")
    telemetry.record("loop", _raise(KeyError("x")))
    [event] = telemetry.queued()
    assert event["where"] == "loop" and event["type"] == "KeyError"
    assert len(_journal()) == 2


def test_record_never_raises(tmp_path, monkeypatch):
    home = tmp_path / "a-file"
    home.write_text("")
    monkeypatch.setenv("LADO_HOME", str(home))
    telemetry.record("loop", _raise(KeyError("x")))  # no exception


def test_schema_error_is_never_recorded(telemetry_on):
    telemetry.record("loop", _raise(state.SchemaError("another schema")))
    assert _journal() == [] and telemetry.queued() == []


def test_bounded_append_rotates(tmp_path):
    path = tmp_path / "some.log"
    path.write_text("x" * (telemetry.JOURNAL_MAX + 100_000))
    (tmp_path / "some.log.1").write_text("old")
    telemetry.bounded_append(path, "new line\n")
    assert path.read_text() == "new line\n"
    assert (tmp_path / "some.log.1").stat().st_size == telemetry.JOURNAL_MAX + 100_000


def test_bounded_append_never_raises(tmp_path):
    telemetry.bounded_append(tmp_path / "no-such-folder" / "x.log", "line\n")


def test_outbox_bound_counts_drops(telemetry_on, monkeypatch):
    monkeypatch.setattr(telemetry, "OUTBOX_MAX", 2)
    for _ in range(3):
        telemetry.record("loop", _raise(KeyError("x")))
    assert len(telemetry.queued()) == 2
    assert telemetry.dropped() == 1
    monkeypatch.setattr(telemetry, "DROPPED_MAX", 2)
    for _ in range(5):
        telemetry.record("loop", _raise(KeyError("x")))
    assert (state.home() / "telemetry" / "dropped").stat().st_size == 2
    assert telemetry.dropped() == 2


# Scrubbing.


def test_scrub_leaves_no_path_name_or_token():
    secret, path, name = "sk-live-123", "/Users/ann/work/app", "my-session"

    def fail(token=secret, where=path):
        raise OSError(f"cannot open {path} for {name}")

    try:
        fail()
    except OSError as exc:
        event = telemetry.scrub("hook:turn_end", exc, "claude")
    text = json.dumps(event)
    for leak in (secret, path, name, "ann"):
        assert leak not in text
    assert event["type"] == "OSError"
    assert event["stack"] == ["<external>"]
    assert event["where"] == "hook:turn_end" and event["provider"] == "claude"


def test_scrub_keeps_lado_frames(monkeypatch, tmp_path):
    monkeypatch.setenv("LADO_HOME", str(tmp_path / "secret-home" / "ann"))

    def refuse(*args, **kwargs):
        raise PermissionError(f"no access to {tmp_path}")

    monkeypatch.setattr(type(tmp_path), "mkdir", refuse)
    try:
        state.home()
    except PermissionError as exc:
        event = telemetry.scrub("cli:ls", exc, None)
    assert event["type"] == "PermissionError"
    assert any(frame.startswith("lado/state.py:home:") for frame in event["stack"])
    assert event["stack"][0] == "<external>"  # this test's own frame
    assert all(f.startswith("lado/") or f == "<external>" for f in event["stack"])
    assert str(tmp_path) not in json.dumps(event) and "ann" not in json.dumps(event)


def test_scrub_names_the_chain_and_qualified_types():
    class Inner(Exception):
        pass

    try:
        try:
            raise Inner("secret")
        except Inner as inner:
            raise RuntimeError("other") from inner
    except RuntimeError as exc:
        event = telemetry.scrub("loop", exc, None)
    assert event["type"] == "RuntimeError"
    assert event["chain"] == [f"{__name__}.{Inner.__qualname__}"]
    assert "secret" not in json.dumps(event)


def test_scrub_cuts_where_to_its_name():
    exc = _raise(KeyError("x"))
    assert telemetry.scrub("server:/api/sessions/{name}", exc, None)["where"] == (
        "server:/api/sessions/{name}"
    )
    assert telemetry.scrub("cli:kits add", exc, None)["where"] == "cli:kits add"


def test_fingerprint_ignores_line_numbers():
    stack_a = ["lado/hooks.py:main:276", "<external>", "lado/state.py:home:820"]
    stack_b = ["lado/hooks.py:main:300", "<external>", "lado/state.py:home:900"]
    assert telemetry.fingerprint("KeyError", stack_a) == telemetry.fingerprint("KeyError", stack_b)
    assert telemetry.fingerprint("KeyError", stack_a) != telemetry.fingerprint("OSError", stack_a)
    assert len(telemetry.fingerprint("KeyError", stack_a)) == 16


def test_outbox_files_are_the_owner_s_only(telemetry_on):
    telemetry.record("loop", _raise(KeyError("x")))
    [path] = (state.home() / "telemetry" / "outbox").iterdir()
    assert path.suffix == ".json"
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600
