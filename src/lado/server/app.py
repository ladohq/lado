"""The UI server's FastAPI app: the API under /api, the web UI's bundle on /.

Its OpenAPI schema is the one contract with the UI (web/openapi.json, from which the UI's
TypeScript types are made). Data comes only through lado.state and lado.runtime; the server
never migrates the database: another schema version answers 503.
"""

from collections.abc import Callable
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, WebSocket
from fastapi.responses import FileResponse, PlainTextResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from lado import __version__, runs, runtime, state, terminal
from lado.server import feed, models, terminals
from lado.server.auth import Guard
from lado.server.models import (
    AgentInfo,
    Answer,
    GateAnswer,
    GateInfo,
    History,
    MessageInfo,
    MessageText,
    RunEventInfo,
    Sent,
    SessionInfo,
    WaitingItem,
)

STATIC = Path(__file__).parent / "static"  # the built bundle (make web); not in git
BUILD_HINT = "build it with `make web` in a LADO checkout"


class Health(BaseModel):
    ok: bool
    version: str


def database() -> bool:
    """A dependency of every endpoint that reads lado.db: whether there is one. Reads its
    schema version without opening it for writing, so the server never migrates it."""
    problem = feed.schema_problem()
    if problem:
        raise HTTPException(503, problem)
    return feed.database_made()


def known(name: str, has_db: bool) -> None:
    """404 for a session lado.db does not have."""
    if not has_db or state.get_session(name) is None:
        raise HTTPException(404, f'unknown session "{name}"')


def core(action: Callable[..., str], *args) -> str:
    """Do what the human asked through the core; what it refuses is 400 with its reason."""
    try:
        return action(*args)
    except runtime.LadoError as refused:
        raise HTTPException(400, str(refused)) from refused


def bundle_missing(static: Path) -> bool:
    return not (static / "index.html").is_file()


def contract() -> dict:
    """The API's OpenAPI schema as web/openapi.json keeps it (`make web-types`): without
    LADO's version, so a release does not change it."""
    schema = create_app("", 0).openapi()
    del schema["info"]["version"]
    return schema


