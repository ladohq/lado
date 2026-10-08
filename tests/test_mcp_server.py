import asyncio
import json
import re
from pathlib import Path

import agent_helpers
import pytest
from mcp.server.mcpserver.exceptions import ToolError

from lado import mcp_server, runtime, state, tmux


def _tools(session, agent):
    tools = asyncio.run(mcp_server.build(session, agent).list_tools())
    return sorted(t.name for t in tools)


def test_only_supervisor_can_spawn_workers(repo, fake_tmux):
    runtime.start_session(str(repo), "s", None, provider="claude")
    runtime.spawn_worker("s", "task", name="w1")
    supervisor_tools = [
        "ask_human",
        "finish_worker",
        "flow_advance",
        "flow_cancel",
        "flow_start",
        "flow_status",
        "list_agents",
        "list_artifacts",
        "read_artifact",
        "read_messages",
        "send_message",
        "spawn_worker",
        "write_artifact",
    ]
    assert _tools("s", "supervisor") == supervisor_tools
    assert _tools("s", "w1") == [
        "ask_human",
        "flow_advance",
        "flow_status",
        "list_agents",
        "list_artifacts",
        "read_artifact",
        "read_messages",
        "send_message",
        "write_artifact",
    ]


def test_listing_the_tools_records_that_the_server_is_ready(repo, fake_tmux):
    """The agent's session-start hook waits for this (lado.hooks)."""
    runtime.start_session(str(repo), "s", None, provider="claude")
    asyncio.run(mcp_server.build("s", "supervisor", instance="abc").list_tools())
    ready = [(e.agent, e.detail) for e in state.list_events("s") if e.kind == state.MCP_READY]
    assert ready == [("supervisor", "abc")]


def test_list_agents_says_since_when_and_how_long_each_has_its_status(repo, fake_tmux):
    runtime.start_session(str(repo), "s", None, provider="claude")
    runtime.spawn_worker("s", "task", name="w1")
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


def test_list_agents_says_why_an_agent_waits_after_failed_messages(repo, fake_tmux):
    runtime.start_session(str(repo), "s", None, provider="claude")
    runtime.spawn_worker("s", "task", name="w1")
    state.set_status("s", "supervisor", state.IDLE)
    runtime.send_message("s", "w1", "supervisor", "report")
    at = state.list_messages("s")[0].sent_at
    for delay in runtime.RETRY_DELAYS + runtime.RETRY_DELAYS[-1:]:
        at += delay
        runtime.sweep("s", now=at)
    result = asyncio.run(mcp_server.build("s", "w1").call_tool("list_agents", {}))
    supervisor, worker = result.structured_content["result"]
    assert supervisor["status"] == state.WAITING
    assert supervisor["status_reason"].startswith("did not take 1 message: answer the dialog")
    assert worker["status_reason"] is None


def test_list_agents_says_why_an_agent_stopped(repo, fake_tmux):
    runtime.start_session(str(repo), "s", None, provider="claude")
    runtime.spawn_worker("s", "task", name="w1")
    runtime.agent_ended("s", "w1", "its CLI exited")
    result = asyncio.run(mcp_server.build("s", "supervisor").call_tool("list_agents", {}))
    supervisor, worker = result.structured_content["result"]
    assert (worker["status"], worker["status_reason"]) == (state.STOPPED, "its CLI exited")
    assert supervisor["status_reason"] is None


def test_a_report_is_a_summary_and_a_body_read_once(repo, fake_tmux):
    runtime.start_session(str(repo), "s", None, provider="claude")
    runtime.spawn_worker("s", "task", name="w1")
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
        "artifacts": [],
    }
    again = asyncio.run(supervisor.call_tool("read_messages", {}))
    assert again.structured_content == {"result": []}


def test_finish_worker_reports_what_it_removed(repo, fake_tmux):
    runtime.start_session(str(repo), "s", None, provider="claude")
    worker = runtime.spawn_worker("s", "task", name="w1")
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
    runtime.start_session(str(repo), "s", None, provider="claude")
    server = mcp_server.build("s", "supervisor")
    with pytest.raises(ToolError) as error:
        asyncio.run(server.call_tool(tool, args))
    assert reason in str(error.value)


