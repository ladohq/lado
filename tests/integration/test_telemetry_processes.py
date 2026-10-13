"""LADO's error journal and its statistics sender across processes: a hook, `lado telemetry
send`, `lado start` with an endpoint that does not answer."""

import json
import os
import subprocess
import uuid

import agent_helpers
import fake_provider
import pytest

from lado import runtime, state, telemetry

pytestmark = pytest.mark.integration


@pytest.fixture
def session():
    return f"tel-{uuid.uuid4().hex[:8]}"


def _start(repo, session):
    runtime.start_session(str(repo), session, None, "fake")
    agent_helpers.wait_for(
        lambda: state.get_agent(session, "supervisor").status == state.IDLE, "idle", session
    )


def _journal():
    path = telemetry.journal_path()
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


def test_failing_hook_journals_and_queues(repo, session, telemetry_on):
    _start(repo, session)
    instance = state.get_agent(session, "supervisor").instance
    hook = fake_provider.lado_command(
        "hook", "turn_end", "--session", session, "--agent", "supervisor", "--instance", instance
    )
    # A payload the fake provider cannot parse: the hook fails in LADO's own process.
    done = subprocess.run(hook, input="not json", capture_output=True, text=True, timeout=30)
    assert done.returncode == 0
    [line] = [line for line in _journal() if line["where"].startswith("hook:")]
    assert line["where"] == "hook:turn_end"
    assert (line["session"], line["agent"]) == (session, "supervisor")
    [event] = telemetry.queued()
    assert event["where"] == "hook:turn_end" and event["provider"] == "fake"
    text = json.dumps(event)
    assert session not in text and "supervisor" not in text and str(repo) not in text


def _lado(*args, timeout=60):
    return subprocess.run(
        fake_provider.lado_command(*args),
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
        timeout=timeout,
    )


def test_the_sender_posts_to_a_local_endpoint(repo, session, telemetry_endpoint):
    try:
        raise KeyError("x")
    except KeyError as exc:
        telemetry.record("loop", exc)
    # The session's loop kicks a detached sender at its first pass; this one runs too, and
    # whichever comes first posts, once (the lock, then RETRY_AFTER).
    _start(repo, session)
    done = _lado("telemetry", "send")
    assert (done.returncode, done.stdout, done.stderr) == (0, "", "")
    agent_helpers.wait_for(lambda: telemetry_endpoint.requests, "a post", session)
    agent_helpers.wait_for(lambda: telemetry.last_sent()[0], "the send's end", session)
    [body] = telemetry_endpoint.requests
    kinds = [event["event"] for event in body["batch"]]
    assert kinds == [telemetry.DAILY, telemetry.EXCEPTION]
    daily = body["batch"][0]["properties"]
    assert daily["sessions"] == 1 and daily["agents"] == {"fake": 1}
    assert telemetry.queued() == []
    text = json.dumps(body)
    assert session not in text and str(repo) not in text


def test_start_with_an_unreachable_endpoint(repo, session, telemetry_on):
    url = os.environ["LADO_TELEMETRY_URL"]  # a closed local port
    started = _lado("start", str(repo), "--name", session, "--provider", "fake", "--no-attach")
    assert started.returncode == 0, started.stderr
    said = (started.stdout + started.stderr).lower()
    for word in ("statistic", "telemetry", "endpoint", url.split("//")[1].split("/")[0]):
        assert word not in said
    # lado start kicked the detached sender; it gives up silently, kept for status.
    agent_helpers.wait_for(
        lambda: "last try failed:" in _lado("telemetry", "status").stdout,
        "the sender's failure in lado telemetry status",
        session,
        timeout=40,
    )
    assert _lado("telemetry", "send").returncode == 0
    assert _lado("stop", session).returncode == 0