def create_app(token: str, port: int, static: Path = STATIC) -> FastAPI:
    guard = Guard(token, port)
    hub = feed.Hub(feed.Journal())
    app = FastAPI(title="LADO", version=__version__)

    @app.get("/api/health")
    def health() -> Health:
        return Health(ok=True, version=__version__)

    @app.get("/api/sessions", dependencies=[Depends(guard)])
    def sessions(has_db: bool = Depends(database)) -> list[SessionInfo]:
        if not has_db:
            return []
        return [models.session_info(sess) for sess in state.list_sessions()]

    @app.get("/api/waiting", dependencies=[Depends(guard)])
    def waiting(has_db: bool = Depends(database)) -> list[WaitingItem]:
        """What waits for the human in every session not stopped, oldest first: open gates,
        open questions to the human and agents in `waiting` (Needs you)."""
        if not has_db:
            return []
        return [models.waiting_item(waits) for waits in state.waiting_items()]

    @app.get(
        "/api/events",
        dependencies=[Depends(guard), Depends(database)],
        response_class=StreamingResponse,
        responses={200: {"content": {"text/event-stream": {}}}},
    )
    async def events(
        after: int | None = None, last_event_id: int | None = Header(None)
    ) -> StreamingResponse:
        """The change feed as Server-Sent Events (lado.server.feed). The position is the
        Last-Event-ID header (the browser's own reconnect) or, without it, `after`."""
        position = last_event_id if last_event_id is not None else after
        try:
            await feed.check(hub)
        except feed.Unavailable as error:
            raise HTTPException(503, str(error)) from error
        return StreamingResponse(
            feed.stream(hub, position),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache"},
        )

    @app.get("/api/sessions/{name}/agents", dependencies=[Depends(guard)])
    def agents(name: str, has_db: bool = Depends(database)) -> list[AgentInfo]:
        if not has_db or state.get_session(name) is None:
            raise HTTPException(404, f'unknown session "{name}"')
        return [models.agent_info(agent) for agent in state.list_agents(name)]

    @app.get("/api/sessions/{name}/messages", dependencies=[Depends(guard)])
    def messages(
        name: str,
        with_: Literal["human"] | None = Query(None, alias="with"),
        has_db: bool = Depends(database),
    ) -> list[MessageInfo]:
        """The session's messages, oldest first; with `with`, only those from and to it
        (the human: the chat)."""
        known(name, has_db)
        return [
            models.message_info(m)
            for m in state.list_messages(name)
            if with_ is None or with_ in (m.sender, m.recipient)
        ]

    @app.get("/api/sessions/{name}/events", dependencies=[Depends(guard)])
    def run_events(name: str, has_db: bool = Depends(database)) -> list[RunEventInfo]:
        """What happened to the session's flow runs, oldest first."""
        known(name, has_db)
        return [models.run_event_info(e) for e in state.run_events(name)]

    @app.get("/api/sessions/{name}/gates", dependencies=[Depends(guard)])
    def gates(name: str, has_db: bool = Depends(database)) -> list[GateInfo]:
        """The session's gates, open and closed, oldest first."""
        known(name, has_db)
        return [models.gate_info(g) for g in state.session_gates(name)]

    @app.post("/api/sessions/{name}/gates/{gate}/answer", dependencies=[Depends(guard.changes)])
    def answer_gate(
        name: str, gate: int, given: GateAnswer, has_db: bool = Depends(database)
    ) -> Sent:
        """The human's answer to an open gate: one of its options and a comment for the
        next step. The same core as `lado answer` and the popup."""
        known(name, has_db)
        return Sent(result=core(runs.answer_text, name, str(gate), given.option, given.comment))

    @app.post("/api/sessions/{name}/messages", dependencies=[Depends(guard.changes)])
    def write(name: str, message: MessageText, has_db: bool = Depends(database)) -> Sent:
        """The human's text to an agent of the session (default: the supervisor), through
        the same queue and delivery as an agent's message."""
        known(name, has_db)
        return Sent(result=core(runtime.write_as_human, name, message.text, message.to))

    @app.post(
        "/api/sessions/{name}/questions/{question}/answer", dependencies=[Depends(guard.changes)]
    )
    def answer(name: str, question: int, given: Answer, has_db: bool = Depends(database)) -> Sent:
        """The human's answer to an agent's open question: a choice, own words, or both."""
        known(name, has_db)
        return Sent(result=core(runtime.answer_question, name, question, given.choice, given.text))

    @app.post(
        "/api/sessions/{name}/questions/{question}/dismiss", dependencies=[Depends(guard.changes)]
    )
    def dismiss(name: str, question: int, has_db: bool = Depends(database)) -> Sent:
        """The human dismisses an agent's open question; the agent hears of it."""
        known(name, has_db)
        return Sent(result=core(runtime.dismiss_question, name, question))

    @app.get("/api/sessions/{name}/agents/{agent}/history", dependencies=[Depends(guard)])
    def history(
        name: str,
        agent: str,
        lines: int = Query(2000, ge=1, le=50000),
        has_db: bool = Depends(database),
    ) -> History:
        """The agent's window: its last `lines` lines, for the UI's read-only history, and
        whether the agent shows a full-screen program, whose history is inside it."""
        if not has_db:
            raise HTTPException(404, f'unknown session "{name}"')
        try:
            found = terminal.history(name, agent, lines)
        except terminal.NoTerminal as none:
            raise HTTPException(404, str(none)) from none
        return History(text=found.text, alternate=found.alternate)

    @app.websocket("/api/sessions/{name}/agents/{agent}/terminal")
    async def terminal_socket(ws: WebSocket, name: str, agent: str, mode: str = terminal.VIEW):
        """The agent's terminal (lado.server.terminals): mode view or control."""
        await terminals.serve(ws, guard, name, agent, mode)

    if (static / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=static / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def page(path: str, request: Request):
        """A file of the bundle, or for any other path the UI's page, whose router shows it.
        A path under /api or /assets, or one at the top that names a file (has an
        extension), is never the page: an open tab asking for a file an upgrade removed gets
        404, not HTML. Deeper down a dot is part of a name (`/sessions/a.b`)."""
        if path == "api" or path.startswith("api/") or path.startswith("assets/"):
            raise HTTPException(404)
        if "token" in request.query_params:
            return guard.login(request)
        file = bundle_file(static, path)
        if file is not None:
            return FileResponse(file)
        if "/" not in path and "." in path:
            raise HTTPException(404)
        if bundle_missing(static):
            return PlainTextResponse(f"The web UI's bundle is missing: {BUILD_HINT}.", 503)
        return FileResponse(static / "index.html")

    return app


def bundle_file(static: Path, path: str) -> Path | None:
    """The file `path` names in the bundle's top folder (favicon and the like), if any."""
    if not path or "/" in path:
        return None
    file = (static / path).resolve()
    if file.parent != static.resolve() or not file.is_file():
        return None
    return file


if __name__ == "__main__":  # `make web-types`
    import json

    print(json.dumps(contract(), indent=2))
