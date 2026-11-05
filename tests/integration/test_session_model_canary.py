"""The canary of a server's key on its way to an agent: a unique key reaches the fake model
server's agent through its environment, and nothing else: no config, no answer of the API, no
output of `lado start`, no file under LADO_HOME (lado.db, the logs and the error journal included)
but the server's key file, and no agent of a CLI with no model on that server."""

import json
import uuid

import agent_helpers
import pytest
from test_model_server_probe import serve  # noqa: F401 - a fixture
from test_project_secrets_canary import files_holding

from lado import model_settings, runtime, state
from lado.cli import main
from lado.server import models

pytestmark = pytest.mark.integration

SESSION = "itest"


def inputs(agent: str) -> list:
    log = agent_helpers.fake_logs(SESSION, agent) / "inputs.jsonl"
    return log.read_text().splitlines() if log.exists() else []


def idle(agent: str) -> None:
    agent_helpers.wait_for(
        lambda: state.get_agent(SESSION, agent).status == state.IDLE, f"{agent} idle", SESSION
    )


def env_of(agent: str, out) -> str:
    before = len(inputs(agent))
    runtime.send_message(SESSION, "human", agent, f"sh env > {out}")
    agent_helpers.wait_for(lambda: len(inputs(agent)) > before, "its command", SESSION)
    idle(agent)
    return out.read_text()


def tell(command: str) -> None:
    """Have the supervisor run `command`, and wait until its turn is over."""
    before = len(inputs("supervisor"))
    runtime.send_message(SESSION, "human", "supervisor", command)
    agent_helpers.wait_for(lambda: len(inputs("supervisor")) > before, command, SESSION)
    idle("supervisor")


def test_a_key_file_edited_by_hand_stays_out_of_the_agent_and_is_named_nowhere(
    repo,
    serve,  # noqa: F811
    lado_home,
    tmp_path,
    capsys,
):
    """A control character no save lets through: the server's models go, with a warning, as for
    any key that cannot be read, and the agent starts on another server's model."""
    key = f"canary-{uuid.uuid4().hex}"
    model_settings.add_server("Шлюз", serve("all", key=key), key, warn=print, note=print)
    model_settings.add_server("Дом", serve("all"), None, warn=print, note=print)
    gate, home = state.model_server("Шлюз"), state.model_server("Дом")
    state.add_model("Шлюз Qwen", "fake-server", "m1", gate.id)
    saved = state.add_model("Домашняя Qwen", "fake-server", "m1", home.id)
    state.set_cli_default(state.ModelRef("fake-server", saved.id, None))
    edited = f"{key}\tby-hand"
    key_file = model_settings.key_folder(gate.id) / model_settings.KEY
    key_file.write_text(edited)
    capsys.readouterr()

    args = ["start", str(repo), "--name", SESSION, "--provider", "fake-server", "--no-attach"]
    assert main(args) == 0
    said = capsys.readouterr()
    idle("supervisor")

    assert 'the models of model server "Шлюз" are left out' in said.err
    assert key not in said.out + said.err
    env = env_of("supervisor", tmp_path / "supervisor-env")
    assert key not in env
    assert gate.id not in env  # no provider of that server either
    its_log = lado_home / "fake-agents"
    assert files_holding(lado_home, key.encode(), [key_file, its_log]) == []


def test_the_key_is_in_the_agent_s_environment_and_nowhere_else(
    repo,
    serve,  # noqa: F811
    lado_home,
    tmp_path,
    capsys,
):
    key = f"canary-{uuid.uuid4().hex}"
    model_settings.add_server(
        "Шлюз", serve("gateway-limits", key=key), key, warn=lambda _: None, note=lambda _: None
    )
    server = state.model_server("Шлюз")
    saved = state.add_model("Шлюз Qwen", "fake-server", "small", server.id)
    state.set_cli_default(state.ModelRef("fake-server", saved.id, None))

    args = ["start", str(repo), "--name", SESSION, "--provider", "fake-server", "--no-attach"]
    assert main(args) == 0
    said = capsys.readouterr()
    idle("supervisor")
    # The server's limits went with its key: this answer needs it.
    assert "has a context of 16,000 tokens" in said.out + said.err

    variable = f"{model_settings.KEY_VARIABLE}{server.id.upper()}"
    env = env_of("supervisor", tmp_path / "supervisor-env")
    assert f"{variable}={key}" in env

    runtime.send_message(SESSION, "human", "supervisor", "spawnwith w1@fake sleep 0")
    agent_helpers.wait_for(
        lambda: (w := state.get_agent(SESSION, "w1")) is not None and w.seen_at > 0,
        "the worker's first hook",
        SESSION,
    )
    idle("w1")
    assert key not in env_of("w1", tmp_path / "worker-env")

    assert key not in said.out + said.err
    answers = json.dumps(
        [models.agent_info(agent).model_dump() for agent in state.list_agents(SESSION)]
    )
    assert key not in answers
    assert key not in json.dumps(models.session_info(state.get_session(SESSION)).model_dump())
    key_file = model_settings.key_folder(server.id) / model_settings.KEY
    # The fake agent's own log records its environment, where the key belongs: no file of LADO's.
    its_log = lado_home / "fake-agents"
    assert files_holding(lado_home, key.encode(), [key_file, its_log]) == []


def test_a_worker_s_key_stays_in_its_own_environment(
    repo,
    serve,  # noqa: F811
    lado_home,
    tmp_path,
):
    key = f"canary-{uuid.uuid4().hex}"
    url = serve("all", key=key)
    model_settings.add_server("Шлюз", url, key, warn=lambda _: None, note=lambda _: None)
    server = state.model_server("Шлюз")
    state.add_model("Шлюз-Qwen", "fake-server", "m1", server.id)
    runtime.start_session(str(repo), SESSION, None, "fake")
    idle("supervisor")

    tell("listmodels")
    tell("spawnmodel w1@fake-server Шлюз-Qwen sleep")
    agent_helpers.wait_for(
        lambda: (w := state.get_agent(SESSION, "w1")) is not None and w.seen_at > 0,
        "the worker's first hook",
        SESSION,
    )
    idle("w1")

    variable = f"{model_settings.KEY_VARIABLE}{server.id.upper()}"
    assert f"{variable}={key}" in env_of("w1", tmp_path / "worker-env")
    assert key not in env_of("supervisor", tmp_path / "supervisor-env")

    # A refusal with the server gone says nothing of the key either.
    with state.connect() as db:
        db.execute(
            "UPDATE model_servers SET address = 'http://127.0.0.1:9' WHERE id = ?", (server.id,)
        )
    tell("spawnmodel w2@fake-server Шлюз-Qwen sleep")
    results = agent_helpers.fake_logs(SESSION, "supervisor") / "seen.json"
    assert "LADO cannot check m1" in results.read_text()
    assert key not in results.read_text()

    key_file = model_settings.key_folder(server.id) / model_settings.KEY
    # The worker's own log records its environment, where the key belongs: no file of LADO's.
    its_log = lado_home / "fake-agents"
    assert files_holding(lado_home, key.encode(), [key_file, its_log]) == []
