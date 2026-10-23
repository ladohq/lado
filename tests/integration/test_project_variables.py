"""A project's variables for real (openspec change project-variables): every agent of a
session in a project gets its project's values, over the outside folder's, read from
lado.db by whoever launches, also the supervisor's `lado mcp`; a session without a project
gets none; a kit's MCP server gets a key set only in the project through lado.mcp_exec.
The fake agent stands in for an LLM."""

import json

import agent_helpers
import pytest
from agent_helpers import install_kit, wait_for
from test_project_sessions import _approve_and_start, seen, stop_all

from lado import projects, runs, runtime, state

pytestmark = pytest.mark.integration

SHOP_VALUE = "https://a b=c ü"  # a space, = and unicode pass unchanged
TINY = """\
name: tiny
description: a worker does it
start: build
states:
  build: {agent: worker, do: sleep 0, outcomes: {done: end}}
  end: {end: true}
"""


def environ(session: str, agent: str) -> dict[str, str]:
    """The environment the fake agent reported at its start, waited for."""
    path = agent_helpers.fake_logs(session, agent) / "seen.json"

    def found() -> dict:
        return json.loads(path.read_text()).get("environ", {}) if path.exists() else {}

    return wait_for(found, f"{agent} of {session} to report", session)


def wait_idle(session: str, agent: str = "supervisor") -> None:
    wait_for(
        lambda: (a := state.get_agent(session, agent)) and a.status == state.IDLE,
        f"{agent} of {session} idle",
        session,
    )


def tell(session: str, agent: str, command: str) -> None:
    runtime.send_message(session, "human", agent, command)


@pytest.fixture
def two(tmp_path, monkeypatch, git_config):
    """LADO_REPOS=<tmp>/ws, the projects shop and acme with a repository frontend each
    (from scratch), BOARD_URL set in both; the outside folder with BOARD_URL=out and
    OTHER=o; the flow kit itvars with the flow tiny."""
    monkeypatch.setenv("LADO_REPOS", str(tmp_path / "ws"))
    outside = tmp_path / "secrets"
    outside.mkdir(mode=0o700)
    (outside / "BOARD_URL").write_text("out\n")
    (outside / "OTHER").write_text("o")
    monkeypatch.setenv("LADO_ENV_DIR", str(outside))
    for id, value in (("shop", SHOP_VALUE), ("acme", "https://b")):
        projects.create(id, None)
        projects.add_new(id, "frontend")
        projects.set_variable(id, "BOARD_URL", value)
    kit = tmp_path / "kits" / "itvars"
    (kit / "flows").mkdir(parents=True)
    (kit / "kit.yaml").write_text("name: itvars\nversion: 1.0.0\n")
    (kit / "flows" / "tiny.yaml").write_text(TINY)
    install_kit(kit)
    yield
    stop_all()


