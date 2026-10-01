import asyncio

from lado import mcp_server, runtime, state


def _tools(session, agent):
    tools = asyncio.run(mcp_server.build(session, agent).list_tools())
    return sorted(t.name for t in tools)


def test_only_supervisor_can_spawn_workers(repo, fake_tmux):
    runtime.start_session(str(repo), "s", None)
    runtime.spawn_worker("s", "task")
    assert _tools("s", "supervisor") == ["list_agents", "send_message", "spawn_worker"]
    assert _tools("s", "w1") == ["list_agents", "send_message"]


def test_spawn_worker_takes_a_provider(repo, fake_tmux):
    runtime.start_session(str(repo), "s", None)
    server = mcp_server.build("s", "supervisor")
    asyncio.run(server.call_tool("spawn_worker", {"task": "t", "provider": "kilo"}))
    agents = asyncio.run(server.call_tool("list_agents", {}))
    assert "kilo" in str(agents)
    assert state.get_agent("s", "w1").provider == "kilo"