@pytest.mark.parametrize(
    ("tool", "args"), [("list_agents", {}), ("send_message", {"to": "w1", "summary": "hi"})]
)
def test_a_tool_on_an_older_schema_says_why_and_changes_nothing(repo, fake_tmux, tool, args):
    """LADO upgraded in place under a running session: `lado mcp` runs the new code."""
    runtime.start_session(str(repo), "s", None, provider="claude")
    agent_helpers.previous_schema()
    before = agent_helpers.database()
    server = mcp_server.build("s", "supervisor", instance="abc")
    asyncio.run(server.list_tools())  # the CLI still gets the tools
    with pytest.raises(ToolError) as error:
        asyncio.run(server.call_tool(tool, args))
    assert "LADO was upgraded under a running session" in str(error.value)
    assert "`lado stop --all`, then `lado start`" in str(error.value)
    assert agent_helpers.database() == before


def test_spawn_worker_without_tmux_says_why_and_what_its_undo_could_not_do(
    repo, fake_tmux, monkeypatch
):
    runtime.start_session(str(repo), "s", None, provider="claude")

    def no_tmux(*args):
        raise tmux.TmuxMissing("tmux is not installed or not on PATH (/nowhere)")

    monkeypatch.setattr(tmux, "new_window", no_tmux)
    monkeypatch.setattr(tmux, "kill_window", no_tmux)
    server = mcp_server.build("s", "supervisor")
    with pytest.raises(ToolError) as error:
        asyncio.run(server.call_tool("spawn_worker", {"task": "t"}))
    assert str(error.value) == (
        "Error executing tool spawn_worker: tmux is not installed or not on PATH (/nowhere)\n"
        "undo of the spawn of worker: close its window failed: TmuxMissing: "
        "tmux is not installed or not on PATH (/nowhere)"
    )
    assert [a.name for a in state.list_agents("s")] == ["supervisor"]


def test_spawn_worker_refuses_a_provider_without_the_sessions_mode(repo, fake_tmux):
    runtime.start_session(str(repo), "s", "dontAsk", provider="claude")
    server = mcp_server.build("s", "supervisor")
    with pytest.raises(ToolError) as error:
        asyncio.run(server.call_tool("spawn_worker", {"task": "t", "provider": "kilo"}))
    assert '"dontAsk" is not supported by Kilo CLI (kilo)' in str(error.value)


ACCEPTED = {
    "list_agents": "none",
    "flow_advance": "run, outcome, note_summary, note_body, artifacts",
    "flow_status": "run",
    "send_message": "to, summary, body, artifacts",
    "ask_human": "question, details, choices, free_answer, artifacts",
    "read_messages": "none",
    "write_artifact": "name, content, file, media_type, summary, title",
    "read_artifact": "name, from_line, to_line",
    "list_artifacts": "run",
    "spawn_worker": "task, name, provider, role, without, run",
    "flow_start": "flow, task, name, human_language",
    "flow_cancel": "run, reason",
    "finish_worker": "name, discard",
}


@pytest.mark.parametrize("tool", ACCEPTED)
def test_tools_refuse_unknown_arguments(repo, fake_tmux, tool):
    """An agent with a stale tool schema, or a typo, learns that its argument was not used."""
    runtime.start_session(str(repo), "s", None, provider="claude")
    assert sorted(ACCEPTED) == _tools("s", "supervisor")
    server = mcp_server.build("s", "supervisor")
    with pytest.raises(ToolError) as error:
        asyncio.run(server.call_tool(tool, {"foo": 1, "bar": 2}))
    assert str(error.value) == (
        f'{tool} has no argument "bar", "foo"; it accepts: {ACCEPTED[tool]}'
    )
    assert state.list_agents("s")[-1].name == "supervisor"  # nothing ran


