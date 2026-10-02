import asyncio
import json

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from lado import mcp_server, runtime, state


def _tools(session, agent):
    tools = asyncio.run(mcp_server.build(session, agent).list_tools())
    return sorted(t.name for t in tools)


def test_only_supervisor_can_spawn_workers(repo, fake_tmux):
    runtime.start_session(str(repo), "s", None)
    runtime.spawn_worker("s", "task")
    supervisor_tools = [
        "finish_worker",
        "flow_advance",
        "flow_cancel",
        "flow_start",
        "flow_status",
        "list_agents",
        "read_messages",
        "send_message",
        "spawn_worker",
    ]
    assert _tools("s", "supervisor") == supervisor_tools
    assert _tools("s", "w1") == [
        "flow_advance",
        "flow_status",
        "list_agents",
        "read_messages",
        "send_message",
    ]


def test_listing_the_tools_records_that_the_server_is_ready(repo, fake_tmux):
    """The agent's session-start hook waits for this (lado.hooks)."""
    runtime.start_session(str(repo), "s", None)
    asyncio.run(mcp_server.build("s", "supervisor", instance="abc").list_tools())
    ready = [(e.agent, e.detail) for e in state.list_events("s") if e.kind == state.MCP_READY]
    assert ready == [("supervisor", "abc")]


def test_list_agents_says_since_when_and_how_long_each_has_its_status(repo, fake_tmux):
    runtime.start_session(str(repo), "s", None)
    runtime.spawn_worker("s", "task")
    with state.connect() as db:
        db.execute(
            "UPDATE events SET created_at = strftime('%Y-%m-%d %H:%M:%f', 'now', '-90 seconds')"
            " WHERE agent = 'w1'"
        )
        db.execute("DELETE FROM events WHERE agent = 'supervisor'")
    result = asyncio.run(mcp_server.build("s", "w1").call_tool("list_agents", {}))
    supervisor, worker = result.structured_content["result"]
    assert (supervisor["status_since"], supervisor["status_for_seconds"]) == (None, None)
    assert worker["status_since"] == state.status_since("s")["w1"].isoformat()
    assert 90 <= worker["status_for_seconds"] < 100


def test_a_report_is_a_summary_and_a_body_read_once(repo, fake_tmux):
    runtime.start_session(str(repo), "s", None)
    runtime.spawn_worker("s", "task")
    worker = mcp_server.build("s", "w1")
    report = {"to": "supervisor", "summary": "DONE: x added", "body": "Files: x.py\nChecks: ok"}
    asyncio.run(worker.call_tool("send_message", report))
    state.take_pending("s", "supervisor", state.DELIVERED)
    supervisor = mcp_server.build("s", "supervisor")
    result = asyncio.run(supervisor.call_tool("read_messages", {}))
    [message] = result.structured_content["result"]
    assert message.pop("time")
    assert message == {
        "id": 1,
        "from": "w1",
        "summary": "DONE: x added",
        "body": "Files: x.py\nChecks: ok",
    }
    again = asyncio.run(supervisor.call_tool("read_messages", {}))
    assert again.structured_content == {"result": []}


def test_finish_worker_reports_what_it_removed(repo, fake_tmux):
    runtime.start_session(str(repo), "s", None)
    worker = runtime.spawn_worker("s", "task")
    server = mcp_server.build("s", "supervisor")
    result = asyncio.run(server.call_tool("finish_worker", {"name": "w1", "discard": True}))
    assert json.loads(result.content[0].text) == {
        "name": "w1",
        "finished": "discarded",
        "removed": {"window": "w1", "worktree": worker.cwd, "branch": "lado/s/w1"},
        "dropped_messages": 0,
    }
    assert state.get_agent("s", "w1") is None


@pytest.mark.parametrize(
    ("tool", "args", "reason"),
    [
        ("finish_worker", {"name": "supervisor"}, "end the whole session with `lado stop s`"),
        ("send_message", {"to": "nobody", "summary": "hi"}, 'no running agent "nobody"'),
        ("send_message", {"to": "w1", "summary": "a\nb"}, "summary must be one line"),
        ("spawn_worker", {"task": "t", "role": "boss"}, 'no worker role "boss"'),
    ],
)
def test_tool_errors_tell_the_agent_why(repo, fake_tmux, tool, args, reason):
    runtime.start_session(str(repo), "s", None)
    server = mcp_server.build("s", "supervisor")
    with pytest.raises(ToolError) as error:
        asyncio.run(server.call_tool(tool, args))
    assert reason in str(error.value)


