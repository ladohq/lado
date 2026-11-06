"""A small model on a server, end to end with the fake agent, a real model server in its own
process and `lado start`: the start's warning, and a turn that ended on an error."""

import json
import subprocess
import uuid

import agent_helpers
import fake_provider
import pytest
from test_model_server_probe import serve  # noqa: F401 - a fixture
from test_project_secrets_canary import files_holding

from lado import model_settings, runtime, state
from lado.cli import main

pytestmark = pytest.mark.integration

SESSION = "itest"
CLI = "fake-server"


def inputs() -> list:
    log = agent_helpers.fake_logs(SESSION, "supervisor") / "inputs.jsonl"
    return log.read_text().splitlines() if log.exists() else []


def idle() -> None:
    agent_helpers.wait_for(
        lambda: state.get_agent(SESSION, "supervisor").status == state.IDLE, "idle", SESSION
    )


def human_says(text: str) -> state.Message:
    before = len(inputs())
    runtime.write_as_human(SESSION, text)
    sent = state.list_messages(SESSION)[-1]
    agent_helpers.wait_for(lambda: len(inputs()) > before, text, SESSION)
    idle()
    return sent


def reply_state(message: state.Message) -> str | None:
    return state.get_message(SESSION, message.id).reply_state


def start_on(repo, url: str, model: str) -> int:
    model_settings.add_server("Шлюз", url, None, warn=lambda _: None, note=lambda _: None)
    saved = state.add_model("Малая", CLI, model, state.model_server("Шлюз").id)
    state.set_cli_default(state.ModelRef(CLI, saved.id, None))
    return main(["start", str(repo), "--name", SESSION, "--no-attach", "--provider", CLI])


def test_a_start_on_too_small_a_context_warns_and_the_agent_runs(repo, serve, capsys):  # noqa: F811
    assert start_on(repo, serve("gateway-limits"), "small") == 0
    said = capsys.readouterr()
    assert "Малая on Шлюз has a context of 16,000 tokens" in said.out + said.err
    idle()


def test_a_start_on_a_model_of_unknown_context_says_nothing_of_it(repo, serve, capsys):  # noqa: F811
    assert start_on(repo, serve("all"), "m1") == 0
    said = capsys.readouterr()
    assert "context" not in said.out + said.err
    idle()


def test_a_failed_turn_marks_no_message_and_the_next_clean_turn_decides(repo, serve):  # noqa: F811
    assert start_on(repo, serve("all"), "m1") == 0
    idle()
    mine = human_says("fail APIError: the server broke")
    assert reply_state(mine) is None
    human_says("sh true")
    assert reply_state(mine) == state.MISSING


REFUSAL = json.dumps(
    {
        "message": "Engine protocol predict request returned 400: "
        + json.dumps(
            {
                "error": {
                    "code": 400,
                    "message": "request (21556 tokens) exceeds the available context size "
                    "(16384 tokens), try increasing it",
                    "type": "exceed_context_size_error",
                }
            }
        )
    }
)


def test_a_server_s_refusal_for_context_reaches_the_human_in_lado_s_words(
    repo,
    serve,  # noqa: F811
    lado_home,
):
    """The hook of a Kilo agent in its own process, as its plugin runs it: the fake agent's
    provider gives way to Kilo's for the words, and the server's key stays where it belongs."""
    key = f"canary-{uuid.uuid4().hex}"
    model_settings.add_server(
        "Шлюз", serve("all", key=key), key, warn=lambda _: None, note=lambda _: None
    )
    server = state.model_server("Шлюз")
    saved = state.add_model("Малая", CLI, "m1", server.id)
    state.set_cli_default(state.ModelRef(CLI, saved.id, None))
    args = ["start", str(repo), "--name", SESSION, "--no-attach", "--provider", CLI]
    assert main(args) == 0
    idle()
    agent = state.get_agent(SESSION, "supervisor")
    with state.connect() as db:
        db.execute("UPDATE agents SET provider = 'kilo' WHERE session = ?", (SESSION,))

    payload = {"sessionID": "x", "error": {"name": "UnknownError", "message": REFUSAL}}
    hook = ["hook", "session.idle", "--session", SESSION, "--agent", "supervisor"]
    subprocess.run(
        fake_provider.lado_command(*hook, "--instance", agent.instance),
        input=json.dumps(payload),
        text=True,
        check=True,
        timeout=30,
    )

    [told] = [m for m in state.list_messages(SESSION) if m.recipient == state.HUMAN]
    assert told.summary == (
        "turn of supervisor ended on an error: ContextOverflowError: the model's context is too "
        "small for the agent's request; request (21556 tokens) exceeds the available context size "
        "(16384 toke…; it is idle"
    )
    assert told.body == f"UnknownError: {REFUSAL}"
    key_file = model_settings.key_folder(server.id) / model_settings.KEY
    its_log = lado_home / "fake-agents"  # the agent's environment, where the key belongs
    assert files_holding(lado_home, key.encode(), [key_file, its_log]) == []
