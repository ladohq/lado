"""A message to a busy agent comes with the result of its next LADO tool call, through the
real `lado mcp` of each fake agent, its hooks and tmux (openspec mid-turn-messages)."""

import json

import agent_helpers
import pytest

from lado import runtime, state, tmux

pytestmark = pytest.mark.integration

SESSION = "midturn"


def wait_for(check, what: str):
    return agent_helpers.wait_for(check, what, SESSION)


def inputs(agent: str) -> list[str]:
    log = agent_helpers.fake_logs(SESSION, agent) / "inputs.jsonl"
    return [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []


def seen(agent: str) -> dict:
    path = agent_helpers.fake_logs(SESSION, agent) / "seen.json"
    return json.loads(path.read_text()) if path.exists() else {}


def from_w1() -> list[state.Message]:
    return [m for m in state.list_messages(SESSION) if m.sender == "w1"]


def test_a_workers_report_during_the_supervisors_turn_comes_with_its_next_tool_call(repo):
    runtime.start_session(str(repo), SESSION, None, "fake")
    wait_for(lambda: state.get_agent(SESSION, "supervisor").status == state.IDLE, "idle")
    turn = "pause\nagents\nsend w1 send your report\nread"
    tmux.send_text(SESSION, "supervisor", turn)  # typed by the human
    wait_for(lambda: agent_helpers.paused(SESSION, "supervisor", 1), "the supervisor's turn")
    runtime.spawn_worker(SESSION, "send supervisor DONE: x added | Files: x.py", name="w1")
    wait_for(lambda: [m.state for m in from_w1()] == [state.PENDING], "w1's report queued")
    [report] = from_w1()
    agent_helpers.release(SESSION, "supervisor", 1)
    wait_for(lambda: "read" in seen("supervisor"), "the supervisor's read_messages")
    # list_agents: the agents and the report's line after them.
    looked = seen("supervisor")
    assert [a["name"] for a in looked["agents"]] == ["supervisor", "w1"]
    line = runtime.format_message(report)
    assert looked["agents_text"][-1] == f"{runtime.MID_TURN}\n{line}"
    # The reminder: refused, with nothing queued for w1 beyond its task.
    assert "w1's message" in looked["send_text"][0] and "waits for you" in looked["send_text"][0]
    to_w1 = [m.summary for m in state.list_messages(SESSION) if m.recipient == "w1"]
    assert to_w1 == ["your task"]
    # read_messages: the body, once.
    [read] = looked["read"]
    assert (read["id"], read["body"]) == (report.id, "Files: x.py")
    wait_for(lambda: state.get_agent(SESSION, "supervisor").status == state.IDLE, "turn end")
    [taken] = from_w1()
    assert (taken.state, taken.channel) == (state.READ, state.TOOL_RESULT)
    # The turn's end handed nothing over: no second input with the report's line.
    assert inputs("supervisor") == [turn]
    runtime.stop_session(SESSION)
