"""A worker on a model by name (openspec worker-model), end to end through `lado mcp` with the
fake agent: `list_models`, `spawn_worker(model=...)` of the session's CLI, of another and of a
run, what a refusal leaves, a silent server within the probe's timeout."""

import json
import time
from pathlib import Path

import agent_helpers
import pytest
from test_model_server_probe import serve  # noqa: F401 - a fixture

from lado import model_servers, model_settings, runtime, state, tmux

pytestmark = pytest.mark.integration

SESSION = "itest"
SERVER_CLI = "fake-server"
SHIP = """\
name: ship
description: one step for a worker
start: build
states:
  build: {agent: worker, do: Build it., outcomes: {done: end}}
  end: {end: true}
"""


def wait_for(check, what: str):
    return agent_helpers.wait_for(check, what, SESSION)


def seen(agent: str = "supervisor") -> dict:
    path = agent_helpers.fake_logs(SESSION, agent) / "seen.json"
    return json.loads(path.read_text()) if path.exists() else {}


def inputs(agent: str) -> list:
    log = agent_helpers.fake_logs(SESSION, agent) / "inputs.jsonl"
    return log.read_text().splitlines() if log.exists() else []


def idle(agent: str = "supervisor") -> None:
    wait_for(lambda: state.get_agent(SESSION, agent).status == state.IDLE, f"{agent} idle")


def runs(command: str) -> None:
    """Have the supervisor run `command`, and wait until its turn is over."""
    before = len(inputs("supervisor"))
    runtime.send_message(SESSION, "human", "supervisor", command)
    wait_for(lambda: len(inputs("supervisor")) > before, command)
    idle()


def started(worker: str) -> state.Agent:
    wait_for(
        lambda: (w := state.get_agent(SESSION, worker)) is not None and w.seen_at > 0,
        "the worker's first hook",
    )
    return state.get_agent(SESSION, worker)


def said() -> str:
    return " ".join(text or "" for text in seen()["spawn_text"])


def nothing_of(repo, worker: str) -> None:
    assert state.get_agent(SESSION, worker) is None
    assert worker not in tmux.list_windows(SESSION)
    assert runtime.git(str(repo), "branch", "--list", f"lado/{SESSION}/{worker}") == ""
    assert not Path(repo, ".lado", "worktrees", SESSION, worker).exists()


def save(name: str, url: str) -> state.ModelServer:
    model_settings.add_server(name, url, None, warn=lambda _: None, note=lambda _: None)
    return state.model_server(name)


@pytest.fixture
def session(repo, monkeypatch):
    monkeypatch.setenv("FAKE_AGENT_MODELS", "fake-small,fake-large")
    runtime.start_session(str(repo), SESSION, None, "fake", model="fake-small")
    idle()
    return repo


def test_a_worker_starts_on_a_listed_model_and_the_session_stays(session):
    table = state.get_session(SESSION).power
    runs("spawnmodel w1@- fake-large sleep")
    worker = started("w1")
    assert (worker.provider, worker.model, worker.model_source) == (
        "fake",
        "fake-large",
        "supervisor",
    )
    assert state.get_session(SESSION).power == table
    runs("spawn sleep")
    assert started("worker").model == "fake-small"


def test_a_saved_model_moves_the_worker_to_its_cli(session, serve):  # noqa: F811
    saved = state.add_model("Qwen-дома", SERVER_CLI, "m1", save("Дом", serve("all")).id)
    runs("spawnmodel w1@- Qwen-дома sleep")
    worker = started("w1")
    assert (worker.provider, worker.model, worker.model_source) == (
        SERVER_CLI,
        f"lado-{saved.server}/m1",
        "supervisor",
    )


def test_list_models_shows_the_clis_with_the_session_s_first(session, serve):  # noqa: F811
    state.add_model("Qwen-дома", SERVER_CLI, "m1", save("Дом", serve("all")).id)
    runs("listmodels")
    clis = seen()["models"]["clis"]
    assert (clis[0]["cli"], clis[0]["session"], clis[0]["starts_on"]) == ("fake", True, "fake-small")
    assert clis[0]["builtin"] == ["fake-small", "fake-large"]
    [other] = [cli for cli in clis if cli["cli"] == SERVER_CLI]
    assert other["external"] == [{"name": "Qwen-дома", "server": "Дом", "blocked": None}]


def test_a_refused_name_leaves_nothing(session):
    runs("spawnmodel w1@- no-such-model sleep")
    assert "no-such-model is in no agent CLI's list of models; list_models shows them" in said()
    nothing_of(session, "w1")


def test_a_model_of_another_cli_is_refused_for_a_provider(session, serve):  # noqa: F811
    state.add_model("Qwen-дома", SERVER_CLI, "m1", save("Дом", serve("all")).id)
    runs("spawnmodel w1@fake Qwen-дома sleep")
    assert '"Qwen-дома" is a model of Fake server agent, not of Fake agent' in said()
    nothing_of(session, "w1")


def test_a_hanging_server_refuses_within_the_probe_s_timeout(session, serve):  # noqa: F811
    hanging = serve("hang")
    server = state.add_model_server("gone", "Дом", hanging, "LM Studio", ["chat completions"])
    state.add_model("Qwen-дома", SERVER_CLI, "m1", server.id)
    before = time.monotonic()
    runs(f"spawnmodel w1@{SERVER_CLI} Qwen-дома sleep")  # with its provider no other list is read
    assert time.monotonic() - before < model_servers.TIMEOUT + 10  # the agent's turn around it
    assert "LADO cannot check m1" in said()
    nothing_of(session, "w1")


def test_a_run_s_worker_takes_a_model_and_a_refused_one_leaves_the_step(repo, monkeypatch):
    monkeypatch.setenv("FAKE_AGENT_MODELS", "fake-small,fake-large")
    kit = repo.parent / "kits" / "itflow"
    (kit / "flows").mkdir(parents=True)
    (kit / "kit.yaml").write_text("name: itflow\nversion: 1.0.0\n")
    (kit / "flows" / "ship.yaml").write_text(SHIP)
    agent_helpers.install_kit(kit)
    runtime.start_session(str(repo), SESSION, None, "fake", ["default", "itflow"])
    idle()
    runs("flow_start ship add a file")
    name = "ship/add-a-file"
    runs(f"spawnrun {name} no-such-model")
    assert "no-such-model is in no agent CLI's list of models" in said()
    assert state.get_agent(SESSION, "worker") is None
    runs(f"spawnrun {name} fake-large")
    worker = started("worker")
    assert (worker.run, worker.model, worker.model_source) == (name, "fake-large", "supervisor")
