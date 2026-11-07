"""tests/fake_endpoint.py: the 401 model API of the smoke and container tests, in process and
as a script (the container tests run it inside the image)."""

import json
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import fake_endpoint
import fake_endpoint as endpoints
import pytest

from lado import model_servers
from lado.providers import base

SCRIPT = Path(fake_endpoint.__file__)


def post(url: str, body: dict | None = None) -> tuple[int, dict]:
    request = urllib.request.Request(url, data=json.dumps(body or {}).encode(), method="POST")
    try:
        urllib.request.urlopen(request, timeout=5)
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())
    raise AssertionError("the endpoint answered 2xx")


def test_in_process_it_answers_401_with_each_apis_body_and_keeps_requests():
    endpoint = fake_endpoint.Endpoint()
    try:
        assert post(f"{endpoint.url}/v1/messages") == (401, fake_endpoint.ANTHROPIC_401)
        assert post(f"{endpoint.url}/v1/responses") == (401, fake_endpoint.OPENAI_401)
        assert endpoint.requests == [("POST", "/v1/messages"), ("POST", "/v1/responses")]
        assert endpoint.tools == [[], []]
    finally:
        endpoint.close()


# A request as Codex 0.162 sends one to a newer model: tools at the top and, for the model's
# metadata, in an input item of type additional_tools, some in namespaces.
CODEX_REQUEST = {
    "model": "gpt-5.6-sol",
    "tools": [{"type": "function", "name": "exec_command"}],
    "input": [
        {"type": "message", "role": "user", "content": []},
        {
            "type": "additional_tools",
            "tools": [
                {"type": "namespace", "name": "functions", "tools": [{"name": "exec"}]},
                {"type": "namespace", "name": "collaboration", "tools": [{"name": "wait_agent"}]},
                {"type": "function", "name": "update_plan"},
            ],
        },
    ],
}


def test_it_keeps_the_tool_names_of_each_request():
    endpoint = fake_endpoint.Endpoint()
    try:
        post(f"{endpoint.url}/v1/responses", CODEX_REQUEST)
        request = urllib.request.Request(f"{endpoint.url}/v1/responses", data=b"\x28\xb5")
        try:
            urllib.request.urlopen(request, timeout=5)
        except urllib.error.HTTPError:
            pass
        assert endpoint.tools == [
            ["exec_command", "functions.exec", "collaboration.wait_agent", "update_plan"],
            [],  # a body that is not JSON (a compressed one) has none
        ]
        assert endpoint.models == ["gpt-5.6-sol", ""]
    finally:
        endpoint.close()


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_as_a_script_it_serves_on_its_port_and_logs_each_request(tmp_path):
    port, log = free_port(), tmp_path / "requests.jsonl"
    script = subprocess.Popen([sys.executable, "-I", str(SCRIPT), str(port), str(log)])
    try:
        deadline = time.monotonic() + 10
        while True:
            try:
                code, _ = post(f"http://127.0.0.1:{port}/v1/messages", CODEX_REQUEST)
                break
            except urllib.error.URLError:
                assert time.monotonic() < deadline, "the script never listened"
                time.sleep(0.1)
        assert code == 401
        assert json.loads(log.read_text().splitlines()[0]) == {
            "method": "POST",
            "path": "/v1/messages",
            "tools": ["exec_command", "functions.exec", "collaboration.wait_agent", "update_plan"],
        }
    finally:
        script.terminate()
        script.wait(timeout=10)


# The Responses API.


def _post(server, body, key="k"):
    request = urllib.request.Request(
        f"{server.url}/v1/responses",
        json.dumps(body).encode(),
        {"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    return urllib.request.urlopen(request, timeout=5).read().decode()


def _items(stream):
    events = [json.loads(line[6:]) for line in stream.splitlines() if line.startswith("data: ")]
    assert events[0]["type"] == "response.created"
    assert events[-1]["type"] == "response.completed"
    return [e["item"] for e in events if e["type"] == "response.output_item.done"], events[-1]


@pytest.fixture
def responses(tmp_path):
    server = endpoints.Responses("m1", tmp_path / "ran", "k")
    yield server
    server.close()


def _said(text):
    return {"type": "message", "role": "user", "content": [{"type": "input_text", "text": text}]}


def test_the_probe_sees_the_responses_api_and_the_context(responses):
    found = model_servers.probe(responses.url, "k")
    assert base.RESPONSES in found.apis and found.models == ("m1",)
    limits = model_servers.context_limits(responses.url, "k")
    assert limits["m1"].context == endpoints.CONTEXT


def test_the_script_runs_the_shell_then_lado_s_tool_then_ends(responses):
    tools = [{"type": "namespace", "name": "mcp__lado", "tools": [{"name": "list_agents"}]}]
    first = {"model": "m1", "tools": tools, "input": [_said(endpoints.RUN_TOOLS)]}
    [shell], _ = _items(_post(responses, first))
    assert (shell["name"], shell["call_id"]) == (endpoints.CODEX_SHELL, endpoints.SHELL_CALL)
    assert str(responses.marker) in json.loads(shell["arguments"])["cmd"]
    done = {"type": "function_call_output", "call_id": endpoints.SHELL_CALL, "output": "ok"}
    [mcp], _ = _items(_post(responses, {**first, "input": [done]}))
    assert (mcp["name"], mcp["namespace"]) == ("list_agents", "mcp__lado")
    last = {**done, "call_id": endpoints.MCP_CALL}
    [text], _ = _items(_post(responses, {**first, "input": [last]}))
    assert text["type"] == "message"
    assert responses.tool_results() == [endpoints.SHELL_CALL, endpoints.MCP_CALL]


def test_a_compaction_is_counted_and_usage_reported(responses):
    responses.tokens = 60000
    asks = {"model": "m1", "input": [_said(endpoints.ASKS_A_COMPACTION)]}
    _, completed = _items(_post(responses, asks))
    assert completed["response"]["usage"]["input_tokens"] == 60000
    assert responses.compactions == 1


def test_a_refusal_and_a_wrong_key(responses):
    with pytest.raises(urllib.error.HTTPError) as wrong:
        _post(responses, {"model": "m1"}, key="other")
    assert wrong.value.code == 401
    responses.refusal = (429, {"error": {"message": "slow"}})
    with pytest.raises(urllib.error.HTTPError) as limited:
        _post(responses, {"model": "m1"})
    assert (limited.value.code, limited.value.headers["Retry-After"]) == (429, "1")
