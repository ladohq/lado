"""MCP server that gives agents LADO tools. Each agent's CLI starts one over stdio.

The calling agent is identified by LADO_SESSION and LADO_AGENT, which lado.runtime writes
into that agent's MCP config.
"""

import os
from collections.abc import Iterator
from contextlib import contextmanager

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from lado import kits, runtime, state, tmux


@contextmanager
def _reasons() -> Iterator[None]:
    """Pass LADO's errors on to the agent. The MCP server shows the agent only "Error
    executing tool" for other exceptions, so it would not learn why or what to do."""
    try:
        yield
    except (runtime.LadoError, kits.KitError, tmux.TmuxError) as exc:
        raise ToolError(str(exc)) from exc


def build(session: str, agent: str) -> MCPServer:
    server = MCPServer("lado", instructions=f'You are agent "{agent}" in LADO session "{session}".')

    @server.tool()
    def list_agents() -> list[dict]:
        """List the agents in this session: role, provider, status, branch and worktree."""
        return [
            {
                "name": a.name,
                "role": a.role,
                "provider": a.provider,
                "status": a.status,
                "branch": a.branch,
                "worktree": a.cwd,
                "task": (a.task or "")[:200],
            }
            for a in state.list_agents(session)
        ]

    @server.tool()
    def send_message(to: str, summary: str, body: str | None = None) -> str:
        """Send a message to another agent in this session, e.g. to="supervisor".

        `summary` is one line (at most 200 characters) and is all the recipient sees at
        first; put the details in `body`, which it reads with read_messages. It is delivered
        right away if the agent is idle, otherwise when its current turn ends.
        """
        with _reasons():
            return runtime.send_message(session, agent, to, summary, body)

    @server.tool()
    def read_messages() -> list[dict]:
        """Read the bodies of the messages you got that you have not read yet, oldest first.

        A message with a body arrives as one line ending in "call read_messages". Each body
        is returned once; with nothing unread the list is empty.
        """
        return [
            {
                "id": m.id,
                "from": m.sender,
                "summary": m.title,
                "body": m.body,
                "time": f"{m.created_at} UTC",
            }
            for m in state.read_messages(session, agent)
        ]

    me = state.get_agent(session, agent)
    if me and me.name == runtime.SUPERVISOR:

        @server.tool()
        def spawn_worker(
            task: str,
            name: str | None = None,
            provider: str | None = None,
            role: str | None = None,
            without: list[str] | None = None,
        ) -> dict:
            """Start a new worker agent on `task` in its own git worktree and branch.

            `role` is one of the session's worker roles (default: the kits' default). `without`
            switches off skills or MCP servers for this worker, e.g. ["skill:x", "mcp:y"].
            `provider` is the agent CLI to run it with, e.g. "claude" or "kilo" (default: the
            session's). The worker reports back with send_message when it is done or blocked.
            """
            with _reasons():
                worker = runtime.spawn_worker(session, task, name, provider, role, without)
            return {
                "name": worker.name,
                "role": worker.role,
                "branch": worker.branch,
                "worktree": worker.cwd,
            }

        @server.tool()
        def finish_worker(name: str, discard: bool = False) -> dict:
            """End a worker once its branch is merged into your current branch: close its
            window, remove its worktree and branch. Its messages and events stay in the log.

            It refuses while the branch is not merged or the worktree has uncommitted changes.
            `discard=True` ends the worker anyway and throws that work away. Messages it has
            not received yet are dropped; the result counts them.
            """
            with _reasons():
                finished = runtime.finish_worker(session, name, discard)
            worker = finished.worker
            return {
                "name": worker.name,
                "finished": finished.how,
                "removed": {"window": worker.name, "worktree": worker.cwd, "branch": worker.branch},
                "dropped_messages": finished.dropped,
            }

    return server


def main() -> int:
    session, agent = os.environ.get("LADO_SESSION"), os.environ.get("LADO_AGENT")
    if not session or not agent:
        raise SystemExit("lado mcp is started by LADO agents; LADO_SESSION/LADO_AGENT not set")
    build(session, agent).run("stdio")
    return 0
