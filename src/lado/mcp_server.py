"""MCP server that gives agents LADO tools. Each agent's CLI starts one over stdio.

The calling agent is identified by LADO_SESSION and LADO_AGENT, which lado.runtime writes
into that agent's MCP config.
"""

import datetime
import os
from collections.abc import Iterator
from contextlib import contextmanager

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from lado import kits, runs, runtime, state, tmux


@contextmanager
def _reasons() -> Iterator[None]:
    """Pass LADO's errors on to the agent. The MCP server shows the agent only "Error
    executing tool" for other exceptions, so it would not learn why or what to do."""
    try:
        yield
    except (runtime.LadoError, kits.KitError, tmux.TmuxError) as exc:
        raise ToolError(str(exc)) from exc


class _Server(MCPServer):
    """Records once that the agent's CLI listed the tools: the agent's session-start hook
    waits for it, so that its first turn has them (lado.hooks)."""

    def __init__(self, session: str, agent: str, instance: str):
        super().__init__(
            "lado", instructions=f'You are agent "{agent}" in LADO session "{session}".'
        )
        self._lado_agent = (session, agent)
        self._lado_instance = instance  # "" when started without one: nothing to record

    async def list_tools(self):
        tools = await super().list_tools()
        if self._lado_instance:
            session, agent = self._lado_agent
            state.add_event(session, agent, state.MCP_READY, self._lado_instance)
            self._lado_instance = ""
        return tools

    async def call_tool(self, name, arguments, context=None):
        """Refuse arguments the tool does not have. The MCP library drops them without a
        word, so an agent with a stale tool schema, or a typo, would never learn that its
        argument was not used."""
        tool = self._tool_manager.get_tool(name)
        if tool:
            accepted = list(tool.parameters.get("properties", {}))
            unknown = ", ".join(f'"{a}"' for a in sorted(set(arguments) - set(accepted)))
            if unknown:
                raise ToolError(
                    f"{name} has no argument {unknown}; it accepts: {', '.join(accepted) or 'none'}"
                )
        return await super().call_tool(name, arguments, context)


