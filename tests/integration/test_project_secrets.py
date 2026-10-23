"""A project's secrets for real (openspec change project-secrets): every agent of a session
in a project gets its project's secrets, over the outside folder's, read from their folder
by whoever launches, also the supervisor's `lado mcp`; a session without a project gets
none; a kit's MCP server gets a key set only as a project secret through lado.mcp_exec;
deleting the project removes them. The fake agent stands in for an LLM."""

import os

import agent_helpers
import pytest
from agent_helpers import install_kit, wait_for
from test_project_sessions import _approve_and_start, seen, stop_all
from test_project_variables import TINY, environ, tell, wait_idle

from lado import project_secrets, projects, runs, runtime, state

pytestmark = pytest.mark.integration

# Names no login shell or CI runner sets, so a value seen is the project's.
NAME = "IT_PROJECT_TOKEN"
SHOP_VALUE = "shop-secret a=b ü\nline2"  # a space, =, unicode and a line break pass unchanged


@pytest.fixture
def two(tmp_path, monkeypatch, git_config):
    """LADO_REPOS=<tmp>/ws, the projects shop and acme with a repository frontend each
    (from scratch), the secret NAME in both; the outside folder with NAME=out and OTHER=o;
    the flow kit itsecrets with the flow tiny."""
    monkeypatch.setenv("LADO_REPOS", str(tmp_path / "ws"))
    monkeypatch.delenv(NAME, raising=False)
    outside = tmp_path / "outside"
    outside.mkdir(mode=0o700)
    (outside / NAME).write_text("out\n")
    (outside / "OTHER").write_text("o")
    monkeypatch.setenv("LADO_ENV_DIR", str(outside))
    for id, value in (("shop", SHOP_VALUE), ("acme", "acme-secret")):
        projects.create(id, None)
        projects.add_new(id, "frontend")
        projects.set_secret(id, NAME, value)
    kit = tmp_path / "kits" / "itsecrets"
    (kit / "flows").mkdir(parents=True)
    (kit / "kit.yaml").write_text("name: itsecrets\nversion: 1.0.0\n")
    (kit / "flows" / "tiny.yaml").write_text(TINY)
    install_kit(kit)
    yield
    stop_all()


def test_every_agent_of_a_session_gets_its_project_s_secrets(two, tmp_path):
    kits = ["default", "itsecrets"]
    runtime.start_session(None, None, None, "fake", kits, project="shop", repo_name="frontend")
    runtime.start_session(None, None, None, "fake", kits, project="acme", repo_name="frontend")
    plain = agent_helpers.init_repo(tmp_path / "app")
    runtime.start_session(str(plain), "app", None, "fake")
    shop, acme, app = (environ(s, "supervisor") for s in ("shop-frontend", "acme-frontend", "app"))
    assert (shop[NAME], shop["OTHER"]) == (SHOP_VALUE, "o")
    assert acme[NAME] == "acme-secret"
    assert app[NAME] == "out"  # no project: the outside folder's

    # Set after the supervisor started: its `lado mcp` reads the folder, not its environment.
    projects.set_secret("shop", "IT_MODEL_KEY", "m")
    wait_idle("shop-frontend")
    tell("shop-frontend", "supervisor", "spawn sleep 0")
    worker = environ("shop-frontend", "worker")
    assert (worker[NAME], worker["IT_MODEL_KEY"]) == (SHOP_VALUE, "m")
    assert "IT_MODEL_KEY" not in environ("shop-frontend", "supervisor")

    # A flow run's worker, spawned by the supervisor too.
    run = runs.start("shop-frontend", "tiny", "build it", notices=[])
    wait_idle("shop-frontend")
    tell("shop-frontend", "supervisor", f"spawnrun {run.name}")
    runner = wait_for(
        lambda: next((a for a in state.list_agents("shop-frontend") if a.run), None),
        "the run's worker",
        "shop-frontend",
    )
    assert environ("shop-frontend", runner.name)[NAME] == SHOP_VALUE

    # The session its supervisor starts is in the project, and gets its secrets.
    (projects.folder("shop") / "frontend" / "brief.md").write_text("# Fix the login\n")
    _approve_and_start("shop-frontend", "fix-login")
    assert seen("shop-frontend")["start_session"]["session"] == "fix-login"
    fix = environ("fix-login", "supervisor")
    assert (fix[NAME], fix["IT_MODEL_KEY"]) == (SHOP_VALUE, "m")

    # The other project's agents are untouched.
    wait_idle("acme-frontend")
    tell("acme-frontend", "supervisor", "spawn sleep 0")
    other = environ("acme-frontend", "worker")
    assert other[NAME] == "acme-secret" and "IT_MODEL_KEY" not in other


