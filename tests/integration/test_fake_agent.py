"""The fake agent itself, run directly with hooks that only log: it must behave like a CLI the
tests can rely on, or a failing integration test only times out instead of saying why."""

import json
import subprocess
import sys

import fake_provider
import pytest

pytestmark = pytest.mark.integration


def run_agent(tmp_path, lines: list[str], mcp: dict) -> subprocess.CompletedProcess:
    """Run the fake agent with `lines` as its input and `mcp` as its LADO MCP server; its
    hooks append their event to a file."""
    events = tmp_path / "events"
    (tmp_path / "skills").mkdir()
    config = {
        "hooks": {e: ["sh", "-c", f"echo {e} >> '{events}'"] for e in fake_provider.EVENTS},
        "prompt": "",
        "skills": str(tmp_path / "skills"),
        "mcp": {"lado": mcp},
        "continue_on_turn_end": False,
        "inputs": str(tmp_path / "inputs.jsonl"),
        "seen": str(tmp_path / "seen.json"),
    }
    (tmp_path / "fake.json").write_text(json.dumps(config))
    return subprocess.run(
        [sys.executable, str(fake_provider.AGENT), str(tmp_path / "fake.json")],
        input="".join(f"{line}\n" for line in lines),
        capture_output=True,
        text=True,
        timeout=20,
    )


def test_the_agent_ends_its_process_on_exit(tmp_path, lado_home):
    env = {"LADO_HOME": str(lado_home), "LADO_SESSION": "s", "LADO_AGENT": "a"}
    lado = {"command": fake_provider.lado_command("mcp"), "env": env}
    result = run_agent(tmp_path, ["read", "exit"], lado)  # a tool call: its MCP server is up
    assert result.returncode == 0, result.stderr
    assert json.loads((tmp_path / "seen.json").read_text())["read"] == []  # the call worked
    assert (tmp_path / "events").read_text().split()[-1] == "session_end"


def test_a_tool_call_fails_when_the_mcp_server_cannot_start(tmp_path):
    result = run_agent(
        tmp_path, ["send supervisor hello", "exit"], {"command": ["false"], "env": {}}
    )
    assert result.returncode == 0, result.stderr
    assert "Traceback" in result.stderr
    turn = ["prompt_submit", "turn_end"]  # the failed call ends the turn, as any error does
    assert (tmp_path / "events").read_text().split() == [
        "session_start",
        *turn,
        "prompt_submit",  # exit
        "session_end",
    ]
