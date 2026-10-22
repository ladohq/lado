"""LADO's image (openspec capability container): one `docker run` serves the UI on its
LADO_PORT, `lado doctor` is clean, says `in a container` and finds the four agent CLIs,
Node 22 and npx are on the agents' PATH, a Claude Code agent gets to idle and knows it runs
in a container, and the compose file publishes one port number and runs the image of
LADO_VERSION."""

import json
import os
import urllib.request

import pytest
from container_helpers import IMAGE, ROOT, agent_pid, claude_session, free_port, health

from lado import update

pytestmark = pytest.mark.container


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
    # The four agent CLIs at their pins (an untested version would be a warn, a missing one
    # an info).
    for cli in ("Claude Code", "Codex CLI", "Kilo CLI", "OpenCode"):
        assert any(line.startswith(f"[ok  ] {cli}:") for line in printed), doctor.stdout


def test_node_and_npx_are_on_the_login_shells_path(container):
    shell = container.exec("bash", "-lc", "node --version && npx --version")
    node, npx = shell.stdout.split()
    assert node.startswith("v22."), node
    assert npx[0].isdigit(), npx


def test_a_claude_session_gets_to_idle_and_knows_the_container(container):
    container.sh(
        "git init -q -b main ~/repo && git -C ~/repo -c user.name=lado "
        "-c user.email=lado@example.com commit -q --allow-empty -m first"
    )
    claude_session(container, "/home/lado/repo")

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
    # The workspace at the host's own path, as LADO_REPOS.
    workspace = compose.env["LADO_WORKSPACE"]
    doctor = compose.run("exec", "-T", "lado", "lado", "doctor", check=False).stdout
    assert f"[ok  ] Workspace: {workspace} (LADO_REPOS)" in doctor.splitlines(), doctor
    assert "From another machine" not in link.stderr  # published on loopback only


def test_compose_on_the_network_with_a_name_gives_the_link_for_a_phone(compose):
    """LADO_LISTEN and LADO_PUBLIC_HOST from .env (share-access): stdout stays the one
    local link a launcher reads, the phone's link goes to stderr."""
    compose.env |= {"LADO_LISTEN": "0.0.0.0", "LADO_PUBLIC_HOST": "lado-test.local"}
    compose.run("up", "-d")
    health(compose.port)
    link = compose.run("exec", "-T", "lado", "lado", "ui", "--no-open")
    [local] = link.stdout.splitlines()
    assert local.startswith(f"http://127.0.0.1:{compose.port}/?token="), link.stdout
    token = local.partition("?token=")[2]
    remote = f"From another machine: http://lado-test.local:{compose.port}/?token={token}"
    assert remote in link.stderr.splitlines(), link.stderr
    assert f"listens on 0.0.0.0:{compose.port}, open to other machines" in link.stderr


PLACEHOLDER = "/set-LADO_WORKSPACE-to-your-workspace-folder"


def workspace_of(compose) -> tuple[str, str]:
    """What `docker compose config` makes of the workspace: LADO_REPOS, and the folder of
    the one bind that is neither the secrets' nor the ssh agent's, mounted at its own path
    and never made on the host."""
    config = json.loads(compose.run("config", "--format", "json").stdout)
    lado = config["services"]["lado"]
    binds = [
        (v["source"], v["target"], v.get("bind", {}).get("create_host_path"))
        for v in lado["volumes"]
        if v["type"] == "bind" and v["target"] not in ("/run/secrets", "/run/lado/ssh-agent.sock")
    ]
    assert len(binds) == 1, lado["volumes"]
    [(source, target, create)] = binds
    # A short bind comes out with create_host_path true; a false one may be left out.
    assert source == target and not create, binds
    return lado["environment"]["LADO_REPOS"], source


@pytest.mark.parametrize(
    "env, want",
    [
        ({"LADO_WORKSPACE": "/tmp/lado-new"}, "/tmp/lado-new"),
        ({"LADO_PROJECTS": "/tmp/lado-old"}, "/tmp/lado-old"),  # an installed .env
        ({"LADO_WORKSPACE": "/tmp/lado-new", "LADO_PROJECTS": "/tmp/lado-old"}, "/tmp/lado-new"),
    ],
    ids=["workspace", "projects-still-accepted", "workspace-wins"],
)
def test_compose_takes_the_workspace_from_lado_workspace_else_lado_projects(compose, env, want):
    for name in ("LADO_WORKSPACE", "LADO_PROJECTS"):
        compose.env.pop(name, None)
    compose.env |= env
    assert workspace_of(compose) == (want, want)


def test_compose_without_a_workspace_refuses_at_up_and_names_lado_workspace(compose):
    """No nested `:?` (Compose v2 on GitHub's runners evaluates it even when the outer
    variable is set): `config` passes, `up` refuses at the bind, which is never made."""
    for name in ("LADO_WORKSPACE", "LADO_PROJECTS"):
        compose.env.pop(name, None)
    assert workspace_of(compose) == (PLACEHOLDER, PLACEHOLDER)
    done = compose.run("up", "-d", check=False)
    assert done.returncode != 0, done.stdout
    assert "LADO_WORKSPACE" in done.stderr, done.stderr
    assert not os.path.exists(PLACEHOLDER)


def test_compose_runs_the_image_of_lado_version_and_lado_image_wins(compose):
    del compose.env["LADO_IMAGE"]
    compose.env.pop("LADO_VERSION", None)
    done = compose.run("config", check=False)
    assert done.returncode != 0
    assert "LADO_VERSION" in done.stderr, done.stderr
    compose.env["LADO_VERSION"] = "0.39.0"
    image = compose.run("config", "--images").stdout.split()
    assert image == [f"{update.IMAGE}:0.39.0"]
    compose.env["LADO_IMAGE"] = IMAGE
    assert compose.run("config", "--images").stdout.split() == [IMAGE]