def test_an_unset_secret_reaches_only_the_agents_started_after_it(two):
    runtime.start_session(None, None, None, "fake", project="shop", repo_name="frontend")
    assert environ("shop-frontend", "supervisor")[NAME] == SHOP_VALUE
    wait_idle("shop-frontend")
    assert projects.unset("shop", NAME) == ["shop-frontend"]
    runtime.spawn_worker("shop-frontend", "sleep 0", name="w1")
    assert environ("shop-frontend", "w1")[NAME] == "out"  # the outside folder's again
    assert environ("shop-frontend", "supervisor")[NAME] == SHOP_VALUE


def test_a_secret_file_not_given_is_named_at_the_start(two):
    os.chmod(project_secrets.folder("shop") / NAME, 0o644)
    started = runtime.start_session(None, None, None, "fake", project="shop", repo_name="frontend")
    assert started.warnings == [
        f"project secret {NAME} of shop not used: readable or writable by others: chmod 600 it"
    ]
    assert environ("shop-frontend", "supervisor")[NAME] == "out"


def test_a_kit_key_only_a_project_secret_reaches_its_mcp_server(tmp_path, monkeypatch, git_config):
    monkeypatch.setenv("LADO_REPOS", str(tmp_path / "ws"))
    monkeypatch.delenv("IT_BOARD_KEY", raising=False)
    projects.create("shop", None)
    projects.add_new("shop", "frontend")
    projects.set_secret("shop", "IT_BOARD_KEY", SHOP_VALUE)
    kit = tmp_path / "kits" / "board"
    (kit / "agents").mkdir(parents=True)
    (kit / "kit.yaml").write_text("name: board\nversion: 1.0.0\n")
    (kit / "agents" / "boarder.md").write_text(
        "---\nname: boarder\ndescription: reads the board\n"
        "mcp:\n  echo:\n    command: ['${KIT_DIR}/echo.sh']\n    env: {KEY: '${IT_BOARD_KEY}'}\n"
        "---\nYou read the board.\n"
    )
    (kit / "echo.sh").write_text('#!/bin/sh\nprintf %s "$KEY" > "$(dirname "$0")/got"\n')
    (kit / "echo.sh").chmod(0o755)
    install_kit(kit)
    kits = ["default", "board"]
    try:
        runtime.start_session(None, None, None, "fake", kits, project="shop", repo_name="frontend")
        wait_idle("shop-frontend")
        runtime.spawn_worker("shop-frontend", "sleep 0", role="boarder")
        wait_idle("shop-frontend", "boarder")
        tell("shop-frontend", "boarder", "mcp echo")
        wait_for(lambda: (kit / "got").exists(), "the MCP server's run", "shop-frontend")
        assert (kit / "got").read_text() == SHOP_VALUE
        configs = state.home_path() / "agents"
        for path in configs.rglob("*"):  # the config holds the name, never the value
            if path.is_file():
                assert b"shop-secret" not in path.read_bytes(), path

        plain = agent_helpers.init_repo(tmp_path / "app")
        runtime.start_session(str(plain), "app", None, "fake", kits)
        wait_idle("app")
        with pytest.raises(Exception, match="IT_BOARD_KEY"):
            runtime.spawn_worker("app", "sleep 0", role="boarder")
    finally:
        stop_all()


def test_deleting_the_project_removes_its_secrets(two):
    runtime.start_session(None, None, None, "fake", project="shop", repo_name="frontend")
    environ("shop-frontend", "supervisor")
    runtime.stop_session("shop-frontend")
    projects.delete("shop", yes=True)
    assert not os.path.lexists(project_secrets.data_folder("shop"))
    assert projects.secrets("acme") == [NAME]
    projects.create("shop", None)
    projects.add_new("shop", "frontend")
    assert projects.secrets("shop") == []
    runtime.start_session(None, "shop-again", None, "fake", project="shop", repo_name="frontend")
    assert environ("shop-again", "supervisor")[NAME] == "out"
