"""A session on a model of a server, end to end with the fake agent, real model servers in their
own processes and `lado start`: which model an agent starts on, every ticked model in its launch,
the check before a start and each resume, LADO's own resume, a default that moves."""

import json

import agent_helpers
import pytest
from test_model_server_probe import serve  # noqa: F401 - a fixture

from lado import model_settings, runtime, state
from lado.cli import main

pytestmark = pytest.mark.integration

SESSION = "itest"
CLI = "fake-server"


def wait_for(check, what: str):
    return agent_helpers.wait_for(check, what, SESSION)


def seen(agent: str) -> dict:
    path = agent_helpers.fake_logs(SESSION, agent) / "seen.json"
    return json.loads(path.read_text()) if path.exists() else {}


def inputs(agent: str) -> list:
    log = agent_helpers.fake_logs(SESSION, agent) / "inputs.jsonl"
    return log.read_text().splitlines() if log.exists() else []


def idle(agent: str = "supervisor") -> None:
    wait_for(lambda: state.get_agent(SESSION, agent).status == state.IDLE, f"{agent} idle")


def runs(agent: str, command: str) -> None:
    before = len(inputs(agent))
    runtime.send_message(SESSION, "human", agent, command)
    wait_for(lambda: len(inputs(agent)) > before, command)
    idle(agent)


def env_of(agent: str, tmp_path) -> dict[str, str]:
    """The agent's environment, as its own shell prints it."""
    out = tmp_path / f"env-{agent}-{len(inputs(agent))}"
    runs(agent, f"sh env -0 > {out}")
    pairs = (item.split("=", 1) for item in out.read_text().split("\0") if item)
    return dict(pairs)


def save(name: str, url: str, key: str | None = None):
    model_settings.add_server(name, url, key, warn=lambda _: None, note=lambda _: None)
    return state.model_server(name)


def tick(name: str, server, model: str = "m1", cli: str = CLI):
    return state.add_model(name, cli, model, server.id)


def default(saved) -> None:
    state.set_cli_default(state.ModelRef(saved.cli, saved.id, None))


def stop() -> None:
    runtime.stop_session(SESSION)


def named(saved) -> str:
    return f"lado-{saved.server}/{saved.model}"


def start(repo, *more: str) -> int:
    args = ["start", str(repo), "--name", SESSION, "--no-attach"]
    return main([*args, "--provider", CLI, *more])


@pytest.mark.parametrize("chosen", ["built-in", "external", "nothing"])
def test_every_ticked_model_is_in_the_agent_whatever_the_session_chose(
    repo,
    serve,  # noqa: F811
    monkeypatch,
    tmp_path,
    chosen,
):
    monkeypatch.setenv("FAKE_AGENT_MODELS", "fake-small")
    one = tick("Локальная Qwen", save("LM Studio дома", serve("all")))
    other = tick("Шлюз Qwen", save("Шлюз", serve("all")))
    given = {"built-in": ["--model", "fake-small"], "external": ["--model", one.name]}
    assert start(repo, *given.get(chosen, [])) == 0
    idle()
    env = env_of("supervisor", tmp_path)
    got = {server["id"]: server for server in json.loads(env["FAKE_AGENT_SERVERS"])}
    assert set(got) == {one.server, other.server}
    assert got[one.server]["models"] == [["m1", "Локальная Qwen"]]
    expected = {"built-in": "fake-small", "external": named(one)}.get(chosen)
    assert env.get("FAKE_AGENT_MODEL") == expected


def test_a_session_starts_on_its_cli_s_default(repo, serve, tmp_path):  # noqa: F811
    saved = tick("Локальная Qwen", save("LM Studio дома", serve("all")))
    default(saved)
    assert start(repo) == 0
    assert state.get_session(SESSION).power is None
    idle()
    assert env_of("supervisor", tmp_path)["FAKE_AGENT_MODEL"] == named(saved)
    agent = state.get_agent(SESSION, "supervisor")
    assert (agent.model, agent.model_source) == (named(saved), "default")
    runs("supervisor", "agents")
    assert seen("supervisor")["agents"][0]["model"] == "Локальная Qwen"


def test_a_default_changed_before_a_resume_reaches_it_and_is_said(
    repo,
    serve,  # noqa: F811
    tmp_path,
    capsys,
):
    server = save("LM Studio дома", serve("all"))
    first = tick("Локальная Qwen", server)
    default(first)
    assert start(repo) == 0
    idle()
    stop()
    second = tick("Шлюз Qwen", save("Шлюз", serve("all")))
    default(second)
    capsys.readouterr()
    assert main(["start", str(repo), "--name", SESSION, "--no-attach"]) == 0
    assert "  changed model: Локальная Qwen -> Шлюз Qwen" in capsys.readouterr().out
    idle()
    assert env_of("supervisor", tmp_path)["FAKE_AGENT_MODEL"] == named(second)


