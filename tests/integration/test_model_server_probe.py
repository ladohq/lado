"""`lado model-server probe` across processes (openspec change model-server-probe): the real
command against the fake model server in a process of its own (tests/fake_model_server.py).
A canary key piped in reaches the server and nothing else: no output, no file under
LADO_HOME, lado.db and the error journal included."""

import os
import socket
import subprocess
import sys
import time
import uuid
from pathlib import Path

import fake_model_server
import fake_provider
import pytest

pytestmark = pytest.mark.integration

SCRIPT = Path(fake_model_server.__file__)


def lado(*args: str, stdin: str | None = None, env: dict | None = None):
    return subprocess.run(
        fake_provider.lado_command(*args),
        input=stdin,
        stdin=None if stdin is not None else subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=60,
        env=env,
    )


@pytest.fixture
def serve(tmp_path):
    """The fake server as a script: its URL; it logs nothing but its own requests."""
    started = []

    def start(profile: str, key: str | None = None) -> str:
        port_file = tmp_path / f"port-{len(started)}"
        argv = [sys.executable, "-I", str(SCRIPT), profile, str(port_file)]
        started.append(subprocess.Popen([*argv, *([key] if key else [])]))
        deadline = time.monotonic() + 10
        while not port_file.exists():
            assert time.monotonic() < deadline, "the fake server never wrote its port"
            time.sleep(0.05)
        return f"http://127.0.0.1:{port_file.read_text()}"

    yield start
    for process in started:
        process.terminate()
        process.wait(timeout=10)


def closed_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_probe_a_fake_server_process(serve):
    url = serve("ollama")
    done = lado("model-server", "probe", url)
    assert (done.returncode, done.stderr) == (0, "")
    assert done.stdout.splitlines() == [
        url,
        "type: Ollama",
        "models: llama3.1:8b, qwen2.5-coder:7b",
        "CLIs: Kilo CLI, OpenCode (chat completions); Codex CLI (Responses API)",
        "not: Claude Code (no Anthropic Messages API)",
    ]


def test_a_gateway_of_both_apis_is_openai_compatible(serve, lado_home):
    """LiteLLM lists in Anthropic's shape when asked with anthropic-version."""
    url = serve("litellm")
    done = lado("model-server", "probe", url)
    assert (done.returncode, done.stderr) == (0, "")
    assert done.stdout.splitlines()[1:3] == [
        "type: OpenAI-compatible",
        f"models: {', '.join(fake_model_server.LITELLM_MODELS)}",
    ]
    assert not any(line.startswith("not:") for line in done.stdout.splitlines())
    assert lado("model-server", "add", "gw", url).returncode == 0
    assert lado("model-server", "list").stdout.splitlines()[1].split()[:3] == [
        "gw",
        url,
        "OpenAI-compatible",
    ]
    assert "gw answers (OpenAI-compatible)" in lado("doctor").stdout


def test_canary_key_is_kept_nowhere(serve, lado_home):
    canary = f"canary-key-{uuid.uuid4().hex}"
    url = serve("openai", key=canary)
    done = lado("model-server", "probe", url, "--key", stdin=canary + "\n")
    assert done.returncode == 0, done.stderr
    assert "type: OpenAI-compatible" in done.stdout  # so the key reached the server
    refused = lado("model-server", "probe", url, "--key", stdin="wrong-" + canary)
    assert refused.stderr == f"lado: {url} refused the key (401)\n"
    for output in (done.stdout, done.stderr, refused.stdout, refused.stderr):
        assert canary not in output
    assert not (lado_home / "lado.db").exists()
    for folder, _, files in os.walk(lado_home):
        for name in files:
            assert canary.encode() not in (Path(folder) / name).read_bytes(), name


def test_closed_port(lado_home):
    port = closed_port()
    done = lado("model-server", "probe", f"127.0.0.1:{port}")
    assert done.returncode == 1
    assert done.stderr == f"lado: http://127.0.0.1:{port} does not answer (connection refused)\n"


def test_container_hint_process():
    port = closed_port()
    env = {**os.environ, "LADO_CONTAINER": "1"}
    done = lado("model-server", "probe", f"localhost:{port}", env=env)
    assert done.returncode == 1
    assert done.stderr.splitlines()[-1] == (
        "lado: LADO runs in a container, where localhost is the container itself; a server on "
        f"your machine: lado model-server probe http://host.docker.internal:{port} (not tried)"
    )