def build(session: str, agent: str, instance: str = "") -> MCPServer:
    server = _Server(session, agent, instance)

    @server.tool()
    def list_agents() -> list[dict]:
        """List the agents in this session: role, provider, status (with since when and for
        how many seconds, and why it waits when LADO could not deliver it messages), branch
        and worktree."""
        since = state.status_since(session)
        now = datetime.datetime.now(datetime.timezone.utc)
        reasons = runtime.waiting_reasons(session)
        agents = []
        for a in state.list_agents(session):
            when = since.get(a.name)
            took = max(0, int((now - when).total_seconds())) if when else None
            agents.append(
                {
                    "name": a.name,
                    "role": a.role,
                    "provider": a.provider,
                    "status": a.status,
                    "status_since": when.isoformat() if when else None,
                    "status_for_seconds": took,
                    "waiting_reason": reasons.get(a.name),
                    "branch": a.branch,
                    "worktree": a.cwd,
                    "run": a.run,
                    "task": (a.task or "")[:200],
                }
            )
        return agents

    @server.tool()
    def flow_advance(
        run: str, outcome: str, note_summary: str | None = None, note_body: str | None = None
    ) -> dict:
        """Report the outcome of the flow step you were given; the run moves on to the next
        state and LADO tells whoever acts there.

        Only the agent acting in the run's current step can advance it. `outcome` is one of
        the step's outcomes. `note_summary` (one line) and `note_body` go to the next step.
        `notices` are what LADO tells you about the move you made (e.g. that the next step
        needs a worker), instead of a message.
        """
        with _reasons():
            notices = []
            advanced = runs.advance(
                session, agent, run, outcome, note_summary, note_body, notices=notices
            )
            return {**runs.describe(advanced), "notices": notices}

    @server.tool()
    def flow_status(run: str | None = None) -> list[dict]:
        """Flow runs: state, status, who acts, allowed outcomes, visits per state. A worker
        sees its own run; the supervisor every open run. With `run`, that one run with its
        task, worktree and branch."""
        with _reasons():
            return runs.status(session, agent, run)

    @server.tool()
    def send_message(to: str, summary: str, body: str | None = None) -> str:
        """Send a message to another agent in this session, e.g. to="supervisor", or to the
        human with to="human" (they read it in LADO's UI).

        `summary` is one line (at most 200 characters) and is all the recipient sees at
        first; put the details in `body`, which it reads with read_messages. It is delivered
        right away if the agent is idle, otherwise when its current turn ends.
        """
        with _reasons():
            return runtime.send_message(session, agent, to, summary, body)

    @server.tool()
    def ask_human(
        question: str,
        details: str | None = None,
        choices: list[str] | None = None,
        free_answer: bool = True,
    ) -> str:
        """Ask the human a question in LADO's UI, e.g. a decision with your recommendation.

        `question` is one line; `details` the rest. `choices` (at most 6, each one short
        line) are buttons; with `free_answer` the human may also answer in their own words.
        It does not wait: the answer, or that the human dismissed the question, comes as a
        message from human: "Answer to #<id>: ..." or "Dismissed #<id>".
        """
        with _reasons():
            return runtime.ask_human(session, agent, question, details, choices, free_answer)

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
            task: str | None = None,
            name: str | None = None,
            provider: str | None = None,
            role: str | None = None,
            without: list[str] | None = None,
            run: str | None = None,
        ) -> dict:
            """Start a new worker agent on `task` in its own git worktree and branch.

            `role` is one of the session's worker roles, required unless the session has
            one. Without `name`, the worker is named after its role: "developer", else
            "developer-2", …. `without` switches off skills or MCP servers for this worker,
            e.g. ["skill:x", "mcp:y"], or only those of one kit: ["skill:x@kit"].
            `provider` is the agent CLI to run it with, e.g. "claude" or "kilo" (default: the
            session's). The worker reports back with send_message when it is done or blocked,
            or with flow_advance when it finished a step of a run.

            With `run`, the worker works for that flow run, in the run's worktree and branch.
            If the run's current step waits for a worker, the step is its task: leave out
            `task` (and `role`, which then defaults to the step's role).
            """
            with _reasons():
                if run:
                    worker = runs.spawn_worker(session, run, role, task, name, provider, without)
                elif not task or not task.strip():
                    raise runtime.LadoError("task is missing; give the worker a task")
                else:
                    worker = runtime.spawn_worker(session, task, name, provider, role, without)
            return {
                "name": worker.name,
                "role": worker.role,
                "branch": worker.branch,
                "worktree": worker.cwd,
                "run": worker.run,
            }

        @server.tool()
        def flow_start(
            flow: str, task: str, name: str | None = None, human_language: str | None = None
        ) -> dict:
            """Start a run of a flow from the kits on `task`. Flows are optional: use one
            when its description fits the task.

            The run is named <flow>/<name> (default: from the task's first words) and gets
            its own git worktree and branch from your current HEAD, shared by its workers.
            LADO then sends each step to the agent that acts in it, or asks you to
            spawn_worker(role=..., run=...) when the step needs a worker: `notices` says so
            when the first step does.

            `human_language` is the language the human writes in, e.g. "ru": every step is
            told to write its notes in it, since the human reads them at gates.
            """
            with _reasons():
                notices = []
                started = runs.start(session, flow, task, name, notices, human_language)
                return {**runs.describe(started), "notices": notices}

        @server.tool()
        def flow_cancel(run: str, reason: str) -> dict:
            """Cancel an open flow run: its workers are finished, its worktree and branch
            are kept for you to merge or remove."""
            with _reasons():
                finished = runs.cancel(session, run, reason)
                cancelled = state.get_run(session, run)
            return {
                "run": run,
                "finished_workers": [f.worker.name for f in finished],
                "kept": {"worktree": cancelled.worktree, "branch": cancelled.branch},
            }

        @server.tool()
        def finish_worker(name: str, discard: bool = False) -> dict:
            """End a worker once its branch is merged into your current branch: close its
            window, remove its worktree and branch. Its messages and events stay in the log.

            It refuses while the branch is not merged or the worktree has uncommitted changes.
            `discard=True` ends the worker anyway and throws that work away. Messages it has
            not received yet are dropped; the result counts them.

            A worker of a flow run only has its window closed while its run is open or other
            workers of the run remain: the worktree and branch belong to the run.
            """
            with _reasons():
                finished = runtime.finish_worker(session, name, discard)
            worker = finished.worker
            removed = {"window": worker.name}
            if finished.removed_worktree:
                removed.update(worktree=worker.cwd, branch=worker.branch)
            return {
                "name": worker.name,
                "finished": finished.how,
                "removed": removed,
                "dropped_messages": finished.dropped,
            }

    return server


def main() -> int:
    session, agent = os.environ.get("LADO_SESSION"), os.environ.get("LADO_AGENT")
    if not session or not agent:
        raise SystemExit("lado mcp is started by LADO agents; LADO_SESSION/LADO_AGENT not set")
    build(session, agent, os.environ.get("LADO_INSTANCE", "")).run("stdio")
    return 0
