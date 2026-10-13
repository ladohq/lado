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


# The daily report.


def _db_with_usage():
    """Usage in lado.db: some of it a day and a half ago, the rest an hour ago."""
    old, new = "2026-10-11 12:00:00.000", "2026-10-13 08:00:00.000"
    with state.connect() as db:
        for name, at in (("a", old), ("b", new), ("c", new)):
            db.execute(
                "INSERT INTO sessions (name, repo, created_at) VALUES (?, '/r', ?)", (name, at)
            )
        rows = [
            ("b", state.SPAWNED, state.spawned_detail("worker", "claude"), new),
            ("b", state.SPAWNED, state.spawned_detail("supervisor", "claude"), new),
            ("c", state.SPAWNED, state.spawned_detail("worker", "codex"), new),
            ("a", state.SPAWNED, state.spawned_detail("worker", "codex"), old),
            ("a", state.SESSION_RESUME, "", new),
            ("b", state.FLOW_START, "", new),
            ("b", state.GATE_OPEN, "", new),
            ("b", state.GATE_OPEN, "", old),
            ("c", state.TURN_ERROR, "overloaded", new),
        ]
        for session, kind, detail, at in rows:
            db.execute(
                "INSERT INTO events (session, agent, kind, detail, created_at) "
                "VALUES (?, 'x', ?, ?, ?)",
                (session, kind, detail, at),
            )


NOW = telemetry.parse_time("2026-10-13T09:00:00Z")


def _sent(**fields):
    folder = state.home() / "telemetry"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "sent.json").write_text(json.dumps(fields))


def test_spawned_provider_reads_what_is_written():
    assert state.spawned_provider(state.spawned_detail("a role, provider x", "codex")) == "codex"
    assert state.spawned_provider("something else") is None


def test_report_counts_window(telemetry_on, monkeypatch):
    monkeypatch.setattr(telemetry, "_providers", lambda: {"claude": "2.1.296"})
    _db_with_usage()
    _sent(report_at="2026-10-12T09:00:00Z")
    event = telemetry.report(NOW)
    assert event["event"] == telemetry.DAILY
    props = event["properties"]
    assert props["since"] == "2026-10-12T09:00:00Z"
    assert props["sessions"] == 3  # b and c started, a resumed
    assert props["agents"] == {"claude": 2, "codex": 1}
    assert (props["runs"], props["gates"], props["turn_errors"]) == (1, 1, 1)
    assert props["providers"] == {"claude": "2.1.296"}
    assert props["$process_person_profile"] is False and props["$geoip_disable"] is True
    assert event["distinct_id"] == props["install"]
    assert set(props) - {"$process_person_profile", "$geoip_disable"} <= set(telemetry.FIELDS)
    assert "db" not in props


def test_report_first_one_counts_a_day(telemetry_on, monkeypatch):
    monkeypatch.setattr(telemetry, "_providers", dict)
    assert telemetry.report(NOW)["properties"]["since"] == "2026-10-12T09:00:00Z"


def test_report_without_db(telemetry_on, monkeypatch):
    monkeypatch.setattr(telemetry, "_providers", dict)
    props = telemetry.report(NOW)["properties"]
    assert props["db"] == "unreadable"
    assert "sessions" not in props and "agents" not in props
    assert props["lado_errors"] == 0


def test_report_not_due_within_24h(telemetry_on, monkeypatch):
    monkeypatch.setattr(telemetry, "_providers", dict)
    _sent(report_at="2026-10-12T10:00:00Z")
    assert telemetry.report(NOW) is None
    _sent(report_at="2026-10-12T09:00:00Z")
    assert telemetry.report(NOW) is not None


def test_report_window_at_most_30_days(telemetry_on, monkeypatch):
    monkeypatch.setattr(telemetry, "_providers", dict)
    _sent(report_at="2026-08-29T09:00:00Z")
    assert telemetry.report(NOW)["properties"]["since"] == "2026-09-13T09:00:00Z"


