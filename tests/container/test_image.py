"""LADO's image (openspec capability container): one `docker run` serves the UI on its
LADO_PORT, `lado doctor` is clean and says `in a container`, Node 22 and npx are on the
agents' PATH, a Claude Code agent gets to idle and knows it runs in a container, and the
compose file publishes one port number."""

import json
import time
import urllib.request

import pytest
from container_helpers import PYTHON, ROOT, docker, free_port, health

pytestmark = pytest.mark.container

ENDPOINT_PORT = 8399  # the fake model API, on the container's own loopback
KEY = "container-fake-key-0123456789abcdef"  # no account's key: the endpoint takes none


def wheel_version() -> str | None:
    """The version of the one wheel `make docker` built, when the checkout has it."""
    wheels = list((ROOT / "dist").glob("lado-*.whl"))
    return wheels[0].name.split("-")[1] if len(wheels) == 1 else None


def test_docker_run_serves_the_ui_on_its_port(container):
    found = health(container.port)
    assert found["ok"] is True
    installed = container.exec("lado", "--version").stdout.split()[-1]
    assert found["version"] == installed
    if wheel_version():
        assert installed == wheel_version()
    with urllib.request.urlopen(f"http://127.0.0.1:{container.port}/", timeout=10) as page:
        assert b"<html" in page.read().lower()
    logs = container.logs()
    assert "runs in a container" in logs and f"0.0.0.0:{container.port}" in logs, logs
    link = container.exec("lado", "ui", "--no-open").stdout.strip()
    assert link.startswith(f"http://127.0.0.1:{container.port}/?token="), link


def test_without_lado_port_the_server_is_on_8765(start):
    port = free_port()
    start(port, "-p", f"127.0.0.1:{port}:8765")
    assert health(port)["ok"] is True


def test_lado_doctor_is_clean_in_the_container(container):
    doctor = container.exec("lado", "doctor", check=False)
    assert doctor.returncode == 0, doctor.stdout + doctor.stderr
    printed = doctor.stdout.splitlines()
    assert not [line for line in printed if line.startswith("[FAIL]")], doctor.stdout
    [lado] = [line for line in printed if line.startswith("[ok  ] LADO:")]
    assert lado.endswith("in a container")
    # Claude Code at its pin (an untested version would be a warn), the other CLIs absent.
    assert any(line.startswith("[ok  ] Claude Code:") for line in printed), doctor.stdout
    for other in ("Codex CLI", "Kilo CLI", "OpenCode"):
        assert any(line.startswith(f"[info] {other}:") for line in printed), doctor.stdout


def test_node_and_npx_are_on_the_login_shells_path(container):
    shell = container.exec("bash", "-lc", "node --version && npx --version")
    node, npx = shell.stdout.split()
    assert node.startswith("v22."), node
    assert npx[0].isdigit(), npx


def agent_pid(container, session: str, window: str) -> int:
    """The agent CLI's own process: the window's pane process, as lado.agent_env execs the
    CLI in place and Claude Code 2.x is a native binary. Checked, never guessed: its
    executable must be the file the `claude` command names."""
    pane = container.exec(
        "tmux", "-L", "lado", "display-message", "-p", "-t", f"{session}:{window}", "#{pane_pid}"
    ).stdout.strip()
    running = container.exec("readlink", f"/proc/{pane}/exe").stdout.strip()
    claude = container.sh('readlink -f "$(command -v claude)"').stdout.strip()
    assert running == claude, f"pane process {pane} runs {running}, not claude ({claude})"
    return int(pane)


def test_a_claude_session_gets_to_idle_and_knows_the_container(container):
    # The fake model API inside the container, on its own loopback.
    endpoint = str(ROOT / "tests" / "fake_endpoint.py")
    docker("cp", endpoint, f"{container.name}:/tmp/fake_endpoint.py")
    docker(
        "exec", "-d", container.name, PYTHON, "-I", "/tmp/fake_endpoint.py",
        str(ENDPOINT_PORT), "/tmp/endpoint.jsonl",
    )  # fmt: skip
    # Claude Code pointed at it through the login shell, as a human gives a token; its
    # first-run screens, the bypass mode's disclaimer and the repository's trust done.
    container.sh(
        "cat >> ~/.profile <<'EOF'\n"
        f"export ANTHROPIC_BASE_URL=http://127.0.0.1:{ENDPOINT_PORT}\n"
        f"export ANTHROPIC_AUTH_TOKEN={KEY}\n"
        "export CLAUDE_CODE_MAX_RETRIES=0\n"
        "export CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1\n"
        "EOF"
    )
    container.write(
        "/home/lado/.claude/.claude.json",
        json.dumps(
            {
                "hasCompletedOnboarding": True,
                "bypassPermissionsModeAccepted": True,
                "projects": {"/home/lado/repo": {"hasTrustDialogAccepted": True}},
            }
        ),
    )
    container.sh(
        "git init -q -b main ~/repo && git -C ~/repo -c user.name=lado "
        "-c user.email=lado@example.com commit -q --allow-empty -m first"
    )
    started = container.exec(
        "lado", "start", "/home/lado/repo", "--name", "smoke", "--provider", "claude",
        "--permission-mode", "bypassPermissions", "--no-attach", check=False,
    )  # fmt: skip
    assert started.returncode == 0, started.stdout + started.stderr

    status, deadline = "", time.monotonic() + 120
    while time.monotonic() < deadline:
        status = container.python(
            "from lado import state; a = state.get_agent('smoke', 'supervisor'); "
            "print(a.status if a else 'gone')"
        )
        if status == "idle":
            break
        time.sleep(0.5)
    assert status == "idle", f"the supervisor is {status}"

    # The agent's own environment, as its login shell made it (profile.d), not the image's ENV.
    pid = agent_pid(container, "smoke", "supervisor")
    environ = container.exec("cat", f"/proc/{pid}/environ").stdout.split("\0")
    assert "LADO_CONTAINER=1" in environ
    doctor = container.sh(
        f"xargs -0 sh -c 'exec env -i \"$@\" lado doctor' _ < /proc/{pid}/environ", check=False
    )
    [lado] = [line for line in doctor.stdout.splitlines() if "] LADO:" in line]
    assert lado.endswith("in a container"), doctor.stdout + doctor.stderr

    stopped = container.exec("lado", "stop", "--all", check=False)
    assert stopped.returncode == 0, stopped.stdout + stopped.stderr


def test_compose_serves_on_lado_port(compose):
    compose.run("up", "-d")
    assert health(compose.port)["ok"] is True
    link = compose.run("exec", "-T", "lado", "lado", "ui", "--no-open")
    assert link.stdout.strip().startswith(f"http://127.0.0.1:{compose.port}/?token="), link.stdout


def test_compose_refuses_without_the_projects_folder(compose):
    del compose.env["LADO_PROJECTS"]
    done = compose.run("config", check=False)
    assert done.returncode != 0
    assert "LADO_PROJECTS" in done.stderr
