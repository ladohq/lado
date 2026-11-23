import dataclasses

import agent_helpers

from lado import mcp_stdio, runtime, state


def test_the_tool_set_is_what_the_agent_s_row_says(repo, fake_tmux):
    runtime.start_session(str(repo), "s", None, provider="claude")
    runtime.spawn_worker("s", "task", name="w1")
    agent_helpers.forget_tasks("s")
    lead, worker = state.get_agent("s", "supervisor"), state.get_agent("s", "w1")
    assert mcp_stdio.tool_set(None) == "none"
    assert mcp_stdio.tool_set(worker) == "worker"
    assert mcp_stdio.tool_set(dataclasses.replace(worker, read_only=True)) == "read-only"
    assert mcp_stdio.tool_set(lead) == "supervisor"
    lead_read_only = dataclasses.replace(lead, read_only=True)
    assert mcp_stdio.tool_set(lead_read_only) == "read-only-supervisor"


def test_the_supervisor_s_name_is_the_runtime_s():
    """mcp_stdio does not import lado.runtime: it costs the server's start 0.05 s."""
    assert mcp_stdio.SUPERVISOR == runtime.SUPERVISOR


def test_the_instructions_name_the_agent_and_its_session():
    assert mcp_stdio.instructions("s", "w1") == 'You are agent "w1" in LADO session "s".'
