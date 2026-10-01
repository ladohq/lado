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
