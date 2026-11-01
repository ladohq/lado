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