def test_spawn_worker_takes_a_provider(repo, fake_tmux):
    runtime.start_session(str(repo), "s", None, provider="claude")
    server = mcp_server.build("s", "supervisor")
    asyncio.run(server.call_tool("spawn_worker", {"task": "t", "provider": "kilo"}))
    agents = asyncio.run(server.call_tool("list_agents", {}))
    assert "kilo" in str(agents)
    assert state.get_agent("s", "worker").provider == "kilo"


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
    (kit / "kit.yaml").write_text("name: k\nversion: 1.0.0\n")
    (kit / "flows" / "ship.yaml").write_text(SHIP)
    runtime.start_session(str(repo), "s", None, kit_names=["default", "k"], provider="claude")
    run = _call("s", "supervisor", "flow_start", {"flow": "ship", "task": "Add x", "name": "x"})
    assert (run["run"], run["state"], run["acting"]) == ("ship/x", "build", "worker (not spawned)")
    [run] = _call("s", "supervisor", "flow_status", {"run": "ship/x"})
    worker = _call("s", "supervisor", "spawn_worker", {"run": "ship/x"})
    assert (worker["run"], worker["worktree"]) == ("ship/x", run["worktree"])
    assert worker["name"] == "worker"  # named after its role
    [agent] = [a for a in _call("s", "supervisor", "list_agents") if a["name"] == "worker"]
    assert agent["run"] == "ship/x"
    with pytest.raises(ToolError, match='unknown outcome "ok" for step build; valid: done'):
        _call("s", "worker", "flow_advance", {"run": "ship/x", "outcome": "ok"})
    args = {"run": "ship/x", "outcome": "done", "note_summary": "built", "note_body": "x.py"}
    after = _call("s", "worker", "flow_advance", args)
    assert (after["state"], after["acting"], after["note"]) == ("merge", "supervisor", "built")
    [status] = _call("s", "worker", "flow_status")
    assert status["outcomes"] == {"merged": "end"}
    cancelled = _call("s", "supervisor", "flow_cancel", {"run": "ship/x", "reason": "stop"})
    assert cancelled["finished_workers"] == ["worker"]
    assert cancelled["kept"] == {"worktree": run["worktree"], "branch": run["branch"]}


@pytest.mark.parametrize("run", [False, True])
def test_spawn_worker_says_what_holds_the_worker_before_its_first_hook(
    repo, fake_tmux, claude_config, run
):
    kit = repo / ".lado" / "kits" / "k"
    (kit / "flows").mkdir(parents=True)
    (kit / "kit.yaml").write_text("name: k\nversion: 1.0.0\n")
    (kit / "flows" / "ship.yaml").write_text(SHIP)
    claude_config.trust()  # Claude Code trusts no folder; Kilo asks nothing
    runtime.start_session(str(repo), "s", None, kit_names=["default", "k"], provider="kilo")
    args = {"provider": "claude"}
    if run:
        _call("s", "supervisor", "flow_start", {"flow": "ship", "task": "Add x", "name": "x"})
        args["run"] = "ship/x"
    else:
        args["task"] = "t"
    worker = _call("s", "supervisor", "spawn_worker", args)
    assert worker["warnings"] == [
        f'Claude Code asks whether to trust {repo}: in its terminal choose "Yes, I trust '
        'this folder" (Enter alone answers "No, exit" and closes the agent)'
    ]
    claude_config.trust(repo)
    worker = _call("s", "supervisor", "spawn_worker", {**args, "task": "t", "name": "w2"})
    assert worker["warnings"] == []


SHORT = {
    "run",
    "flow",
    "state",
    "status",
    "acting",
    "outcomes",
    "produces",
    "gate",
    "visits",
    "note",
}