def test_report_counts_lado_errors_and_drops(telemetry_on, monkeypatch):
    monkeypatch.setattr(telemetry, "_providers", dict)
    monkeypatch.setattr(telemetry, "OUTBOX_MAX", 1)
    telemetry.record("loop", _raise(KeyError("x")))
    telemetry.record("loop", _raise(KeyError("x")))
    props = telemetry.report()["properties"]
    assert props["lado_errors"] == 2
    assert props["errors_dropped"] == 1


def test_report_names_only_built_in_and_official_kits(telemetry_on, monkeypatch, tmp_path):
    from lado import kits

    monkeypatch.setattr(telemetry, "_providers", dict)
    for name, marketplace in (("sdlc", "official"), ("mine", None), ("theirs", "acme")):
        folder = tmp_path / name
        folder.mkdir()
        (folder / "kit.yaml").write_text(f"name: {name}\nversion: 1.0.0\n")
        state.add_kit(state.InstalledKit(name, None, None, None, str(folder), marketplace))
    props = telemetry.report()["properties"]
    builtin = sorted(found.name for found in kits.builtin_kits())
    assert props["kits"] == {"named": sorted([*builtin, "sdlc"]), "other": 2}


# The batch.


def test_batch_groups_by_fingerprint(telemetry_on, monkeypatch):
    monkeypatch.setattr(telemetry, "_providers", dict)
    for _ in range(3):
        telemetry.record("loop", _raise(KeyError("x")))
    telemetry.record("loop", _raise(ValueError("y")))
    events = telemetry.batch()
    assert [e["event"] for e in events] == [
        telemetry.DAILY,
        telemetry.EXCEPTION,
        telemetry.EXCEPTION,
    ]
    counts = sorted(e["properties"]["count"] for e in events[1:])
    assert counts == [1, 3]


def test_exception_event_shape(telemetry_on, monkeypatch):
    monkeypatch.setattr(telemetry, "_providers", dict)
    _sent(report_at=telemetry.format_time(telemetry.now()))  # no report due
    try:
        state.home().joinpath("no-such-dir", "x").read_text()
    except OSError as exc:
        telemetry.record("cli:ls", exc)
    [event] = telemetry.batch()
    assert event["event"] == "$exception"
    props = event["properties"]
    [entry] = props["$exception_list"]
    assert entry["type"] == "FileNotFoundError"
    assert entry["value"] == "FileNotFoundError in cli:ls"
    assert entry["stacktrace"]["type"] == "raw"
    for frame in entry["stacktrace"]["frames"]:
        assert frame["platform"] == "custom" and frame["lang"] == "python"
        assert frame["in_app"] is True
        assert frame["filename"].startswith("lado/")
    assert props["$exception_fingerprint"] == props["fingerprint"]
    assert props["$process_person_profile"] is False and props["$geoip_disable"] is True
    assert props["count"] == 1 and props["first_at"] == props["last_at"]
    assert "no-such-dir" not in json.dumps(event)


def test_old_outbox_files_are_dropped_and_counted(telemetry_on, monkeypatch):
    monkeypatch.setattr(telemetry, "_providers", dict)
    telemetry.record("loop", _raise(KeyError("x")))
    [path] = (state.home() / "telemetry" / "outbox").iterdir()
    old = time_ns_days_ago(31)
    path.rename(path.with_name(f"{old}-1-abcd.json"))
    telemetry.record("loop", _raise(ValueError("y")))
    events = telemetry.batch()
    assert [e["properties"].get("type") for e in events[1:]] == ["ValueError"]
    assert telemetry.dropped() == 1
    assert len(telemetry.queued()) == 1


def time_ns_days_ago(days):
    import time

    return time.time_ns() - days * 86400 * 10**9


# Sending.


def test_send_posts_and_empties(telemetry_endpoint, monkeypatch):
    monkeypatch.setattr(telemetry, "_providers", dict)
    telemetry.record("loop", _raise(KeyError("x")))
    assert telemetry.send() == 0
    [body] = telemetry_endpoint.requests
    assert body["api_key"] == telemetry.TEST_TOKEN
    assert [e["event"] for e in body["batch"]] == [telemetry.DAILY, telemetry.EXCEPTION]
    assert telemetry.queued() == []
    sent = json.loads((state.home() / "telemetry" / "sent.json").read_text())
    assert sent["sent_at"] and sent["report_at"] and sent["error"] is None
    assert telemetry.last_sent() == (sent["sent_at"], None)