def test_spawn_worker_refuses_a_provider_without_the_sessions_mode(repo, fake_tmux):
    runtime.start_session(str(repo), "s", "dontAsk")
    server = mcp_server.build("s", "supervisor")
    with pytest.raises(ToolError) as error:
        asyncio.run(server.call_tool("spawn_worker", {"task": "t", "provider": "kilo"}))
    assert '"dontAsk" is not supported by Kilo CLI (kilo)' in str(error.value)


ACCEPTED = {
    "list_agents": "none",
    "flow_advance": "run, outcome, note_summary, note_body",
    "flow_status": "run",
    "send_message": "to, summary, body",
    "read_messages": "none",
    "spawn_worker": "task, name, provider, role, without, run",
    "flow_start": "flow, task, name, human_language",
    "flow_cancel": "run, reason",
    "finish_worker": "name, discard",
}


@pytest.mark.parametrize("tool", ACCEPTED)
def test_tools_refuse_unknown_arguments(repo, fake_tmux, tool):
    """An agent with a stale tool schema, or a typo, learns that its argument was not used."""
    runtime.start_session(str(repo), "s", None)
    assert sorted(ACCEPTED) == _tools("s", "supervisor")
    server = mcp_server.build("s", "supervisor")
    with pytest.raises(ToolError) as error:
        asyncio.run(server.call_tool(tool, {"foo": 1, "bar": 2}))
    assert str(error.value) == (
        f'{tool} has no argument "bar", "foo"; it accepts: {ACCEPTED[tool]}'
    )
    assert state.list_agents("s")[-1].name == "supervisor"  # nothing ran


def test_spawn_worker_takes_a_provider(repo, fake_tmux):
    runtime.start_session(str(repo), "s", None)
    server = mcp_server.build("s", "supervisor")
    asyncio.run(server.call_tool("spawn_worker", {"task": "t", "provider": "kilo"}))
    agents = asyncio.run(server.call_tool("list_agents", {}))
    assert "kilo" in str(agents)
    assert state.get_agent("s", "w1").provider == "kilo"


SHIP = """\
name: ship
description: build it, then the supervisor merges it
start: build
states:
  build: {agent: worker, do: Build it., outcomes: {done: merge}}
  merge: {agent: supervisor, do: Merge it., outcomes: {merged: end}}
  end: {end: true}
"""


def _call(session, agent, tool, args=None):
    result = asyncio.run(mcp_server.build(session, agent).call_tool(tool, args or {}))
    if result.structured_content is None:  # a dict comes as JSON text
        return json.loads(result.content[0].text)
    return result.structured_content["result"]


def test_flow_tools_start_a_run_spawn_its_worker_and_advance_it(repo, fake_tmux):
    kit = repo / ".lado" / "kits" / "k"
    (kit / "flows").mkdir(parents=True)
    (kit / "kit.yaml").write_text("name: k\ninclude: [default]\n")
    (kit / "flows" / "ship.yaml").write_text(SHIP)
    runtime.start_session(str(repo), "s", None, kit_names=["k"])
    run = _call("s", "supervisor", "flow_start", {"flow": "ship", "task": "Add x", "name": "x"})
    assert (run["run"], run["state"], run["acting"]) == ("ship/x", "build", "worker (not spawned)")
    [run] = _call("s", "supervisor", "flow_status", {"run": "ship/x"})
    worker = _call("s", "supervisor", "spawn_worker", {"run": "ship/x"})
    assert (worker["run"], worker["worktree"]) == ("ship/x", run["worktree"])
    [agent] = [a for a in _call("s", "supervisor", "list_agents") if a["name"] == "w1"]
    assert agent["run"] == "ship/x"
    with pytest.raises(ToolError, match='unknown outcome "ok" for step build; valid: done'):
        _call("s", "w1", "flow_advance", {"run": "ship/x", "outcome": "ok"})
    args = {"run": "ship/x", "outcome": "done", "note_summary": "built", "note_body": "x.py"}
    after = _call("s", "w1", "flow_advance", args)
    assert (after["state"], after["acting"], after["note"]) == ("merge", "supervisor", "built")
    [status] = _call("s", "w1", "flow_status")
    assert status["outcomes"] == {"merged": "end"}
    cancelled = _call("s", "supervisor", "flow_cancel", {"run": "ship/x", "reason": "stop"})
    assert cancelled["finished_workers"] == ["w1"]
    assert cancelled["kept"] == {"worktree": run["worktree"], "branch": run["branch"]}


