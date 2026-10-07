"""Kits for real: a project kit in the test repo, agents started from it by the fake agent."""

import json
from pathlib import Path

import pytest
from agent_helpers import fake_logs
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
    write(kit / "kit.yaml", "name: itkit\nversion: 1.0.0\n")
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
    # The MCP server: writes the token it got next to itself.
    write(kit / "echo.sh", '#!/bin/sh\nprintf %s "$TOKEN" > "$(dirname "$0")/got"\n')
    (kit / "echo.sh").chmod(0o755)
    return kit


def seen(agent: str) -> dict:
    """What the fake agent reported it was given."""
    path = fake_logs(SESSION, agent) / "seen.json"
    return json.loads(path.read_text()) if path.exists() else {}


def test_agents_get_roles_skills_and_mcp_from_kits(repo, kit, monkeypatch):
    runtime.start_session(str(repo), SESSION, None, "fake", ["default", "itkit"])
    wait_status("supervisor", state.IDLE)
    supervisor = seen("supervisor")
    assert supervisor["prompt"].startswith("You are the supervisor.")
    assert f'agent "supervisor" in LADO session "{SESSION}"' in supervisor["prompt"]
    assert "  - reviewer (kit itkit): reviews a branch" in supervisor["prompt"]
    assert supervisor["skills"] == {"notes": "take notes", "plan": "make a plan"}
    assert list(supervisor["mcp"]) == ["lado"]

    monkeypatch.setenv("IT_TOKEN", "s3cr3t-t0k")
    runtime.spawn_worker(SESSION, "sleep 0", role="reviewer")
    runtime.spawn_worker(SESSION, "sleep 0", role="reviewer", without=["mcp:echo", "skill:notes"])
    # Named after their role: the second one gets "-2".
    wait_status("reviewer", state.IDLE)
    wait_status("reviewer-2", state.IDLE)
    first, second = seen("reviewer"), seen("reviewer-2")
    assert first["prompt"].startswith("You review branches.")
    assert f'You are worker "reviewer" in LADO session "{SESSION}"' in first["prompt"]
    assert first["skills"] == {"notes": "take notes"}
    assert first["mcp"]["echo"]["command"][-2:] == ["--", f"{kit.resolve()}/echo.sh"]
    assert first["mcp"]["echo"]["env"] == {}
    assert (second["skills"], list(second["mcp"])) == ({}, ["lado"])

    # The server gets the token from the agent's environment, through LADO's wrapper.
    runtime.send_message(SESSION, "human", "reviewer", "mcp echo")
    wait_for(lambda: seen("reviewer").get("mcp_run"), "the MCP server's run")
    assert seen("reviewer")["mcp_run"] == {"server": "echo", "code": 0, "stderr": ""}
    assert (kit / "got").read_text() == "s3cr3t-t0k"
    # No file under the agents' config folders holds it; the window's env.json is gone
    # once read.
    root = state.home() / "agents"
    assert list(root.rglob("env.json")) == []
    assert [p for p in root.rglob("*") if p.is_file() and b"s3cr3t" in p.read_bytes()] == []
    wait_status("reviewer", state.IDLE)

    # A skill's scripts run from where the agent found the skill.
    assert (
        runtime.send_message(SESSION, "human", "reviewer", "run notes scripts/hello.sh") == "sent"
    )
    wait_for(lambda: seen("reviewer").get("run"), "the script's output")
    assert seen("reviewer")["run"] == {
        "file": "notes/scripts/hello.sh",
        "output": "hello from notes",
    }

    # Its agents' config folders go with the stop.
    runtime.stop_session(SESSION)
    assert not (root / SESSION).exists()
