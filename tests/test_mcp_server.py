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
        "list_agents",
        "read_messages",
        "send_message",
        "spawn_worker",
    ]
    assert _tools("s", "supervisor") == supervisor_tools
    assert _tools("s", "w1") == ["list_agents", "read_messages", "send_message"]


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


def test_spawn_worker_takes_a_provider(repo, fake_tmux):
    runtime.start_session(str(repo), "s", None)
    server = mcp_server.build("s", "supervisor")
    asyncio.run(server.call_tool("spawn_worker", {"task": "t", "provider": "kilo"}))
    agents = asyncio.run(server.call_tool("list_agents", {}))
    assert "kilo" in str(agents)
    assert state.get_agent("s", "w1").provider == "kilo"


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
