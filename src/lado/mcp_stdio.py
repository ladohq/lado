"""The process of an agent's LADO MCP server (`lado mcp`), lean so that it starts fast.

It imports the standard library and lado.state only; lado.mcp_server and with it the MCP
SDK, whose import is almost all of the server's start, load later.
"""

from lado import state

SUPERVISOR = "supervisor"  # the lead's agent name (lado.runtime.SUPERVISOR)


def tool_set(me: state.Agent | None) -> str:
    """Which tools the agent's server has (lado.mcp_server.build): none of the agent's own
    without its row, a worker's, or the supervisor's, each read-only or not."""
    if me is None:
        return "none"
    if me.name == SUPERVISOR:
        return "read-only-supervisor" if me.read_only else "supervisor"
    return "read-only" if me.read_only else "worker"


def instructions(session: str, agent: str) -> str:
    """The server's instructions to the agent's CLI."""
    return f'You are agent "{agent}" in LADO session "{session}".'
