"""The UI server's FastAPI app: the API under /api, the web UI's bundle on /.

Its OpenAPI schema is the one contract with the UI (web/openapi.json, from which the UI's
TypeScript types are made). Data comes only through lado.state and lado.runtime; the server
never migrates the database: another schema version answers 503.
"""

import datetime
from collections.abc import Callable
from pathlib import Path
from typing import Literal, TypeVar

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, WebSocket
from fastapi.responses import FileResponse, PlainTextResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from lado import __version__, kits, runs, runtime, state, terminal
from lado.server import feed, launch, models, terminals
from lado.server.auth import Guard
from lado.server.models import (
    AgentDetails,
    AgentInfo,
    Answer,
    Finish,
    FinishPreviewInfo,
    FolderInfo,
    ForgetPreview,
    Forgotten,
    GateAnswer,
    GateInfo,
    History,
    KitInfo,
    Launch,
    MessagePage,
    MessageText,
    NoteInfo,
    ProviderInfo,
    RecentFolder,
    Refused,
    Resume,
    RunEventInfo,
    RunInfo,
    Sent,
    SessionInfo,
    Started,
    Stopped,
    StopPreview,
    Taken,
    WaitingItem,
)

T = TypeVar("T")
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


def core(action: Callable[..., T], *args) -> T:
    """Do what the human asked through the core; what it refuses is 400 with its reason."""
    try:
        return action(*args)
    except runtime.LadoError as refused:
        raise HTTPException(400, str(refused)) from refused


