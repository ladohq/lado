"""What the container tests share: the `docker` CLI, the image under test, a free port, the
server's health on the host's loopback, and a container of the image."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).parents[2]
IMAGE = os.environ.get("LADO_TEST_IMAGE", "lado:local")
PYTHON = "/opt/uv/tools/lado/bin/python"  # LADO's own Python in the image
# Every container a test makes: no statistics, no look at PyPI.
QUIET = ["-e", "LADO_TELEMETRY=0", "-e", "LADO_NO_UPDATE_CHECK=1"]
PREFIX = "lado-test-"  # each container, volume and compose project a test makes


def docker(*args: str, check: bool = True, timeout: float = 120, **kw):
    return subprocess.run(
        ["docker", *args], capture_output=True, text=True, check=check, timeout=timeout, **kw
    )


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def health(port: int, timeout: float = 90) -> dict:
    """/api/health on the host's loopback, once the server answers."""
    deadline = time.monotonic() + timeout
    while True:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=5) as r:
                return json.loads(r.read())
        except OSError as e:
            if time.monotonic() > deadline:
                raise AssertionError(f"no /api/health on 127.0.0.1:{port} in {timeout} s") from e
            time.sleep(0.5)


def run_container(name: str, *args: str) -> None:
    """The image as one `docker run` starts it, with a home volume of its own (`<name>-home`)."""
    docker("run", "-d", "--name", name, *QUIET, "-v", f"{name}-home:/home/lado", *args, IMAGE)


def remove_container(name: str) -> None:
    docker("rm", "-f", name, check=False)
    docker("volume", "rm", f"{name}-home", check=False)


class Container:
    """A running container of the image, its UI server on the host's `port`."""

    def __init__(self, name: str, port: int):
        self.name, self.port = name, port

    def exec(self, *cmd: str, check: bool = True, input: str | None = None, timeout=120):
        return docker("exec", "-i", self.name, *cmd, check=check, input=input, timeout=timeout)

    def sh(self, script: str, **kw):
        return self.exec("sh", "-c", script, **kw)

    def python(self, code: str) -> str:
        return self.exec(PYTHON, "-c", code).stdout.strip()

    def write(self, path: str, text: str):
        self.sh(f'mkdir -p "$(dirname {path})" && cat > {path}', input=text)

    def logs(self) -> str:
        done = docker("logs", self.name, check=False)
        return done.stdout + done.stderr