def test_show_is_what_send_posts(telemetry_endpoint, monkeypatch):
    monkeypatch.setattr(telemetry, "_providers", dict)
    telemetry.record("loop", _raise(KeyError("x")))
    monkeypatch.setattr(telemetry, "now", lambda: NOW)  # the same report's times
    shown = telemetry.preview()
    telemetry.send()
    [body] = telemetry_endpoint.requests
    posted = body["batch"]
    assert [shown["report"], *shown["errors"]] == posted


def test_send_failure_keeps_everything(telemetry_endpoint, monkeypatch):
    monkeypatch.setattr(telemetry, "_providers", dict)
    telemetry_endpoint.status = 500
    telemetry.record("loop", _raise(KeyError("x")))
    assert telemetry.send() == 0
    assert len(telemetry_endpoint.requests) == 1
    assert len(telemetry.queued()) == 1
    assert "500" in telemetry.last_sent()[1]
    telemetry_endpoint.status = 200
    assert telemetry.send() == 0  # within RETRY_AFTER: no try
    assert len(telemetry_endpoint.requests) == 1
    monkeypatch.setattr(telemetry, "RETRY_AFTER", 0)
    assert telemetry.send() == 0
    assert len(telemetry_endpoint.requests) == 2
    assert telemetry.queued() == []
    assert telemetry.last_sent()[1] is None


def test_send_removes_only_what_it_sent(telemetry_endpoint, monkeypatch):
    monkeypatch.setattr(telemetry, "_providers", dict)
    telemetry.record("loop", _raise(KeyError("x")))
    post = telemetry._post

    def post_and_record(events, environ=None):
        post(events, environ)
        telemetry.record("loop", _raise(ValueError("during the post")))

    monkeypatch.setattr(telemetry, "_post", post_and_record)
    telemetry.send()
    [left] = telemetry.queued()
    assert left["type"] == "ValueError"


def test_send_subtracts_only_the_drops_it_reported(telemetry_endpoint, monkeypatch):
    monkeypatch.setattr(telemetry, "_providers", dict)
    monkeypatch.setattr(telemetry, "OUTBOX_MAX", 0)
    telemetry.record("loop", _raise(KeyError("x")))
    post = telemetry._post

    def post_and_drop(events, environ=None):
        post(events, environ)
        telemetry.record("loop", _raise(KeyError("x")))

    monkeypatch.setattr(telemetry, "_post", post_and_drop)
    telemetry.send()
    assert telemetry_endpoint.requests[0]["batch"][0]["properties"]["errors_dropped"] == 1
    assert telemetry.dropped() == 1


def test_second_sender_exits(telemetry_endpoint, monkeypatch):
    import fcntl

    telemetry.record("loop", _raise(KeyError("x")))
    lock = open(state.home() / "telemetry" / "send.lock", "a")
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    try:
        assert telemetry.send() == 0
    finally:
        lock.close()
    assert telemetry_endpoint.requests == []
    assert len(telemetry.queued()) == 1


@pytest.mark.parametrize("how", ["off", "env"])
def test_send_off_or_env_off_posts_nothing(telemetry_endpoint, monkeypatch, how):
    telemetry.record("loop", _raise(KeyError("x")))
    if how == "off":
        telemetry.choose("off")
    else:
        monkeypatch.setenv("DO_NOT_TRACK", "1")
    assert telemetry.send() == 0
    assert telemetry_endpoint.requests == []


def _hanging_server():
    import socket
    import threading

    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen()
    accepted = []
    threading.Thread(target=lambda: accepted.append(server.accept()), daemon=True).start()
    return server