def test_every_agent_of_a_session_gets_its_project_s_values(two, tmp_path):
    kits = ["default", "itvars"]
    runtime.start_session(None, None, None, "fake", kits, project="shop", repo_name="frontend")
    runtime.start_session(None, None, None, "fake", kits, project="acme", repo_name="frontend")
    plain = agent_helpers.init_repo(tmp_path / "app")
    runtime.start_session(str(plain), "app", None, "fake")
    shop, acme, app = (environ(s, "supervisor") for s in ("shop-frontend", "acme-frontend", "app"))
    assert (shop["BOARD_URL"], shop["OTHER"]) == (SHOP_VALUE, "o")
    assert (acme["BOARD_URL"], acme["OTHER"]) == ("https://b", "o")
    assert (app["BOARD_URL"], app["OTHER"]) == ("out", "o")  # no project: the folder's

    # Set after the supervisor started: its `lado mcp` reads lado.db, not its environment.
    projects.set_variable("shop", "MODEL_URL", "http://m")
    wait_idle("shop-frontend")
    tell("shop-frontend", "supervisor", "spawn sleep 0")
    worker = environ("shop-frontend", "worker")
    assert (worker["BOARD_URL"], worker["MODEL_URL"]) == (SHOP_VALUE, "http://m")
    assert "MODEL_URL" not in environ("shop-frontend", "supervisor")

    # A flow run's worker, spawned by the supervisor too.
    run = runs.start("shop-frontend", "tiny", "build it", notices=[])
    wait_idle("shop-frontend")
    tell("shop-frontend", "supervisor", f"spawnrun {run.name}")
    runner = wait_for(
        lambda: next((a for a in state.list_agents("shop-frontend") if a.run), None),
        "the run's worker",
        "shop-frontend",
    )
    assert environ("shop-frontend", runner.name)["MODEL_URL"] == "http://m"

    # The session its supervisor starts is in the project, and gets its values.
    (projects.folder("shop") / "frontend" / "brief.md").write_text("# Fix the login\n")
    _approve_and_start("shop-frontend", "fix-login")
    assert seen("shop-frontend")["start_session"]["session"] == "fix-login"
    fix = environ("fix-login", "supervisor")
    assert (fix["BOARD_URL"], fix["MODEL_URL"]) == (SHOP_VALUE, "http://m")

    # The other project's agents are untouched.
    wait_idle("acme-frontend")
    tell("acme-frontend", "supervisor", "spawn sleep 0")
    other = environ("acme-frontend", "worker")
    assert other["BOARD_URL"] == "https://b" and "MODEL_URL" not in other


def test_an_unset_reaches_only_the_agents_started_after_it(two):
    runtime.start_session(None, None, None, "fake", project="shop", repo_name="frontend")
    assert environ("shop-frontend", "supervisor")["BOARD_URL"] == SHOP_VALUE
    wait_idle("shop-frontend")
    assert projects.unset_variable("shop", "BOARD_URL") == ["shop-frontend"]
    # Spawned from here: under LADO_AGENT_ENV=inherit the supervisor's `lado mcp` would pass
    # its own environment on (docs/design/agents.md).
    runtime.spawn_worker("shop-frontend", "sleep 0", name="w1")
    assert environ("shop-frontend", "w1")["BOARD_URL"] == "out"
    assert environ("shop-frontend", "supervisor")["BOARD_URL"] == SHOP_VALUE


def test_a_name_lado_sets_keeps_lado_s_value_with_a_warning(two):
    state.set_project_variable("shop", "LADO_SESSION", "other")  # stored past the rule
    started = runtime.start_session(None, None, None, "fake", project="shop", repo_name="frontend")
    assert started.warnings == [
        "project variable LADO_SESSION of shop not used: LADO sets LADO_SESSION for fake"
    ]
    assert environ("shop-frontend", "supervisor")["LADO_SESSION"] == "shop-frontend"


def test_a_kit_key_only_in_the_project_reaches_its_mcp_server(tmp_path, monkeypatch, git_config):
    monkeypatch.setenv("LADO_REPOS", str(tmp_path / "ws"))
    monkeypatch.delenv("BOARD_URL", raising=False)
    projects.create("shop", None)
    projects.add_new("shop", "frontend")
    projects.set_variable("shop", "BOARD_URL", SHOP_VALUE)
    kit = tmp_path / "kits" / "board"
    (kit / "agents").mkdir(parents=True)
    (kit / "kit.yaml").write_text("name: board\nversion: 1.0.0\n")
    (kit / "agents" / "boarder.md").write_text(
        "---\nname: boarder\ndescription: reads the board\n"
        "mcp:\n  echo:\n    command: ['${KIT_DIR}/echo.sh']\n    env: {URL: '${BOARD_URL}'}\n"
        "---\nYou read the board.\n"
    )
    (kit / "echo.sh").write_text('#!/bin/sh\nprintf %s "$URL" > "$(dirname "$0")/got"\n')
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

        plain = agent_helpers.init_repo(tmp_path / "app")
        runtime.start_session(str(plain), "app", None, "fake", kits)
        wait_idle("app")
        with pytest.raises(Exception, match="BOARD_URL"):
            runtime.spawn_worker("app", "sleep 0", role="boarder")
    finally:
        stop_all()
