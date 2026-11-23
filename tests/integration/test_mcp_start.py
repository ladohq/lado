"""The LADO MCP server's start (lado.mcp_stdio): real servers as an agent's CLI starts them,
a first start, which the SDK answers, then one the cache answers until the SDK is up."""

import json
import os
import subprocess

import pytest

from lado import mcp_stdio, state
from lado.providers import base

pytestmark = pytest.mark.integration

INITIALIZE = {
    "protocolVersion": "2025-06-18",
    "capabilities": {},
    "clientInfo": {"name": "test", "version": "1"},
}


@pytest.fixture
def agents(repo):
    state.add_session(state.Session("s", str(repo), None, provider="claude"))
    for name, role in (("supervisor", "supervisor"), ("w1", "worker")):
        state.add_agent(
            state.Agent("s", name, role, str(repo), None, None, state.IDLE, provider="claude")
        )


def _start(agent: str) -> tuple[list[dict], list[str]]:
    """The answers of the agent's LADO MCP server to a client's start and a tool call, and
    the server's stderr; the server ends with the client's input."""
    server = base.mcp_server(state.get_agent("s", agent))
    process = subprocess.Popen(
        server.command,
        env={**os.environ, **server.env},
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    messages = [
        {"id": 1, "method": "initialize", "params": INITIALIZE},
        {"method": "notifications/initialized"},
        {"id": 2, "method": "tools/list"},
        {"id": 3, "method": "tools/call", "params": {"name": "list_agents", "arguments": {}}},
    ]
    answers = []
    for message in messages:
        process.stdin.write(json.dumps({"jsonrpc": "2.0", **message}) + "\n")
        process.stdin.flush()
        if "id" in message:
            answers.append(json.loads(process.stdout.readline()))
    out, err = process.communicate(timeout=60)
    assert (process.returncode, out) == (0, ""), err  # one answer per request
    return answers, err


def _tools(answers: list[dict]) -> set[str]:
    return {tool["name"] for tool in answers[1]["result"]["tools"]}


def _agents_listed(answers: list[dict]) -> list[str]:
    return [a["name"] for a in answers[2]["result"]["structuredContent"]["result"]]


def test_a_warm_start_answers_as_the_cold_one_did(agents, lado_home):
    cold, _ = _start("supervisor")
    assert len(list((lado_home / "mcp-cache").glob("*.json"))) == 1
    warm, _ = _start("supervisor")
    assert warm[:2] == cold[:2]
    assert warm[0]["result"]["instructions"] == mcp_stdio.instructions("s", "supervisor")
    assert "spawn_worker" in _tools(warm)
    assert _agents_listed(warm) == _agents_listed(cold) == ["supervisor", "w1"]
    instance = state.get_agent("s", "supervisor").instance
    ready = [e for e in state.list_events("s") if e.kind == state.MCP_READY]
    assert [e.detail for e in ready] == [instance, instance]  # once a start


def test_a_worker_after_the_supervisor_gets_a_worker_s_tools(agents, lado_home):
    supervisor, _ = _start("supervisor")
    worker, _ = _start("w1")
    assert worker[0]["result"]["instructions"] == mcp_stdio.instructions("s", "w1")
    assert "spawn_worker" not in _tools(worker)
    assert _tools(supervisor) - _tools(worker) >= {"spawn_worker", "recommend"}
    assert len(list((lado_home / "mcp-cache").glob("*.json"))) == 2
    again, _ = _start("w1")  # from the worker's own entry
    assert again[:2] == worker[:2]