def _kits_refused(refused: kits.KitError) -> HTTPException:
    """A start or resume the session's kits refuse: 400 with Refused."""
    detail = Refused(message=str(refused), switch_off=refused.switch_off)
    return HTTPException(400, detail.model_dump(mode="json"))


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

    @app.get("/api/folders", dependencies=[Depends(guard)])
    def folder(path: str, has_db: bool = Depends(database)) -> FolderInfo:
        """A folder as the New session window checks it: whether a session can start
        there (the core's reason when not), its subfolders and the session name it gives."""
        return core(launch.folder_info, path, has_db)

    @app.get("/api/folders/recent", dependencies=[Depends(guard)])
    def recent_folders(has_db: bool = Depends(database)) -> list[RecentFolder]:
        """The folders of past sessions, the latest started first."""
        return launch.recent_folders() if has_db else []

    @app.get("/api/kits", dependencies=[Depends(guard)])
    def list_kits(where: str | None = None) -> list[KitInfo]:
        """The kits a session of the folder `where` can take, one per name."""
        return core(launch.kit_infos, where)

    @app.get("/api/providers", dependencies=[Depends(guard)])
    def list_providers() -> list[ProviderInfo]:
        """LADO's providers and whether each one's CLI can run here, checked anew."""
        return launch.provider_infos()

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

    def known_agent(name: str, agent: str, has_db: bool) -> state.Agent:
        """The session's agent; 404 for an unknown session or agent."""
        known(name, has_db)
        found = state.get_agent(name, agent)
        if found is None:
            raise HTTPException(404, f'no agent "{agent}" in session "{name}"')
        return found

    @app.get("/api/sessions/{name}/agents/{agent}/details", dependencies=[Depends(guard)])
    def agent_details(name: str, agent: str, has_db: bool = Depends(database)) -> AgentDetails:
        """The agent's whole task and where its work stands in git now (not in the feed:
        git is asked on each request)."""
        return models.agent_details(known_agent(name, agent, has_db))

    @app.get("/api/sessions/{name}/agents/{agent}/finish-preview", dependencies=[Depends(guard)])
    def finish_preview(
        name: str, agent: str, has_db: bool = Depends(database)
    ) -> FinishPreviewInfo:
        """What finishing the worker would do now, refused as the finish would be."""
        known_agent(name, agent, has_db)
        return models.finish_preview_info(core(runtime.finish_preview, name, agent))

    @app.post("/api/sessions/{name}/agents/{agent}/finish", dependencies=[Depends(guard.changes)])
    def finish(name: str, agent: str, given: Finish, has_db: bool = Depends(database)) -> Sent:
        """Finish the worker, as `lado finish` does."""
        known(name, has_db)
        return Sent(result=core(runtime.finish_worker, name, agent, given.discard).text())

    @app.get("/api/sessions/{name}/messages", dependencies=[Depends(guard)])
    def messages(
        name: str,
        with_: Literal["human"] | None = Query(None, alias="with"),
        agent: str | None = None,
        before: int | None = None,
        after: int | None = None,
        since: datetime.datetime | None = None,
        until: datetime.datetime | None = None,
        limit: int | None = Query(None, ge=1),
        has_db: bool = Depends(database),
    ) -> MessagePage:
        """The session's messages, oldest first: with `with`, only those from and to it
        (the human: the chat), with `agent` from and to that agent; ids below `before` and
        above `after`; made from the second of `since` to the end of the second of `until`;
        the latest `limit` of them, or all without it."""
        known(name, has_db)
        where = state.MessageFilter(
            with_=with_,
            agent=agent,
            before=before,
            after=after,
            since=None if since is None else models.db_second(since),
            until=None if until is None else models.db_second(until, after=True),
        )
        items, earlier = state.message_page(name, where, limit)
        return MessagePage(items=[models.message_info(m) for m in items], earlier=earlier)

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

    @app.get("/api/sessions/{name}/runs", dependencies=[Depends(guard)])
    def flow_runs(name: str, has_db: bool = Depends(database)) -> list[RunInfo]:
        """The session's flow runs, open and closed, newest first."""
        known(name, has_db)
        return [models.run_info(r) for r in reversed(state.list_runs(name))]

    @app.get("/api/sessions/{name}/notes", dependencies=[Depends(guard)])
    def notes(name: str, has_db: bool = Depends(database)) -> list[NoteInfo]:
        """The notes of the session's flow runs, oldest first: each is a step a run took."""
        known(name, has_db)
        return [models.note_info(n) for n in state.run_notes(name)]

    @app.post(
        "/api/sessions",
        dependencies=[Depends(guard.changes), Depends(database)],
        responses={400: {"model": Refused}, 409: {"model": Taken}},
    )
    def start(given: Launch) -> Started:
        """Start a new session, as `lado start` does, without attaching to it. A name a
        session has is 409 with that session's status and folder; on an empty LADO_HOME
        the core makes lado.db."""
        if given.where.kind != "folder":
            raise HTTPException(400, f'where of kind "{given.where.kind}" is not supported yet')
        try:
            done = runtime.start_session(
                launch.full_path(given.where.path),
                given.name,
                given.permission_mode,
                given.provider,
                given.kits,
                given.without,
                resume=False,
            )
        except runtime.SessionExists as taken:
            detail = Taken(message=str(taken), status=taken.status, repo=taken.repo)
            raise HTTPException(409, detail.model_dump(mode="json")) from taken
        except kits.KitError as refused:
            raise _kits_refused(refused) from refused
        except runtime.LadoError as refused:
            raise HTTPException(400, str(refused)) from refused
        return models.started(done)

    @app.post(
        "/api/sessions/{name}/resume",
        dependencies=[Depends(guard.changes)],
        responses={400: {"model": Refused}},
    )
    def resume(name: str, given: Resume, has_db: bool = Depends(database)) -> Started:
        """Start a stopped session again, in its folder; the settings given replace its
        stored ones, and the answer says what changed and which open runs cannot go on."""
        known(name, has_db)
        sess = state.get_session(name)
        assert sess is not None
        try:
            done = runtime.start_session(
                sess.repo,
                name,
                given.permission_mode,
                given.provider,
                given.kits,
                given.without,
                resume=True,
            )
        except runtime.NoSuchSession as gone:
            raise HTTPException(404, str(gone)) from gone
        except kits.KitError as refused:
            raise _kits_refused(refused) from refused
        except runtime.LadoError as refused:
            raise HTTPException(400, str(refused)) from refused
        return models.started(done)

    @app.get("/api/sessions/{name}/stop-preview", dependencies=[Depends(guard)])
    def stop_preview(name: str, has_db: bool = Depends(database)) -> StopPreview:
        """What stopping the session would do now; changes nothing."""
        known(name, has_db)
        preview = core(runtime.stop_preview, name)
        return StopPreview(
            agents=preview.agents,
            dropped=preview.dropped,
            open_runs=preview.open_runs,
            worktrees=models.worktrees(preview.worktrees),
        )

    @app.post("/api/sessions/{name}/stop", dependencies=[Depends(guard.changes)])
    def stop(name: str, has_db: bool = Depends(database)) -> Stopped:
        """Stop the session, as `lado stop` does: its history, runs and worktrees stay."""
        known(name, has_db)
        return Stopped(dropped=core(runtime.stop_session, name).dropped)

    @app.get("/api/sessions/{name}/forget-preview", dependencies=[Depends(guard)])
    def forget_preview(name: str, has_db: bool = Depends(database)) -> ForgetPreview:
        """What forgetting the stopped session would drop and leave on disk."""
        known(name, has_db)
        preview = core(runtime.forget_preview, name)
        return ForgetPreview(open_runs=preview.runs, worktrees=models.worktrees(preview.worktrees))

    @app.delete("/api/sessions/{name}", dependencies=[Depends(guard.changes)])
    def forget(name: str, force: bool = False, has_db: bool = Depends(database)) -> Forgotten:
        """Forget the stopped session with its history, as `lado forget` does; with open
        runs only with `force`. Worktrees and branches stay on disk."""
        known(name, has_db)
        done = core(runtime.forget_session, name, force)
        return Forgotten(open_runs=done.runs, worktrees=models.worktrees(done.worktrees))

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
