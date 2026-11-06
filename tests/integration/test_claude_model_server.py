"""A CLI of one model per process on a model server, end to end through `lado mcp` with the fake
agent: each agent has its own model and server, whatever its supervisor runs on, and the
supervisor's key stays out of a worker on another server or a built-in model. "fake-claude" writes
its settings by Claude Code's code."""

import json

import agent_helpers
import pytest
from test_model_server_probe import serve  # noqa: F401 - a fixture

from lado import model_settings, runtime, state
from lado.providers import base

pytestmark = pytest.mark.integration

SESSION = "itest"
CLI = "fake-claude"


def seen(agent: str = "supervisor") -> dict:
    path = agent_helpers.fake_logs(SESSION, agent) / "seen.json"
    return json.loads(path.read_text()) if path.exists() else {}


def inputs(agent: str) -> list:
    log = agent_helpers.fake_logs(SESSION, agent) / "inputs.jsonl"
    return log.read_text().splitlines() if log.exists() else []


def idle(agent: str = "supervisor") -> None:
    agent_helpers.wait_for(
        lambda: state.get_agent(SESSION, agent).status == state.IDLE, f"{agent} idle", SESSION
    )


def runs(command: str) -> None:
    before = len(inputs("supervisor"))
    runtime.send_message(SESSION, "human", "supervisor", command)
    agent_helpers.wait_for(lambda: len(inputs("supervisor")) > before, command, SESSION)
    idle()


def started(worker: str) -> state.Agent:
    agent_helpers.wait_for(
        lambda: (w := state.get_agent(SESSION, worker)) is not None and w.seen_at > 0,
        "the worker's first hook",
        SESSION,
    )
    return state.get_agent(SESSION, worker)


def settings(agent: state.Agent) -> dict:
    return json.loads((base.config_path(agent) / "settings.json").read_text())


def said() -> str:
    return " ".join(text or "" for text in seen()["spawn_text"])


def save(name: str, url: str, key: str | None, model: str) -> state.ConfiguredModel:
    model_settings.add_server(name, url, key, warn=lambda _: None, note=lambda _: None)
    return state.add_model(f"{name}-m", CLI, model, state.model_server(name).id)


@pytest.fixture
def on_server(repo, serve, tmp_path, monkeypatch):  # noqa: F811
    """A session of "fake-claude" on the model of the server `first`, its key `key-first`, not
    logged in; a second server `second` with its own key and model."""
    monkeypatch.setenv("FAKE_AGENT_LOGIN", str(tmp_path / "login"))
    monkeypatch.setenv("FAKE_AGENT_MODELS", "fake-large")
    first = save("first", serve("all", key="key-first"), "key-first", "m1")
    save("second", serve("all", key="key-second"), "key-second", "m1")
    state.set_cli_default(state.ModelRef(CLI, first.id, None))
    runtime.start_session(str(repo), SESSION, None, CLI)
    idle()
    return first


def test_a_session_on_a_server_starts_without_a_login_and_has_the_server(on_server):
    supervisor = state.get_agent(SESSION, "supervisor")
    assert supervisor.model == "m1"
    server = state.model_server("first")
    written = settings(supervisor)
    assert written["env"]["ANTHROPIC_BASE_URL"] == server.address
    assert written["apiKeyHelper"] == f"printenv LADO_MODEL_KEY_{server.id.upper()}"
    assert written["availableModels"] == ["m1"]
    assert seen()["environ"][f"LADO_MODEL_KEY_{server.id.upper()}"] == "key-first"


def test_a_worker_on_another_server_has_that_server_alone(on_server):
    runs("spawnmodel w1@- second-m sleep 0")
    worker = started("w1")
    first, second = state.model_server("first"), state.model_server("second")
    written = settings(worker)
    assert written["env"]["ANTHROPIC_BASE_URL"] == second.address
    assert written["apiKeyHelper"] == f"printenv LADO_MODEL_KEY_{second.id.upper()}"
    env = seen("w1")["environ"]
    assert env[f"LADO_MODEL_KEY_{second.id.upper()}"] == "key-second"
    assert env[base.MODEL_SERVER] == second.id
    assert f"LADO_MODEL_KEY_{first.id.upper()}" not in env


def test_a_worker_on_a_built_in_model_needs_the_login(on_server):
    runs("spawnmodel w1@- fake-large sleep 0")
    assert "not logged in" in said()
    assert state.get_agent(SESSION, "w1") is None


def test_a_worker_on_a_built_in_model_has_nothing_of_a_server(on_server, tmp_path):
    (tmp_path / "login").write_text("logged in")
    runs("spawnmodel w1@- fake-large sleep 0")
    worker = started("w1")
    assert worker.model == "fake-large"
    assert settings(worker) == {}
    env = seen("w1")["environ"]
    assert base.MODEL_SERVER not in env
    assert not [name for name in env if name.startswith(model_settings.KEY_VARIABLE)]


def test_list_models_blocks_no_model_of_the_cli(on_server):
    runs("listmodels")
    [cli] = [one for one in seen()["models"]["clis"] if one["cli"] == CLI]
    assert {one["name"]: one["blocked"] for one in cli["external"]} == {
        "first-m": None,
        "second-m": None,
    }