@pytest.mark.parametrize("failure", ["refused", "403", "hangs", "dns", "tls"])
def test_unreachable_endpoint_is_silent(telemetry_endpoint, monkeypatch, capsys, failure):
    import socket
    import ssl
    import time

    monkeypatch.setattr(telemetry, "_providers", dict)
    monkeypatch.setattr(telemetry, "SEND_TIMEOUT", 0.3)
    monkeypatch.setattr(telemetry, "SEND_DEADLINE", 1)
    telemetry.record("loop", _raise(KeyError("x")))
    if failure == "refused":
        monkeypatch.setenv("LADO_TELEMETRY_URL", "http://127.0.0.1:1/batch/")
    elif failure == "403":
        telemetry_endpoint.status = 403
    elif failure == "hangs":
        server = _hanging_server()
        port = server.getsockname()[1]
        monkeypatch.setenv("LADO_TELEMETRY_URL", f"http://127.0.0.1:{port}/batch/")
    elif failure == "dns":
        monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: time.sleep(5))
    else:

        def refuse(*args, **kwargs):
            raise ssl.SSLError("certificate verify failed")

        monkeypatch.setattr(telemetry, "_open", refuse)
    began = time.monotonic()
    assert telemetry.send() == 0
    assert time.monotonic() - began < telemetry.SEND_DEADLINE + 1
    assert capsys.readouterr() == ("", "")
    assert len(telemetry.queued()) == 1
    assert telemetry.last_sent()[1]
    import fcntl

    with open(state.home() / "telemetry" / "send.lock", "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)  # released


def test_the_deadline_is_not_swallowed_while_the_report_is_counted(
    telemetry_on, monkeypatch, capsys
):
    """The deadline's signal may come in any step of the build, also where the report
    passes over a failing count (F1): the try still ends there, and never reaches the
    network without its deadline."""
    import socket
    import time

    monkeypatch.setattr(telemetry, "_providers", dict)
    monkeypatch.setattr(telemetry, "SEND_DEADLINE", 1)
    with state.connect():
        pass
    monkeypatch.setattr(state, "usage_counts", lambda since: time.sleep(2))
    looked_up = []
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: looked_up.append(1) or time.sleep(4))
    began = time.monotonic()
    assert telemetry.send() == 0
    assert time.monotonic() - began < 1.5
    assert looked_up == []
    assert "no answer within 1 s" in telemetry.last_sent()[1]
    assert capsys.readouterr() == ("", "")


def test_a_hanging_cli_s_version_is_ended_with_its_share(tmp_path, monkeypatch):
    """The sender's daemon threads end with it, so the --version a thread runs must end
    within PROVIDERS_WAIT by its own timeout: else every try leaves one behind (F5)."""
    import os
    import time

    from lado import providers

    folder = tmp_path / "clis"
    folder.mkdir()
    pid_file = tmp_path / "pid"
    command = providers.get("claude").command
    (folder / command).write_text(f"#!/bin/sh\necho $$ > {pid_file}\nexec sleep 30\n")
    (folder / command).chmod(0o755)
    monkeypatch.setenv("PATH", f"{folder}{os.pathsep}/usr/bin:/bin")
    monkeypatch.setattr(telemetry, "PROVIDERS_WAIT", 2.0)  # the shell starts under load too
    assert telemetry._providers() == {"claude": ""}
    deadline = time.monotonic() + 6  # its timeout kills it at PROVIDERS_WAIT, not at 10 s
    while not pid_file.exists() or not pid_file.read_text().strip():
        assert time.monotonic() < deadline, "the CLI never started"
        time.sleep(0.05)
    pid = int(pid_file.read_text())

    def alive():
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        return True

    while alive() and time.monotonic() < deadline:
        time.sleep(0.05)
    try:
        assert not alive(), "the CLI's --version outlived its share"
    finally:
        if alive():
            os.kill(pid, 9)


def test_slow_agent_clis_take_only_their_share(monkeypatch):
    """A CLI whose --version hangs leaves its version unknown after PROVIDERS_WAIT, and the
    report goes on (F1)."""
    import time

    from lado import doctor, providers

    monkeypatch.setattr(telemetry, "PROVIDERS_WAIT", 0.3)

    def status(provider, which, timeout):
        if provider.name == "codex":
            time.sleep(5)
        return doctor.ProviderStatus(True, "1.2.3", "", "", "")

    monkeypatch.setattr(doctor, "provider_status", status)
    began = time.monotonic()
    found = telemetry._providers()
    assert time.monotonic() - began < 1
    assert found["codex"] == "" and found["claude"] == "1.2.3"
    assert set(found) == set(providers.names())


