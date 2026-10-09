"""The fake agent itself, run directly with hooks that only log: it must behave like a CLI the
tests can rely on, or a failing integration test only times out instead of saying why."""

import json
import os
import subprocess
import sys

import fake_provider
import pytest

pytestmark = pytest.mark.integration


def run_agent(
    tmp_path, lines: list[str], mcp: dict, env: dict | None = None
) -> subprocess.CompletedProcess:
    """Run the fake agent with `lines` as its input and `mcp` as its LADO MCP server; its
    hooks append their event to a file."""
    agent = start_agent(tmp_path, lines, mcp, env)
    stdout, stderr = agent.communicate(timeout=20)
    return subprocess.CompletedProcess(agent.args, agent.returncode, stdout, stderr)


def start_agent(tmp_path, lines: list[str], mcp: dict, env: dict | None = None) -> subprocess.Popen:
    """The fake agent of run_agent, started: all its input is given at once."""
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
    agent = subprocess.Popen(
        [sys.executable, str(fake_provider.AGENT), str(tmp_path / "fake.json")],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )
    agent.stdin.write("".join(f"{line}\n" for line in lines))
    agent.stdin.close()
    agent.stdin = None  # else communicate() flushes the closed file: an error (seen on 3.12.13)
    return agent


def printed(agent: subprocess.Popen, line: str) -> None:
    """Read the agent's output up to `line`; fail if it ends first."""
    for out in agent.stdout:
        if out.rstrip("\n").endswith(line):
            return
    pytest.fail(f"the agent ended without printing {line!r}")


def lado_mcp(lado_home) -> dict:
    env = {"LADO_HOME": str(lado_home), "LADO_SESSION": "s", "LADO_AGENT": "a"}
    return {"command": fake_provider.lado_command("mcp"), "env": env}


def test_the_agent_ends_its_process_on_exit(tmp_path, lado_home):
    result = run_agent(tmp_path, ["read", "exit"], lado_mcp(lado_home))  # its MCP server is up
    assert result.returncode == 0, result.stderr
    assert json.loads((tmp_path / "seen.json").read_text())["read"] == []  # the call worked
    assert (tmp_path / "events").read_text().split()[-1] == "session_end"


def test_a_tool_error_is_printed_and_the_turn_goes_on(tmp_path, lado_home):
    """As an agent CLI shows a tool's error to its model: the turn ends as usual."""
    result = run_agent(tmp_path, ["send nobody hello", "read", "exit"], lado_mcp(lado_home))
    assert result.returncode == 0, result.stderr
    assert "Traceback" not in result.stderr
    [error] = [line for line in result.stdout.splitlines() if line.startswith("send_message: ")]
    assert 'no running agent "nobody"' in error
    assert json.loads((tmp_path / "seen.json").read_text())["read"] == []  # the next call too


def test_a_pause_holds_the_turn_until_the_test_releases_it(tmp_path):
    lines = ["pause", "pause", "exit"]
    agent = start_agent(tmp_path, lines, {"command": ["false"], "env": {}})
    events = tmp_path / "events"
    printed(agent, "paused 1")
    assert (tmp_path / "paused-1").exists() and not (tmp_path / "paused-2").exists()
    (tmp_path / "release-2").touch()  # another pause's release ends none of this one
    assert events.read_text().split() == ["session_start", "prompt_submit"]  # in its turn
    (tmp_path / "release-1").touch()
    printed(agent, "paused 2")  # the next turn's, released already
    agent.communicate(timeout=20)
    turn = ["prompt_submit", "turn_end"]
    assert events.read_text().split() == ["session_start", *turn, *turn, "prompt_submit"] + [
        "session_end"
    ]


def test_the_agent_imports_no_mcp_package(tmp_path, lado_home):
    """Its own small MCP client: the SDK's import alone costs about a third of a second per
    launch. A package `mcp` that cannot be imported is first on its path."""
    poison = tmp_path / "poison" / "mcp"
    poison.mkdir(parents=True)
    (poison / "__init__.py").write_text("raise ImportError('the fake agent imported mcp')\n")
    env = {**os.environ, "PYTHONPATH": str(poison.parent)}
    server = lado_mcp(lado_home)
    server["env"]["PYTHONPATH"] = ""  # the server, which gets the agent's environment, imports it
    result = run_agent(tmp_path, ["read", "exit"], server, env)
    assert result.returncode == 0, result.stderr
    assert json.loads((tmp_path / "seen.json").read_text())["read"] == []


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
