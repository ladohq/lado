"""Kits for real: a project kit in the test repo, agents started from it by the fake agent."""

import json
from pathlib import Path

import pytest
from agent_helpers import init_repo, publish
from test_agents import SESSION, wait_for, wait_status

from lado import runtime, sources, state

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
    # Named after their role: the second one gets "-2".
    wait_status("reviewer", state.IDLE)
    wait_status("reviewer-2", state.IDLE)
    first, second = seen("reviewer"), seen("reviewer-2")
    assert first["prompt"].startswith("You review branches.")
    assert f'You are worker "reviewer" in LADO session "{SESSION}"' in first["prompt"]
    assert first["skills"] == {"notes": "take notes"}
    assert first["mcp"]["echo"] == {
        "command": [f"{kit.resolve()}/echo.sh"],
        "env": {"TOKEN": "t0k"},
    }
    assert (second["skills"], list(second["mcp"])) == ({}, ["lado"])

    # A skill's scripts run from where the agent found the skill.
    assert (
        runtime.send_message(SESSION, "human", "reviewer", "run notes scripts/hello.sh") == "sent"
    )
    wait_for(lambda: seen("reviewer").get("run"), "the script's output")
    assert seen("reviewer")["run"] == {
        "file": "notes/scripts/hello.sh",
        "output": "hello from notes",
    }


def test_kit_from_a_path_source_includes_a_skill_pack_from_git(tmp_path, repo):
    pack = init_repo(tmp_path / "pack")
    url = publish(
        pack, {"skills/eng/tdd/SKILL.md": "---\nname: tdd\ndescription: test first\n---\n"}
    )
    sources.add(url)
    dev = tmp_path / "dev"
    write(
        dev / "kits" / "team" / "kit.yaml", "name: team\nversion: 0.1.0\ninclude: [default, pack]\n"
    )
    sources.add(str(dev))

    runtime.start_session(str(repo), SESSION, None, "fake", ["team"])
    wait_status("supervisor", state.IDLE)
    assert seen("supervisor")["skills"] == {"tdd": "test first"}
    runtime.spawn_worker(SESSION, "sleep 0")
    wait_status("worker", state.IDLE)
    assert seen("worker")["skills"] == {"tdd": "test first"}
    # Nothing was copied: the agent's skill links into the source's clone.
    link = state.home() / "agents" / SESSION / "worker" / "skills" / "tdd"
    clone = sources.get("pack").path()
    assert link.is_symlink() and link.resolve() == (clone / "skills" / "eng" / "tdd").resolve()