def test_flow_tools_return_short_results_and_the_supervisors_own_notices(repo, fake_tmux):
    kit = repo / ".lado" / "kits" / "k"
    (kit / "flows").mkdir(parents=True)
    (kit / "kit.yaml").write_text("name: k\nversion: 1.0.0\n")
    (kit / "flows" / "ship.yaml").write_text(SHIP)
    runtime.start_session(str(repo), "s", None, kit_names=["default", "k"], provider="claude")
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
    after = _call("s", "worker", "flow_advance", {"run": "ship/x", "outcome": "done"})
    assert set(after) == SHORT | {"language", "notices"}
    assert after["notices"] == []  # the worker's advance: the supervisor gets a message
    [status] = _call("s", "worker", "flow_status")
    assert set(status) == SHORT | {"language"}
    [detail] = _call("s", "supervisor", "flow_status", {"run": "ship/x"})
    assert detail["task"] == task.strip()
    assert detail["worktree"] == state.get_run("s", "ship/x").worktree


def test_no_agent_can_answer_a_gate(repo, fake_tmux):
    kit = repo / ".lado" / "kits" / "k"
    (kit / "flows").mkdir(parents=True)
    (kit / "kit.yaml").write_text("name: k\nversion: 1.0.0\n")
    gated = SHIP.replace("{done: merge}", "{done: check}") + (
        "  check: {gate: approval, ask: 'Go?', outcomes: {approved: merge, rejected: build}}\n"
    )
    (kit / "flows" / "ship.yaml").write_text(gated)
    runtime.start_session(str(repo), "s", None, kit_names=["default", "k"], provider="claude")
    _call("s", "supervisor", "flow_start", {"flow": "ship", "task": "Add x", "name": "x"})
    _call("s", "supervisor", "spawn_worker", {"run": "ship/x"})
    waiting = _call("s", "worker", "flow_advance", {"run": "ship/x", "outcome": "done"})
    assert waiting["gate"] == {"id": 1, "question": "Go?", "options": ["approve", "reject"]}
    for agent in ("worker", "supervisor"):
        with pytest.raises(ToolError, match=r"waits for the human \(gate #1\): answer with lado"):
            _call("s", agent, "flow_advance", {"run": "ship/x", "outcome": "approved"})
    assert state.open_gate("s", "ship/x").id == 1


def test_spawn_worker_needs_a_task_without_a_run(repo, fake_tmux):
    runtime.start_session(str(repo), "s", None, provider="claude")
    with pytest.raises(ToolError, match="give the worker a task"):
        _call("s", "supervisor", "spawn_worker", {})


def test_spawn_worker_takes_a_role_and_without(repo, fake_tmux):
    kit = repo / ".lado" / "kits" / "k"
    (kit / "agents").mkdir(parents=True)
    (kit / "kit.yaml").write_text("name: k\nversion: 1.0.0\n")
    (kit / "agents" / "rev.md").write_text("---\nname: rev\ndescription: reviews\n---\nReview.\n")
    (kit / "skills" / "s").mkdir(parents=True)
    (kit / "skills" / "s" / "SKILL.md").write_text("---\nname: s\ndescription: d\n---\n")
    runtime.start_session(str(repo), "s", None, kit_names=["default", "k"], provider="claude")
    server = mcp_server.build("s", "supervisor")
    args = {"task": "t", "role": "rev", "without": ["skill:s"]}
    asyncio.run(server.call_tool("spawn_worker", args))
    assert state.get_agent("s", "rev").role == "rev"
    cmd = fake_tmux[-1][-1]
    assert "--add-dir" not in cmd
    assert "role" in str(asyncio.run(server.call_tool("list_agents", {})))


def test_an_agent_writes_to_and_asks_the_human(repo, fake_tmux):
    runtime.start_session(str(repo), "s", None, provider="claude")
    runtime.spawn_worker("s", "task", name="w1")
    sent = _call("s", "w1", "send_message", {"to": "human", "summary": "a milestone"})
    assert sent == runtime.TO_HUMAN
    asked = _call(
        "s",
        "w1",
        "ask_human",
        {"question": "Merge?", "choices": ["yes", "no"], "free_answer": False},
    )
    message, question = state.list_messages("s")
    assert asked.startswith(f"question #{question.id} asked")
    assert (message.recipient, message.kind) == ("human", state.MESSAGE)
    assert (question.sender, question.choices, question.free_answer) == ("w1", ["yes", "no"], False)
    with pytest.raises(ToolError, match="no choices and no free answer"):
        _call("s", "w1", "ask_human", {"question": "Merge?", "free_answer": False})


