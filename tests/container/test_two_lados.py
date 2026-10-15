"""Two LADO containers on one machine update independently (openspec capability container):
each a compose project in a folder of its own, with a copy of docker/compose.yaml and an
.env of its own, as compose.yaml's header says. Updating one, a new image reference in its
.env and `docker compose up -d`, leaves the other's container, start and image as they
were."""

import json
import os
import shutil
import subprocess

import pytest
from conftest import QUIET_OVERRIDE, keep
from container_helpers import (
    IMAGE,
    ROOT,
    Container,
    agent_pid,
    claude_session,
    docker,
    free_port,
    git_repo,
    health,
    new_name,
)

pytestmark = pytest.mark.container

# What the human's shell would not set: the folder's .env decides each of them.
FROM_ENV = (
    "COMPOSE_PROJECT_NAME",
    "COMPOSE_FILE",
    "LADO_IMAGE",
    "LADO_VERSION",
    "LADO_PORT",
    "LADO_SECRETS",
)


class Folder:
    """A compose project as a human keeps one: a folder with compose.yaml, the tests' quiet
    settings as compose.override.yaml (compose reads it beside the file) and an .env; each
    command runs there with no -f and no -p."""

    def __init__(self, path, settings: dict):
        self.path, self.settings = path, settings
        self.project, self.port = settings["COMPOSE_PROJECT_NAME"], int(settings["LADO_PORT"])
        path.mkdir()
        shutil.copy(ROOT / "docker" / "compose.yaml", path / "compose.yaml")
        (path / "compose.override.yaml").write_text(QUIET_OVERRIDE)
        (path / "secrets").mkdir(mode=0o700)  # as the header says: compose never makes it
        self.write_env()

    def write_env(self) -> None:
        text = "".join(f"{k}={v}\n" for k, v in self.settings.items())
        (self.path / ".env").write_text(text)

    def run(self, *args: str, check: bool = True) -> subprocess.CompletedProcess:
        env = {k: v for k, v in os.environ.items() if k not in FROM_ENV}
        return docker("compose", *args, check=check, cwd=self.path, env=env, timeout=180)

    def inspect(self) -> dict:
        found = docker("inspect", f"{self.project}-lado-1").stdout
        return json.loads(found)[0]


@pytest.fixture
def folder(request, tmp_path):
    """`folder(name)`: a compose project in `tmp_path/name` on a free port, the image under
    test by a tag of this run's prefix; taken down after the test with its home volume and
    its tags, its container's logs kept when the test fails."""

    def make(name: str) -> Folder:
        project = new_name()
        tag = f"{project}:one"
        docker("tag", IMAGE, tag)
        projects = tmp_path / f"{name}-projects"
        projects.mkdir()
        made = Folder(
            tmp_path / name,
            {
                "COMPOSE_PROJECT_NAME": project,
                "LADO_PORT": str(free_port()),
                "LADO_IMAGE": tag,
                "LADO_VERSION": "test",  # asked for by Compose v2 also beside LADO_IMAGE
                "LADO_PROJECTS": str(projects),
            },
        )
        keep(request.node, Container(f"{project}-lado-1", made.port))

        def down():
            made.run("down", "-v", check=False)
            docker("volume", "rm", "-f", f"{project}_home", check=False)
            for own in (tag, f"{project}:two"):
                docker("image", "rm", own, check=False)  # the tag only: IMAGE keeps it

        request.addfinalizer(down)
        return made

    return make


def test_updating_one_lado_leaves_the_other_as_it_is(folder):
    first, second = folder("first"), folder("second")
    for each in (first, second):
        each.run("up", "-d")
    for each in (first, second):
        assert health(each.port)["ok"] is True
    before = second.inspect()
    # The update of the first: another image reference in its .env (the same image under
    # another tag of this run's prefix stands for a new version), then `up -d`.
    newer = f"{first.project}:two"
    docker("tag", IMAGE, newer)
    first.settings["LADO_IMAGE"] = newer
    first.write_env()
    first.run("up", "-d")
    assert first.inspect()["Config"]["Image"] == newer
    assert health(first.port)["ok"] is True
    after = second.inspect()
    assert (after["Id"], after["State"]["StartedAt"], after["Config"]["Image"]) == (
        before["Id"],
        before["State"]["StartedAt"],
        before["Config"]["Image"],
    )
    assert health(second.port)["ok"] is True


def test_stopping_one_lado_leaves_the_others_sessions(folder):
    first, second = folder("first"), folder("second")
    containers = []
    for each in (first, second):
        each.run("up", "-d")
        health(each.port)
        container = Container(f"{each.project}-lado-1", each.port)
        git_repo(container, "/home/lado/repo")
        claude_session(container, "/home/lado/repo", "app")
        containers.append(container)
    other = containers[1]
    pid = agent_pid(other, "app", "supervisor")
    first.run("down")
    assert (
        other.exec("tmux", "-L", "lado", "has-session", "-t", "=app", check=False).returncode == 0
    )
    assert agent_pid(other, "app", "supervisor") == pid  # the same process
    assert other.agent_status("app", "supervisor") == "idle"
    stopped = other.python(
        "from lado import state; print([s.name for s in state.list_sessions() if s.stopped_at])"
    )
    assert stopped == "[]"
    assert "the container stops" not in other.logs()
