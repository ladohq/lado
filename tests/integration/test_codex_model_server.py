"""A Codex agent on a model server, end to end with the fake agent: "fake-codex" writes its config
and reads its journal by Codex's own code, and the tests write the journal as Codex does: a start
and a worker on a server, the key in no file, and a failed turn no hook reports."""

import json
import sys
import uuid

import agent_helpers
import pytest
from test_model_server_probe import serve  # noqa: F401 - a fixture
from test_project_secrets_canary import files_holding

from lado import model_settings, runtime, state
from lado.cli import main
from lado.providers import base

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

pytestmark = pytest.mark.integration

SESSION = "itest"
CLI = "fake-codex"
JOURNAL = "sessions/2026/11/07/rollout-2026-11-07T17-16-38-a.jsonl"


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


def config(agent: state.Agent) -> dict:
    return tomllib.loads((base.config_path(agent) / "config.toml").read_text())


def save(name: str, url: str, key: str | None, model: str) -> state.ConfiguredModel:
    model_settings.add_server(name, url, key, warn=lambda _: None, note=lambda _: None)
    return state.add_model(f"{name}-m", CLI, model, state.model_server(name).id)


@pytest.fixture
def on_server(repo, serve, tmp_path, monkeypatch, fakes_known_to_lado):  # noqa: F811
    """A session of "fake-codex" on the model of the server `first`, not logged in, its key a
    canary; a second server `second` with its own key."""
    monkeypatch.setenv("FAKE_AGENT_LOGIN", str(tmp_path / "login"))
    monkeypatch.setenv("FAKE_AGENT_MODELS", "fake-large")
    key = f"canary-{uuid.uuid4().hex}"
    first = save("first", serve("all", key=key), key, "m1")
    save("second", serve("all", key="key-second"), "key-second", "m1")
    state.set_cli_default(state.ModelRef(CLI, first.id, None))
    runtime.start_session(str(repo), SESSION, None, CLI)
    idle()
    return key


def told_human() -> list[state.Message]:
    return [m for m in state.list_messages(SESSION) if m.recipient == state.HUMAN]


def busy() -> int:
    """The supervisor in a turn that only the test ends; the number of its pause."""
    before = sum("pause" in line for line in inputs("supervisor"))
    runtime.send_message(SESSION, "human", "supervisor", "pause")
    number = before + 1
    agent_helpers.wait_for(
        lambda: agent_helpers.paused(SESSION, "supervisor", number), "the pause", SESSION
    )
    agent_helpers.wait_for(
        lambda: state.get_agent(SESSION, "supervisor").status == state.BUSY, "busy", SESSION
    )
    return number


def journal(**error) -> None:
    """Codex's lines of a turn that ended on `error`."""
    agent = state.get_agent(SESSION, "supervisor")
    path = base.config_path(agent) / JOURNAL
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as file:
        for payload in ({"type": "task_started"}, {"type": "task_complete", "error": error}):
            file.write(json.dumps({"type": "event_msg", "payload": payload}) + "\n")


def unauthorized(text: str) -> dict:
    return {
        "message": f"unexpected status 401 Unauthorized: {text}, url: http://gw/v1/responses",
        "codex_error_info": {"http_connection_failed": {"http_status_code": 401}},
    }


def test_a_session_on_a_server_starts_with_no_login_and_the_key_in_its_environment(
    on_server, lado_home
):
    supervisor = state.get_agent(SESSION, "supervisor")
    server = state.model_server("first")
    variable = f"{base.KEY_VARIABLE}{server.id.upper()}"
    written = config(supervisor)
    assert supervisor.model == "m1"
    assert written["model_provider"] == f"lado-{server.id}"
    assert written["model_providers"][f"lado-{server.id}"]["env_key"] == variable
    assert seen()["environ"][variable] == on_server
    key_file = model_settings.key_folder(server.id) / model_settings.KEY
    its_log = lado_home / "fake-agents"  # the agent's environment, where the key belongs
    assert files_holding(lado_home, on_server.encode(), [key_file, its_log]) == []


def test_the_page_names_the_server_the_agent_runs_on(on_server):
    shown = model_settings.agent_shown(state.get_agent(SESSION, "supervisor"))
    assert (shown.name, shown.server) == ("first-m", "first")


def test_a_worker_on_another_server_has_that_server_alone(on_server):
    runs("spawnmodel w1@- second-m sleep 0")
    worker = started("w1")
    first, second = state.model_server("first"), state.model_server("second")
    assert config(worker)["model_provider"] == f"lado-{second.id}"
    env = seen("w1")["environ"]
    assert env[f"{base.KEY_VARIABLE}{second.id.upper()}"] == "key-second"
    assert f"{base.KEY_VARIABLE}{first.id.upper()}" not in env


def test_a_worker_on_a_built_in_model_has_nothing_of_a_server(on_server, tmp_path):
    (tmp_path / "login").write_text("logged in")
    runs("spawnmodel w1@- fake-large sleep 0")
    worker = started("w1")
    assert config(worker) == {}
    env = seen("w1")["environ"]
    assert base.MODEL_SERVER not in env
    assert not [name for name in env if name.startswith(base.KEY_VARIABLE)]


def test_a_refused_key_ends_the_turn_in_lado_s_words_and_no_key(on_server, lado_home, capsys):
    busy()
    journal(**unauthorized(f"Incorrect key {on_server}"))
    idle()
    [told] = told_human()
    assert told.summary == (
        "turn of supervisor ended on an error: the model provider refused the key (401): "
        "Incorrect key ***; it is idle"
    )
    assert told.body == "Incorrect key ***"
    assert state.get_agent(SESSION, "supervisor").resume_at is None
    server = state.model_server("first")
    key_file = model_settings.key_folder(server.id) / model_settings.KEY
    # The agent's environment and Codex's own journal, which LADO does not write.
    skip = [key_file, lado_home / "fake-agents", base.configs_root() / SESSION]
    assert files_holding(lado_home, on_server.encode(), skip) == []
    assert main(["log", SESSION]) == 0
    said = capsys.readouterr()
    assert on_server not in said.out + said.err


def test_a_server_error_plans_a_resume_and_tells_no_one(on_server):
    busy()
    journal(message="high demand", codex_error_info="internal_server_error")
    agent_helpers.wait_for(
        lambda: state.get_agent(SESSION, "supervisor").resume_at is not None, "a resume", SESSION
    )
    assert told_human() == []


def test_an_error_is_told_once_though_another_process_reads_on(on_server):
    """This process is not the loop that told it: what was read is kept on disk, as a restarted
    loop finds it."""
    busy()
    journal(**unauthorized("no"))
    idle()
    assert len(told_human()) == 1
    state.set_status(SESSION, "supervisor", state.BUSY)
    runtime.check_turns(SESSION)
    assert state.get_agent(SESSION, "supervisor").status == state.BUSY
    assert len(told_human()) == 1


def test_a_message_waiting_for_the_turn_is_delivered_after_it(on_server):
    number = busy()
    runtime.send_message(SESSION, "human", "supervisor", "sh true")
    journal(**unauthorized("no"))
    agent_helpers.wait_for(told_human, "the line of the failed turn", SESSION)
    agent_helpers.release(SESSION, "supervisor", number)
    agent_helpers.wait_for(
        lambda: any("sh true" in line for line in inputs("supervisor")), "the message", SESSION
    )
