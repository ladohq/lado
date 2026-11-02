"""The session's model (openspec session-model) end to end with the fake agent: from
`lado start --model` to the agent's launch, its hooks, lado.db, list_agents and the UI's
API; a refused model; a worker of another CLI."""

import json

import agent_helpers
import pytest

from lado import runtime, state
from lado.cli import main

pytestmark = pytest.mark.integration

SESSION = "itest"


def wait_for(check, what: str):
    return agent_helpers.wait_for(check, what, SESSION)


def seen(agent: str) -> dict:
    path = agent_helpers.fake_logs(SESSION, agent) / "seen.json"
    return json.loads(path.read_text()) if path.exists() else {}


def inputs(agent: str) -> list[str]:
    log = agent_helpers.fake_logs(SESSION, agent) / "inputs.jsonl"
    return [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []


def runs(agent: str, command: str) -> None:
    """Have `agent` run `command`, and wait until its turn is over."""
    before = len(inputs(agent))
    runtime.send_message(SESSION, "human", agent, command)
    wait_for(lambda: len(inputs(agent)) > before, command)
    wait_for(lambda: state.get_agent(SESSION, agent).status == state.IDLE, f"{agent} idle")


@pytest.fixture
def fake_models(monkeypatch):
    """The fake CLI's own list of models, in the agents' environment."""
    monkeypatch.setenv("FAKE_AGENT_MODELS", "fake-small,fake-large")


def test_the_session_model_reaches_the_agent_lado_db_list_agents_and_the_api(repo, fake_models):
    from lado.server import models

    args = ["start", str(repo), "--name", SESSION, "--provider", "fake", "--no-attach"]
    assert main([*args, "--model", "fake-large"]) == 0
    assert state.get_session(SESSION).power == state.PowerTable.single("fake", "fake-large")
    wait_for(lambda: state.get_agent(SESSION, "supervisor").status == state.IDLE, "idle")
    runs("supervisor", 'sh test "$FAKE_AGENT_MODEL" = fake-large')
    assert seen("supervisor")["sh"]["code"] == 0  # its launch environment has the model
    runs("supervisor", "agents")
    # The fake agent's hooks named the model of its launch environment, the session's.
    listed = {a["name"]: a for a in seen("supervisor")["agents"]}
    assert (listed["supervisor"]["model"], listed["supervisor"]["model_source"]) == (
        "fake-large",
        "session",
    )
    agent = state.get_agent(SESSION, "supervisor")
    assert (agent.model, agent.model_source) == ("fake-large", "session")
    info = models.agent_info(agent)
    assert (info.model.name, info.model.words) == ("fake-large", "chosen for the session")


def test_a_refused_model_starts_nothing(repo, fake_models, capsys):
    args = ["start", str(repo), "--name", SESSION, "--provider", "fake", "--no-attach"]
    assert main([*args, "--model", "nope"]) == 1
    err = capsys.readouterr().err
    assert "nope is not in Fake agent's list of models; FAKE_AGENT_MODELS prints the list" in err
    assert state.get_session(SESSION) is None


def test_a_worker_of_another_cli_runs_its_default_and_says_so(repo, fake_models):
    runtime.start_session(str(repo), SESSION, None, "fake", model="fake-large")
    wait_for(lambda: state.get_agent(SESSION, "supervisor").status == state.IDLE, "idle")
    runs("supervisor", "spawnwith w1@fake-stop sleep 0")
    warning = (
        "w1 runs on Fake agent's default model: the session's model fake-large is for Fake agent"
    )
    assert any(warning in text for text in seen("supervisor")["spawn_text"])
    worker = state.get_agent(SESSION, "w1")
    assert (worker.model, worker.model_source, worker.model_detail) == (
        None,
        "cli",
        "the session's model fake-large is for Fake agent",
    )
