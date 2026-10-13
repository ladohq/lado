"""LADO's error journal and its statistics sender across processes: a hook, `lado telemetry
send`, `lado start` with an endpoint that does not answer."""

import json
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
