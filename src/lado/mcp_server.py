"""MCP server that gives agents LADO tools. Each agent's CLI starts one over stdio.

The calling agent is identified by LADO_SESSION and LADO_AGENT, which lado.runtime writes
into that agent's MCP config.
"""

import os

from mcp.server.mcpserver import MCPServer

from lado import runtime, state


def build(session: str, agent: str) -> MCPServer:
    server = MCPServer("lado", instructions=f'You are agent "{agent}" in LADO session "{session}".')

    @server.tool()
    def list_agents() -> list[dict]:
        """List the agents in this session with their role, status, branch and worktree."""
        return [
            {
                "name": a.name,
                "role": a.role,
                "status": a.status,
                "branch": a.branch,
                "worktree": a.cwd,
                "task": (a.task or "")[:200],
            }
            for a in state.list_agents(session)
        ]

    @server.tool()
    def send_message(to: str, text: str) -> str:
        """Send a message to another agent in this session, e.g. to="supervisor".

        It is delivered right away if the agent is idle, otherwise when its current turn ends.
        """
        return runtime.send_message(session, agent, to, text)

    me = state.get_agent(session, agent)
    if me and me.role == runtime.SUPERVISOR:

        @server.tool()
        def spawn_worker(task: str, name: str | None = None) -> dict:
            """Start a new worker agent on `task` in its own git worktree and branch.

            The worker reports back with send_message when it is done or blocked.
            """
            worker = runtime.spawn_worker(session, task, name)
            return {"name": worker.name, "branch": worker.branch, "worktree": worker.cwd}

    return server


def main() -> int:
    session, agent = os.environ.get("LADO_SESSION"), os.environ.get("LADO_AGENT")
    if not session or not agent:
        raise SystemExit("lado mcp is started by LADO agents; LADO_SESSION/LADO_AGENT not set")
    build(session, agent).run("stdio")
    return 0