def test_the_cli_s_settings_go_past_a_default_and_stay_at_a_resume(
    repo,
    serve,  # noqa: F811
    tmp_path,
):
    url = serve("all")
    default(tick("Локальная Qwen", save("LM Studio дома", url)))
    assert start(repo, "--model", "") == 0
    idle()
    assert "FAKE_AGENT_MODEL" not in env_of("supervisor", tmp_path)
    stop()
    assert main(["start", str(repo), "--name", SESSION, "--no-attach"]) == 0
    idle()
    assert "FAKE_AGENT_MODEL" not in env_of("supervisor", tmp_path)
    agent = state.get_agent(SESSION, "supervisor")
    assert (agent.model, agent.model_source) == (None, "cli")


def _silence(process) -> None:
    process.terminate()
    process.wait()


@pytest.fixture
def silent_url(tmp_path):
    """The URL of a server saved while it answered, by then gone: a closed port."""
    import socket

    with socket.socket() as free:
        free.bind(("127.0.0.1", 0))
        return f"http://127.0.0.1:{free.getsockname()[1]}"


def _saved_silent(url: str):
    return state.add_model_server("gone", "Молчащий", url, "LM Studio", ["chat completions"])


def test_a_silent_server_refuses_the_start_and_stores_nothing(repo, silent_url, capsys):
    default(tick("Локальная Qwen", _saved_silent(silent_url)))
    assert start(repo) == 1
    err = capsys.readouterr().err
    assert f"{silent_url} does not answer" in err and "LADO cannot check m1" in err
    assert "it is Fake server agent's default model" in err
    assert state.get_session(SESSION) is None


def test_lados_own_resume_leaves_the_session_stopped_with_the_reason(
    repo,
    serve,  # noqa: F811
    silent_url,
):
    saved = tick("Локальная Qwen", save("LM Studio дома", serve("all")))
    assert start(repo, "--model", saved.name) == 0
    idle()
    stop()
    with state.connect() as db:
        db.execute("UPDATE model_servers SET address = ?", (silent_url,))
    state.resume_session(state.get_session(SESSION), "")
    state.stop_for_container()
    lines = []
    runtime.resume_at_start(lines.append)
    assert len(lines) == 1
    assert lines[0].startswith(f'lado: could not resume session "{SESSION}" at the container\'s')
    assert "does not answer" in lines[0] and lines[0].endswith("it stays stopped")
    assert state.get_session(SESSION).stopped_at


def test_a_silent_server_of_another_model_stops_nothing(
    repo,
    serve,  # noqa: F811
    silent_url,
    tmp_path,
):
    default(tick("Локальная Qwen", save("LM Studio дома", serve("all"))))
    other = tick("Молчащая", _saved_silent(silent_url))
    assert start(repo) == 0
    idle()
    got = json.loads(env_of("supervisor", tmp_path)["FAKE_AGENT_SERVERS"])
    assert other.server in [server["id"] for server in got]


def test_a_worker_takes_its_own_cli_s_default(repo, serve, monkeypatch):  # noqa: F811
    monkeypatch.setenv("FAKE_AGENT_MODELS", "fake-small,fake-large")
    saved = tick("Локальная Qwen", save("LM Studio дома", serve("all")))
    default(saved)
    state.set_cli_default(state.ModelRef("fake", None, "fake-large"))
    assert start(repo) == 0
    idle()
    runs("supervisor", "spawnwith w1@fake sleep 0")
    wait_for(lambda: state.get_agent(SESSION, "w1").seen_at > 0, "the worker's first hook")
    worker = state.get_agent(SESSION, "w1")
    assert (worker.model, worker.model_source) == ("fake-large", "default")


def test_a_model_changed_in_the_cli_is_known_by_its_provider_id(repo, serve):  # noqa: F811
    from lado import providers
    from lado.server import models

    server = save("LM Studio дома", serve("all"))
    first = tick("Локальная Qwen", server)
    tick("Рабочая Qwen", server, "m2")
    default(first)
    assert start(repo) == 0
    idle()
    same = providers.get(CLI).same_model
    state.report_model(SESSION, "supervisor", f"lado-{server.id}/m2", None, same)
    info = models.agent_info(state.get_agent(SESSION, "supervisor")).model
    assert (info.configured, info.name, info.server) == ("Рабочая Qwen", "m2", server.name)
    assert info.words == "changed in the agent CLI"