def test_the_tools_tell_agents_about_the_human(repo, fake_tmux):
    runtime.start_session(str(repo), "s", None, provider="claude")
    tools = {t.name: t for t in asyncio.run(mcp_server.build("s", "supervisor").list_tools())}
    assert 'to="human"' in tools["send_message"].description
    assert "message from human" in tools["ask_human"].description


def test_a_worker_writes_a_file_of_its_worktree_as_an_artifact_and_others_read_it(
    repo, fake_tmux, tmp_path, monkeypatch
):
    runtime.start_session(str(repo), "s", None, provider="claude")
    worker = runtime.spawn_worker("s", "task", name="w1")
    (Path(worker.cwd) / "report.md").write_text("# Report\nall green\n")
    monkeypatch.chdir(tmp_path)  # `lado mcp` runs elsewhere: the path is the agent's
    args = {"name": "report", "file": "report.md", "summary": "first", "title": "Report"}
    written = _call("s", "w1", "write_artifact", args)
    assert written == {
        "name": "report",
        "status": "created",
        "size": 19,
        "media_type": "text/markdown",
    }
    assert _call("s", "w1", "write_artifact", args)["status"] == "unchanged"
    read = _call("s", "supervisor", "read_artifact", {"name": "report", "from_line": 2})
    assert (read["content"], read["lines"], read["from_line"], read["to_line"]) == (
        "all green\n",
        2,
        2,
        2,
    )
    [listed] = _call("s", "supervisor", "list_artifacts")
    assert {k: v for k, v in listed.items() if k != "time"} == {
        "name": "report",
        "title": "Report",
        "media_type": "text/markdown",
        "size": 19,
        "author": "w1",
        "summary": "first",
    }
    assert listed["time"].endswith(" UTC")


def test_list_artifacts_lists_the_agents_scope_or_a_runs(repo, fake_tmux):
    runtime.start_session(str(repo), "s", None, provider="claude")
    state.add_run(
        state.Run("s", "ship/x", "ship", "{}", {}, "t", "build", "/w", "lado/s/x", {"build": 1}),
        [],
    )
    _call("s", "supervisor", "write_artifact", {"name": "plan", "content": "x"})
    _call("s", "supervisor", "write_artifact", {"name": "ship/x/design", "content": "x"})
    assert [a["name"] for a in _call("s", "supervisor", "list_artifacts")] == ["plan"]
    listed = _call("s", "supervisor", "list_artifacts", {"run": "ship/x"})
    assert [a["name"] for a in listed] == ["ship/x/design"]


@pytest.mark.parametrize(
    ("tool", "args", "reason"),
    [
        ("write_artifact", {"name": "plan"}, "give exactly one of content and file"),
        ("write_artifact", {"name": "Plan", "content": "x"}, "a name is 1-64 characters"),
        ("read_artifact", {"name": "nothing"}, 'no artifact "nothing" in session s'),
        ("list_artifacts", {"run": "ship/none"}, 'no run "ship/none" in session s'),
    ],
)
def test_artifact_tools_tell_the_agent_why(repo, fake_tmux, tool, args, reason):
    runtime.start_session(str(repo), "s", None, provider="claude")
    with pytest.raises(ToolError, match=re.escape(reason)):
        _call("s", "supervisor", tool, args)


def test_read_artifact_of_a_binary_gives_its_metadata(repo, fake_tmux):
    runtime.start_session(str(repo), "s", None, provider="claude")
    (repo / "logo.png").write_bytes(b"\x89PNG")
    _call("s", "supervisor", "write_artifact", {"name": "logo", "file": "logo.png"})
    read = _call("s", "supervisor", "read_artifact", {"name": "logo"})
    assert (read["binary"], read["note"], read["size"]) == (
        True,
        "not shown: its header cannot be read as image/png",
        4,
    )
