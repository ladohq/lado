"""The outside folder (LADO_ENV_DIR) for real: its files reach the agents' processes, also
a worker the supervisor's `lado mcp` spawns, and a kit's MCP server; no value reaches
LADO's records."""

import json
from pathlib import Path

import agent_helpers
import pytest

from lado import log, runtime, state

pytestmark = pytest.mark.integration

SESSION = "outside"
VALUE = "canary-v-1-5e0a"


def environ(agent: str) -> dict[str, str]:
    """The environment the fake agent reported at its start."""
    path = agent_helpers.fake_logs(SESSION, agent) / "seen.json"
    return json.loads(path.read_text()).get("environ", {}) if path.exists() else {}


def wait_environ(agent: str) -> dict[str, str]:
    agent_helpers.wait_for(lambda: environ(agent), f"{agent} to report", SESSION)
    return environ(agent)


def wait_status(agent: str, expected: str) -> None:
    agent_helpers.wait_for(
        lambda: (a := state.get_agent(SESSION, agent)) and a.status == expected,
        f"{agent} to be {expected}",
        SESSION,
    )


@pytest.fixture
def folder(tmp_path, monkeypatch):
    """The outside folder, in the environment of LADO's processes (as the image's ENV and
    profile set it): the test's, `lado loop`'s and the agents' `lado mcp`."""
    path = tmp_path / "secrets"
    path.mkdir(mode=0o700)
    monkeypatch.setenv("LADO_ENV_DIR", str(path))
    return path


def test_the_agents_get_the_folders_variables_and_no_record_holds_them(repo, folder, capsys):
    (folder / "OUT_KEY").write_text(VALUE + "\n")
    (folder / "bad-name").write_text(VALUE)
    started = runtime.start_session(str(repo), SESSION, None, "fake")
    assert started.warnings == [f"variable file bad-name in {folder} not used: not a variable name"]
    supervisor = wait_environ("supervisor")
    assert supervisor["OUT_KEY"] == VALUE
    wait_status("supervisor", state.IDLE)

    # A file added while the session runs reaches the worker its supervisor spawns next.
    (folder / "OUT_KEY2").write_text("v-2")
    runtime.send_message(SESSION, "human", "supervisor", "spawn sleep 0")
    worker = wait_environ("worker")
    assert (worker["OUT_KEY"], worker["OUT_KEY2"]) == (VALUE, "v-2")
    assert "OUT_KEY2" not in environ("supervisor")
    wait_status("worker", state.IDLE)

    home = state.home()
    records = [
        home / "lado.db",
        *(home / name for name in ("hooks.log", "loop.log", "errors.jsonl")),
    ]
    records += [p for p in (home / "agents").rglob("*") if p.is_file()]
    assert list((home / "agents").rglob("env.json")) == []
    assert [str(p) for p in records if p.is_file() and VALUE.encode() in p.read_bytes()] == []
    capsys.readouterr()
    log.show(SESSION)
    shown = capsys.readouterr().out
    assert "spawned" in shown and VALUE not in shown
    runtime.stop_session(SESSION)


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def test_a_kits_mcp_server_gets_the_folders_variable(repo, folder):
    kit = repo.parent / "kits" / "outkit"
    write(kit / "kit.yaml", "name: outkit\nversion: 1.0.0\n")
    write(
        kit / "agents" / "reviewer.md",
        "---\nname: reviewer\ndescription: reviews a branch\n"
        "mcp:\n  echo:\n    command: ['${KIT_DIR}/echo.sh']\n    env: {TOKEN: '${OUT_KIT_KEY}'}\n"
        "---\nYou review branches.\n",
    )
    write(kit / "echo.sh", '#!/bin/sh\nprintf %s "$TOKEN" > "$(dirname "$0")/got"\n')
    (kit / "echo.sh").chmod(0o755)
    agent_helpers.install_kit(kit)
    runtime.start_session(str(repo), SESSION, None, "fake", ["default", "outkit"])
    wait_status("supervisor", state.IDLE)
    with pytest.raises(Exception, match="OUT_KIT_KEY"):
        runtime.spawn_worker(SESSION, "sleep 0", role="reviewer")

    (folder / "OUT_KIT_KEY").write_text("k-from-folder\n")
    runtime.spawn_worker(SESSION, "sleep 0", role="reviewer")
    wait_status("reviewer", state.IDLE)
    runtime.send_message(SESSION, "human", "reviewer", "mcp echo")
    agent_helpers.wait_for(lambda: (kit / "got").exists(), "the MCP server's run", SESSION)
    assert (kit / "got").read_text() == "k-from-folder"
    runtime.stop_session(SESSION)
