import asyncio

from lado import mcp_server, runtime


def _tools(session, agent):
    tools = asyncio.run(mcp_server.build(session, agent).list_tools())
    return sorted(t.name for t in tools)


def test_only_supervisor_can_spawn_workers(repo, fake_tmux):
    runtime.start_session(str(repo), "s", None)
    runtime.spawn_worker("s", "task")
    assert _tools("s", "supervisor") == ["list_agents", "send_message", "spawn_worker"]
    assert _tools("s", "w1") == ["list_agents", "send_message"]
