"""A new image on an old home volume (openspec capabilities container, schema-migration): its
start upgrades lado.db after a backup and says so in `docker logs`, a migration that fails
is one message there and leaves lado.db as it was, and compose.yaml's header steps put the
backup back."""

import os
import subprocess

import pytest
from container_helpers import IMAGE, docker, free_port, health, schema
from test_docker import way_back

from lado import state

pytestmark = pytest.mark.container

BACKUPS = "/home/lado/.lado/backups"


def upgraded(before: int) -> str:
    return (
        f"lado: upgraded lado.db from schema {before} to {state.SCHEMA_VERSION}; its backup is "
        f"{BACKUPS}/lado.db.schema-{before}"
    )


def test_a_new_image_migrates_an_old_home_volume_after_a_backup(start, old_home):
    home, before = old_home()
    port = free_port()
    container = start(port, "-e", f"LADO_PORT={port}", "-p", f"127.0.0.1:{port}:{port}", home=home)
    assert health(port)["ok"] is True
    assert upgraded(before) in container.logs()
    assert container.python("from lado import state; print(state.schema_version())") == str(
        state.SCHEMA_VERSION
    )
    assert container.exec("ls", BACKUPS).stdout.split() == [f"lado.db.schema-{before}"]
    listed = container.exec("lado", "ls").stdout
    assert "old  /home/lado/repo  (stopped)" in listed, listed


def test_a_migration_that_fails_is_one_message_in_docker_logs(start, old_home):
    home, before = old_home(broken=True)
    port = free_port()
    container = start(port, "-e", f"LADO_PORT={port}", home=home)
    exited = docker("wait", container.name, timeout=90).stdout.strip()
    logs = container.logs()
    assert exited == "1", logs
    assert (
        f"lado: could not upgrade lado.db from schema {before} to {state.SCHEMA_VERSION}: "
        "OperationalError: duplicate column name: title. lado.db is unchanged; its backup is "
        f"{BACKUPS}/lado.db.schema-{before}. To go back, run the image you had before: "
        "LADO_IMAGE=<that image> docker compose up -d. Report it with lado bug-report."
    ) in logs, logs
    assert "Traceback" not in logs, logs
    assert schema(home) == before


def test_the_compose_headers_steps_put_the_backup_back(compose, old_home):
    _, before = old_home(volume=f"{compose.project}_home")
    compose.run("up", "-d")
    assert health(compose.port)["ok"] is True
    assert upgraded(before) in compose.run("logs", "lado").stdout
    # The header's commands as a human runs them, the project and its files by compose's
    # own variables; the image under test stands in for the older one.
    env = {
        **compose.env,
        "COMPOSE_FILE": os.pathsep.join(compose.files[1::2]),
        "COMPOSE_PROJECT_NAME": compose.project,
    }
    down, restore, up = (
        step.replace("<older>", IMAGE).replace("<N>", str(before)) for step in way_back()
    )
    for step in (down, restore):
        done = subprocess.run(["sh", "-c", step], env=env, capture_output=True, text=True)
        assert done.returncode == 0, f"{step}\n{done.stdout}{done.stderr}"
    assert schema(f"{compose.project}_home") == before
    done = subprocess.run(["sh", "-c", up], env=env, capture_output=True, text=True)
    assert done.returncode == 0, f"{up}\n{done.stdout}{done.stderr}"
    assert health(compose.port)["ok"] is True  # this image upgrades it again
