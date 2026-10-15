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


def post(url: str) -> tuple[int, dict]:
    request = urllib.request.Request(url, data=b"{}", method="POST")
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
                code, _ = post(f"http://127.0.0.1:{port}/v1/messages")
                break
            except urllib.error.URLError:
                assert time.monotonic() < deadline, "the script never listened"
                time.sleep(0.1)
        assert code == 401
        assert json.loads(log.read_text().splitlines()[0]) == {
            "method": "POST",
            "path": "/v1/messages",
        }
    finally:
        script.terminate()
        script.wait(timeout=10)
