"""The secrets folder is optional (openspec capability container, change
optional-secrets-folder): compose without it binds /dev/null at /run/secrets, which LADO
takes as no secrets and says nothing about; `LADO_SECRETS=./secrets` in .env enables it, and
compose then refuses to start while the folder is missing rather than make it. Only fake
values."""

import pytest
from container_helpers import Container, agent_environ, claude_session, git_repo, health

pytestmark = pytest.mark.container

FAKE_GH = "fake-gh-89-not-a-token"
NONE_LINE = "[info] Variables from outside: /run/secrets: none"


def test_compose_without_the_folder_starts_and_says_nothing_about_it(compose):
    compose.run("up", "-d")
    assert health(compose.port)["ok"] is True
    doctor = compose.run("exec", "-T", "lado", "lado", "doctor", check=False)
    assert doctor.returncode == 0, doctor.stdout
    lines = doctor.stdout.splitlines()
    assert NONE_LINE in lines, doctor.stdout
    assert "LADO_SECRETS=./secrets" in lines[lines.index(NONE_LINE) + 1]
    container = Container(f"{compose.project}-lado-1", compose.port)
    git_repo(container, "/home/lado/app")
    claude_session(container, "/home/lado/app", "app")  # its supervisor reaches idle
    logs = compose.run("logs", "lado").stdout
    assert "/run/secrets" not in logs and "LADO_ENV_DIR" not in logs, logs


def test_secrets_enabled_by_one_line_reach_an_agent(folder):
    made = folder("one", LADO_SECRETS="./secrets")
    secrets = made.path / "secrets"
    secrets.mkdir(mode=0o700)
    (secrets / "GH_TOKEN").write_text(FAKE_GH + "\n")
    (secrets / "GH_TOKEN").chmod(0o600)
    made.run("up", "-d")
    assert health(made.port)["ok"] is True
    doctor = made.run("exec", "-T", "lado", "lado", "doctor", check=False).stdout
    assert "[ok  ] Variables from outside: /run/secrets: GH_TOKEN" in doctor.splitlines(), doctor
    container = Container(f"{made.project}-lado-1", made.port)
    git_repo(container, "/home/lado/app")
    claude_session(container, "/home/lado/app", "app")
    assert f"GH_TOKEN={FAKE_GH}" in agent_environ(container, "app", "supervisor")


def test_the_folder_named_but_missing_is_refused_and_not_made(folder):
    made = folder("missing", LADO_SECRETS="./secrets")
    done = made.run("up", "-d", check=False)
    assert done.returncode != 0
    assert str(made.path / "secrets") in done.stderr, done.stderr
    assert not (made.path / "secrets").exists()
