"""Kits for real: a project kit in the test repo, agents started from it by the fake agent."""

import json
from pathlib import Path

import pytest
from test_agents import SESSION, wait_for, wait_status

from lado import runtime, state

pytestmark = pytest.mark.integration


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


@pytest.fixture
def kit(repo):
    """A project kit: the default kit plus a reviewer with a skill and an MCP server."""
    kit = repo / ".lado" / "kits" / "itkit"
    write(kit / "kit.yaml", "name: itkit\ninclude: [default]\n")
    write(
        kit / "agents" / "reviewer.md",
        "---\nname: reviewer\ndescription: reviews a branch\nskills: [notes]\n"
        "mcp:\n  echo:\n    command: ['${KIT_DIR}/echo.sh']\n    env: {TOKEN: '${IT_TOKEN}'}\n"
        "---\nYou review branches.\n",
    )
    write(kit / "skills" / "notes" / "SKILL.md", "---\nname: notes\ndescription: take notes\n---\n")
    script = kit / "skills" / "notes" / "scripts" / "hello.sh"
    write(script, "#!/bin/sh\necho hello from notes\n")
    script.chmod(0o755)
    write(kit / "skills" / "plan" / "SKILL.md", "---\nname: plan\ndescription: make a plan\n---\n")
    return kit


def seen(agent: str) -> dict:
    """What the fake agent reported it was given."""
    path = state.home() / "agents" / SESSION / agent / "seen.json"
    return json.loads(path.read_text()) if path.exists() else {}


def test_agents_get_roles_skills_and_mcp_from_kits(repo, kit, monkeypatch):
    runtime.start_session(str(repo), SESSION, None, "fake", ["itkit"])
    wait_status("supervisor", state.IDLE)
    supervisor = seen("supervisor")
    assert supervisor["prompt"].startswith("You are the supervisor.")
    assert f'agent "supervisor" in LADO session "{SESSION}"' in supervisor["prompt"]
    assert "  - reviewer: reviews a branch" in supervisor["prompt"]
    assert supervisor["skills"] == {"notes": "take notes", "plan": "make a plan"}
    assert list(supervisor["mcp"]) == ["lado"]

    monkeypatch.setenv("IT_TOKEN", "t0k")
    runtime.spawn_worker(SESSION, "sleep 0", role="reviewer")
    runtime.spawn_worker(SESSION, "sleep 0", role="reviewer", without=["mcp:echo", "skill:notes"])
    wait_status("w1", state.IDLE)
    wait_status("w2", state.IDLE)
    w1, w2 = seen("w1"), seen("w2")
    assert w1["prompt"].startswith("You review branches.")
    assert f'You are worker "w1" in LADO session "{SESSION}"' in w1["prompt"]
    assert w1["skills"] == {"notes": "take notes"}
    assert w1["mcp"]["echo"] == {"command": [f"{kit.resolve()}/echo.sh"], "env": {"TOKEN": "t0k"}}
    assert (w2["skills"], list(w2["mcp"])) == ({}, ["lado"])

    # A skill's scripts run from where the agent found the skill.
    assert runtime.send_message(SESSION, "human", "w1", "run notes scripts/hello.sh") == "sent"
    wait_for(lambda: seen("w1").get("run"), "the script's output")
    assert seen("w1")["run"] == {"file": "notes/scripts/hello.sh", "output": "hello from notes"}