SHORT = {"run", "flow", "state", "status", "acting", "outcomes", "gate", "visits", "note"}


def test_flow_tools_return_short_results_and_the_supervisors_own_notices(repo, fake_tmux):
    kit = repo / ".lado" / "kits" / "k"
    (kit / "flows").mkdir(parents=True)
    (kit / "kit.yaml").write_text("name: k\ninclude: [default]\n")
    (kit / "flows" / "ship.yaml").write_text(SHIP)
    runtime.start_session(str(repo), "s", None, kit_names=["k"])
    task = "Add x. " + "Details. " * 50
    args = {"flow": "ship", "task": task, "name": "x", "human_language": "ru"}
    run = _call("s", "supervisor", "flow_start", args)
    assert set(run) == SHORT | {"language", "notices"}
    assert run["language"] == "ru"
    assert run["notices"] == [
        "flow ship/x: step build needs a worker\n"
        'Start one with spawn_worker(role="worker", run="ship/x"); it gets the step as its task.'
    ]
    assert state.get_run("s", "ship/x").language == "ru"
    assert [m for m in state.list_messages("s") if m.recipient == "supervisor"] == []
    _call("s", "supervisor", "spawn_worker", {"run": "ship/x"})
    after = _call("s", "w1", "flow_advance", {"run": "ship/x", "outcome": "done"})
    assert set(after) == SHORT | {"language", "notices"}
    assert after["notices"] == []  # the worker's advance: the supervisor gets a message
    [status] = _call("s", "w1", "flow_status")
    assert set(status) == SHORT | {"language"}
    [detail] = _call("s", "supervisor", "flow_status", {"run": "ship/x"})
    assert detail["task"] == task.strip()
    assert detail["worktree"] == state.get_run("s", "ship/x").worktree


def test_no_agent_can_answer_a_gate(repo, fake_tmux):
    kit = repo / ".lado" / "kits" / "k"
    (kit / "flows").mkdir(parents=True)
    (kit / "kit.yaml").write_text("name: k\ninclude: [default]\n")
    gated = SHIP.replace("{done: merge}", "{done: check}") + (
        "  check: {gate: approval, ask: 'Go?', outcomes: {approved: merge, rejected: build}}\n"
    )
    (kit / "flows" / "ship.yaml").write_text(gated)
    runtime.start_session(str(repo), "s", None, kit_names=["k"])
    _call("s", "supervisor", "flow_start", {"flow": "ship", "task": "Add x", "name": "x"})
    _call("s", "supervisor", "spawn_worker", {"run": "ship/x"})
    waiting = _call("s", "w1", "flow_advance", {"run": "ship/x", "outcome": "done"})
    assert waiting["gate"] == {"id": 1, "question": "Go?", "options": ["approve", "reject"]}
    for agent in ("w1", "supervisor"):
        with pytest.raises(ToolError, match=r"waits for the human \(gate #1\): answer with lado"):
            _call("s", agent, "flow_advance", {"run": "ship/x", "outcome": "approved"})
    assert state.open_gate("s", "ship/x").id == 1


def test_spawn_worker_needs_a_task_without_a_run(repo, fake_tmux):
    runtime.start_session(str(repo), "s", None)
    with pytest.raises(ToolError, match="give the worker a task"):
        _call("s", "supervisor", "spawn_worker", {})


def test_spawn_worker_takes_a_role_and_without(repo, fake_tmux):
    kit = repo / ".lado" / "kits" / "k"
    (kit / "agents").mkdir(parents=True)
    (kit / "kit.yaml").write_text("name: k\ninclude: [default]\n")
    (kit / "agents" / "rev.md").write_text("---\nname: rev\ndescription: reviews\n---\nReview.\n")
    (kit / "skills" / "s").mkdir(parents=True)
    (kit / "skills" / "s" / "SKILL.md").write_text("---\nname: s\ndescription: d\n---\n")
    runtime.start_session(str(repo), "s", None, kit_names=["k"])
    server = mcp_server.build("s", "supervisor")
    args = {"task": "t", "role": "rev", "without": ["skill:s"]}
    asyncio.run(server.call_tool("spawn_worker", args))
    assert state.get_agent("s", "w1").role == "rev"
    cmd = fake_tmux[-1][5]
    assert "--add-dir" not in cmd
    assert "role" in str(asyncio.run(server.call_tool("list_agents", {})))
