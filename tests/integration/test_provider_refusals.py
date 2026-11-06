"""A model provider's refusal, end to end with the fake agent and `lado hook` in its own process,
as a CLI runs it in the agent's environment: each real provider's words, no resume, and the key
a server repeats in no text of LADO's."""

import json
import os
import subprocess
import uuid

import agent_helpers
import fake_provider
import pytest
from test_model_server_probe import serve  # noqa: F401 - a fixture
from test_project_secrets_canary import files_holding

from lado import model_settings, state
from lado.cli import main
from lado.providers import base

pytestmark = pytest.mark.integration

SESSION = "itest"
CLI = "fake-server"


def idle() -> None:
    agent_helpers.wait_for(
        lambda: state.get_agent(SESSION, "supervisor").status == state.IDLE, "idle", SESSION
    )


def refused(repo, url: str, key: str, provider: str, native: str, payload: dict, on_server=True):
    """A session on a server of `key` whose agent is `provider`'s for its hook, which gets
    `payload` as the CLI's `native` event in the agent's environment; the server's id."""
    model_settings.add_server("Шлюз", url, key, warn=lambda _: None, note=lambda _: None)
    server = state.model_server("Шлюз")
    saved = state.add_model("Облако", CLI, "m1", server.id)
    state.set_cli_default(state.ModelRef(CLI, saved.id, None))
    assert main(["start", str(repo), "--name", SESSION, "--no-attach", "--provider", CLI]) == 0
    idle()
    agent = state.get_agent(SESSION, "supervisor")
    with state.connect() as db:
        db.execute("UPDATE agents SET provider = ? WHERE session = ?", (provider, SESSION))
    env = {**os.environ, f"{base.KEY_VARIABLE}{server.id.upper()}": key}
    if on_server:
        env[base.MODEL_SERVER] = server.id
    hook = ["hook", native, "--session", SESSION, "--agent", "supervisor"]
    subprocess.run(
        fake_provider.lado_command(*hook, "--instance", agent.instance),
        input=json.dumps(payload),
        text=True,
        env=env,
        check=True,
        timeout=30,
    )
    return server


def told_human() -> state.Message:
    [told] = [m for m in state.list_messages(SESSION) if m.recipient == state.HUMAN]
    return told


def check_no_key(lado_home, server, key: str, capsys) -> None:
    key_file = model_settings.key_folder(server.id) / model_settings.KEY
    its_log = lado_home / "fake-agents"  # the agent's environment, where the key belongs
    assert files_holding(lado_home, key.encode(), [key_file, its_log]) == []
    assert main(["log", SESSION]) == 0
    said = capsys.readouterr()
    assert key not in said.out + said.err


@pytest.mark.parametrize("provider", ["kilo", "opencode"])
def test_a_refused_key_of_the_family_reads_in_lado_s_words_with_no_key(
    repo,
    serve,  # noqa: F811
    lado_home,
    capsys,
    provider,
):
    key = f"canary-{uuid.uuid4().hex}"
    error = {"name": "APIError", "message": f"Incorrect API key {key}", "status": 401}
    server = refused(
        repo,
        serve("all", key=key),
        key,
        provider,
        "session.idle",
        {"sessionID": "x", "error": error},
    )
    told = told_human()
    assert told.summary == (
        "turn of supervisor ended on an error: the model provider refused the key (401): "
        "Incorrect API key ***; it is idle"
    )
    assert told.body == "Incorrect API key ***"
    check_no_key(lado_home, server, key, capsys)


def test_lado_stats_counts_a_refusal_by_lado_s_words_alone(
    repo,
    serve,  # noqa: F811
    capsys,
):
    key = f"canary-{uuid.uuid4().hex}"
    error = {"name": "APIError", "message": "Slow: down, server-text", "status": 429}
    url = serve("all", key=key)
    refused(repo, url, key, "kilo", "session.idle", {"sessionID": "x", "error": error})
    capsys.readouterr()
    assert main(["stats"]) == 0
    said = capsys.readouterr().out
    assert "(the model provider limits requests, or the quota is spent (429) 1)" in said
    assert "server-text" not in said


def test_a_402_of_claude_code_goes_to_the_human_at_once_with_no_resume(
    repo,
    serve,  # noqa: F811
    lado_home,
    capsys,
):
    """Claude Code's kind says `unknown`, which alone is temporary; the agent on a server has its
    status in its last message, and the hook sees LADO_MODEL_SERVER."""
    key = f"canary-{uuid.uuid4().hex}"
    payload = {
        "error": "unknown",
        "last_assistant_message": f"API Error: 402 Insufficient credits for {key}",
    }
    server = refused(repo, serve("all", key=key), key, "claude", "StopFailure", payload)
    told = told_human()
    assert told.summary == (
        "turn of supervisor ended on an error: the model provider asks for payment (402): "
        "Insufficient credits for ***; it is idle"
    )
    assert told.body == "Insufficient credits for ***"
    agent = state.get_agent(SESSION, "supervisor")
    assert (agent.status, agent.resume_at) == (state.IDLE, None)
    check_no_key(lado_home, server, key, capsys)


def test_a_claude_agent_on_a_built_in_model_keeps_its_temporary_error(
    repo,
    serve,  # noqa: F811
):
    key = f"canary-{uuid.uuid4().hex}"
    payload = {"error": "unknown", "last_assistant_message": "API Error: 402 Insufficient"}
    refused(repo, serve("all", key=key), key, "claude", "StopFailure", payload, on_server=False)
    assert [m for m in state.list_messages(SESSION) if m.recipient == state.HUMAN] == []
    assert state.get_agent(SESSION, "supervisor").resume_at is not None