def test_an_empty_send_keeps_the_last_send_and_its_failure(telemetry_endpoint, monkeypatch):
    """Nothing to post (F4): sent.json keeps when the last send went and why the last try
    failed."""
    monkeypatch.setattr(telemetry, "_providers", dict)
    _sent(
        report_at=telemetry.format_time(telemetry.now()),
        sent_at="2026-10-01T00:00:00Z",
        error="HTTP 403",
    )
    assert telemetry.send() == 0
    assert telemetry_endpoint.requests == []
    assert telemetry.last_sent() == ("2026-10-01T00:00:00Z", "HTTP 403")


def test_long_outage_stays_bounded(telemetry_on, monkeypatch):
    monkeypatch.setattr(telemetry, "_providers", dict)
    monkeypatch.setattr(telemetry, "OUTBOX_MAX", 3)
    monkeypatch.setattr(telemetry, "RETRY_AFTER", 0)
    _sent(report_at="2026-10-01T00:00:00Z")
    for _ in range(10):
        telemetry.record("loop", _raise(KeyError("x")))
    for _ in range(5):
        telemetry.send()  # the endpoint's port is closed
    assert len(telemetry.queued()) == 3
    assert telemetry.dropped() == 7
    reports = [e for e in telemetry.batch() if e["event"] == telemetry.DAILY]
    assert [r["properties"]["since"] for r in reports] == ["2026-10-01T00:00:00Z"]
    assert sorted(p.name for p in (state.home() / "telemetry").iterdir()) == [
        "consent.json",
        "dropped",
        "id",
        "outbox",
        "send.lock",
        "sent.json",
    ]


def test_sender_crash_is_journaled_not_queued(telemetry_endpoint, monkeypatch):
    def broken(now=None):
        raise ZeroDivisionError

    monkeypatch.setattr(telemetry, "_build", broken)
    assert telemetry.send() == 0
    [line] = _journal()
    assert line["where"] == "telemetry:send" and line["type"] == "ZeroDivisionError"
    assert telemetry.queued() == []
    assert telemetry_endpoint.requests == []


# Kicking the sender.


@pytest.fixture
def spawned(monkeypatch):
    import subprocess

    calls = []
    monkeypatch.setattr(subprocess, "Popen", lambda argv, **kw: calls.append((argv, kw)))
    return calls


def test_kick_starts_nothing_when_nothing_due(telemetry_on, spawned):
    _sent(report_at=telemetry.format_time(telemetry.now()))
    telemetry.kick()
    assert spawned == []


def test_kick_starts_nothing_when_off(spawned, monkeypatch):
    telemetry.kick()  # LADO_TELEMETRY=0
    assert spawned == []


def test_kick_spawns_detached_when_due(telemetry_on, spawned):
    telemetry.kick()
    [(argv, kw)] = spawned
    assert argv[-2:] == ["telemetry", "send"]
    assert kw["start_new_session"] is True
    assert kw["stdout"] == kw["stderr"] == kw["stdin"] == -3  # subprocess.DEVNULL


def test_kick_waits_after_a_try(telemetry_on, spawned):
    telemetry.record("loop", _raise(KeyError("x")))
    _sent(
        report_at=telemetry.format_time(telemetry.now()),
        tried_at=telemetry.format_time(telemetry.now()),
    )
    telemetry.kick()
    assert spawned == []


# docs/telemetry.md, the human's list of what is sent.


def test_docs_list_every_field():
    import re
    from pathlib import Path

    docs = Path(__file__).parent.parent / "docs" / "telemetry.md"
    rows = re.findall(r"^\| `([a-z_]+)` \| (\d+) \|", docs.read_text(), re.MULTILINE)
    assert {name: int(since) for name, since in rows} == telemetry.FIELDS
    assert len(rows) == len(telemetry.FIELDS)  # each once
