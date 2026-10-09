"""The UI server's FastAPI app: the API under /api, the web UI's bundle on /.

Its OpenAPI schema is the one contract with the UI (web/openapi.json, from which the UI's
TypeScript types are made). Data comes only through lado.state and lado.runtime; the server
never migrates the database: another schema version answers 503.
"""

import datetime
import ipaddress
import re
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Literal, TypeVar

import uvicorn
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, WebSocket
from fastapi.responses import (
    FileResponse,
    JSONResponse,
    PlainTextResponse,
    Response,
    StreamingResponse,
)
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

import lado
from lado import (
    artifacts,
    doctor,
    kits,
    marketplaces,
    runs,
    runtime,
    self_update,
    state,
    terminal,
    update,
)
from lado.server import feed, launch, models, terminals
from lado.server.auth import Guard
from lado.server.models import (
    AgentDetails,
    AgentInfo,
    Answer,
    ArtifactInfo,
    Finish,
    FinishPreviewInfo,
    FolderInfo,
    ForgetPreview,
    Forgotten,
    GateAnswer,
    GateInfo,
    InstalledKitInfo,
    InstallKit,
    KitFactInfo,
    KitInfo,
    KitUsersInfo,
    Launch,
    Limits,
    MarketplaceChange,
    MarketplaceInfo,
    MarketplaceUpdate,
    MarketplaceUpdateAsk,
    MessagePage,
    MessageText,
    NewMarketplace,
    NoteInfo,
    OfferInfo,
    OutdatedInfo,
    PlanAsk,
    PlanInfo,
    PlanUpdateAsk,
    ProviderInfo,
    RecentFolder,
    RecordView,
    Refused,
    Resume,
    RunEventInfo,
    RunInfo,
    Sent,
    SessionAbout,
    SessionCounts,
    SessionInfo,
    Started,
    Stopped,
    StopPreview,
    SystemInfo,
    Taken,
    TmuxInfo,
    UpdateAsk,
    UpdateInfo,
    UpdateKit,
    UpdatePlan,
    UpdateStarted,
    WaitingItem,
)

T = TypeVar("T")
STATIC = Path(__file__).parent / "static"  # the built bundle (make web); not in git
BUILD_HINT = "build it with `make web` in a LADO checkout"


class Health(BaseModel):
    ok: bool
    version: str
    started_at: str  # when this server started: a restart shows, also of the same version


def database() -> bool:
    """A dependency of every endpoint that reads lado.db: whether there is one, so a read
    makes none; another schema is a 503 with its reason. The server never migrates it:
    state.connect refuses another schema itself (`another_schema`, also a 503), so this
    check only gives the reason early."""
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
    except (runtime.LadoError, artifacts.ArtifactError) as refused:
        raise HTTPException(400, str(refused)) from refused


def too_large() -> HTTPException:
    return HTTPException(413, f"the file is over the limit of {artifacts.MAX_SIZE} bytes")


def stored(name: str, file_name: str, data: bytes, has_db: bool) -> ArtifactInfo:
    """The human's upload through the core, as the artifact with its record."""
    known(name, has_db)
    written = core(artifacts.upload, name, file_name, data)
    return models.artifact_info(written.artifact, written.record)


def _kits_refused(refused: kits.KitError) -> HTTPException:
    """A start or resume the session's kits refuse: 400 with Refused."""
    detail = Refused(message=str(refused), switch_off=refused.switch_off)
    return HTTPException(400, detail.model_dump(mode="json"))


def kits_core(action: Callable[..., T], *args) -> T:
    """Do what the human asked of kits or marketplaces through the core; what it refuses
    is 400 with Refused and its reason."""
    try:
        return action(*args)
    except kits.KitError as refused:
        raise _kits_refused(refused) from refused
    except marketplaces.MarketplaceError as refused:
        detail = Refused(message=str(refused), switch_off=[])
        raise HTTPException(400, detail.model_dump(mode="json")) from refused


def changed_since_plan(what: str) -> HTTPException:
    return HTTPException(409, f"the kit changed since the plan: {what}; look at its plan again")


def installed_kits_list(has_db: bool) -> list[InstalledKitInfo]:
    """The installed kits, then the built-in ones. Without lado.db only the built-in ones."""
    found = [*(kits.installed_kits() if has_db else []), *kits.builtin_kits()]
    return [models.installed_kit_info(one) for one in found]


def installed_one(name: str) -> InstalledKitInfo:
    found = kits.installed_kit(name)
    if found is None:
        raise HTTPException(404, f'no kit "{name}" is installed')
    return models.installed_kit_info(found)


def install_planned(given: InstallKit) -> InstalledKitInfo:
    """Install what the plan showed: the same commit (git) or MCP servers (a folder)."""
    plan = kits.plan_add(given.spec, given.marketplace)
    if plan.tag is not None and given.commit != plan.commit:
        raise changed_since_plan(f"{plan.tag} is at {plan.commit}, the plan had {given.commit}")
    if plan.tag is None and sorted(given.mcp or []) != sorted(plan.mcp):
        servers = ", ".join(sorted(plan.mcp)) or "none"
        raise changed_since_plan(f"its MCP servers are now: {servers}")
    kits.install(plan)
    return installed_one(plan.name)


def update_planned(name: str, given: UpdateKit) -> InstalledKitInfo:
    plan = kits.plan_update(name, given.tag)
    if plan.commit != given.commit:
        raise changed_since_plan(f"{plan.tag} is at {plan.commit}, the plan had {given.commit}")
    if not plan.current:
        kits.install(plan)
    return installed_one(name)


def marketplace_list(has_db: bool) -> list[MarketplaceInfo]:
    markets = marketplaces.list_() if has_db else [marketplaces.UNMADE_OFFICIAL]
    return [models.marketplace_info(m) for m in markets]


def marketplace_updates(name: str | None) -> list[MarketplaceUpdate]:
    """Each marketplace's update, one that fails with its error (marketplaces.update_each)."""
    updates = []
    for market, done in marketplaces.update_each([name] if name else None):
        if isinstance(done, str):
            updates.append(MarketplaceUpdate(name=market, marketplace=None, error=done))
        else:
            info = models.marketplace_info(done)
            updates.append(MarketplaceUpdate(name=market, marketplace=info, error=None))
    return updates


# The media types whose content is shown inline (in a tab of its own, an <img>, a frame);
# any other is a download: the media type is the agent's word (docs/design/artifacts.md,
# The human's side). Raster images and SVG, under the same sandbox as the rest.
INLINE = frozenset(
    {
        "text/plain",
        "text/markdown",
        "text/html",
        "image/png",
        "image/jpeg",
        "image/gif",
        "image/webp",
        "image/svg+xml",
    }
)
# A record never changes: its content is cached for good, but only as the answer it is.
CACHED = "private, max-age=31536000, immutable"
UNSAFE_IN_FILE_NAME = re.compile(r'[/\\"\x00-\x1f\x7f]')


def _content_headers(media_type: str, name: str, download: bool) -> dict[str, str]:
    """The headers of every answer with an artifact's content: a sandbox (an opaque origin,
    so its scripts never act as the human; scripts only for HTML), no sniffing, and inline
    only for INLINE types unless `download`, with the artifact's name as the file's."""
    file_name = UNSAFE_IN_FILE_NAME.sub("_", artifacts.file_name(name, media_type))
    inline = media_type in INLINE and not download
    return {
        "Content-Security-Policy": "sandbox allow-scripts"
        if media_type == "text/html"
        else "sandbox",
        "X-Content-Type-Options": "nosniff",
        "Content-Disposition": f'{"inline" if inline else "attachment"}; filename="{file_name}"',
    }


def _content_type(media_type: str) -> str:
    return f"{media_type}; charset=utf-8" if media_type.startswith("text/") else media_type


def bundle_missing(static: Path) -> bool:
    return not (static / "index.html").is_file()


def contract() -> dict:
    """The API's OpenAPI schema as web/openapi.json keeps it (`make web-types`): without
    LADO's version, so a release does not change it."""
    schema = create_app("", 0).openapi()
    del schema["info"]["version"]
    return schema


def update_state(checked: update.Check | None) -> UpdateInfo:
    installer = update.installer()
    refused = self_update.refusal(installer)
    available = checked.available if checked else None
    by_hand = []
    if available and refused and refused.kind == self_update.NO_INSTALLER:
        release = update.Release(available, checked.released or "")
        by_hand = self_update.plan(release).by_hand()
    return UpdateInfo(
        current=lado.__version__,
        latest=checked.latest if checked else None,
        available=available,
        released=checked.released if checked else None,
        checked_at=checked.checked_at if checked else None,
        error=checked.error if checked else None,
        running=self_update.running_pid() is not None,
        can_update=refused is None,
        why_not=refused.why if refused else None,
        by_hand=by_hand,
        last=models.update_result_info(update.read_result()),
    )


def latest_plan() -> self_update.Plan:
    """The plan for the latest LADO; 409 when none is newer, 502 when PyPI cannot be read."""
    try:
        plan = self_update.latest_plan()
    except (OSError, ValueError) as exc:
        raise HTTPException(502, f"cannot look up LADO's versions on PyPI: {exc}") from exc
    if plan is None:
        raise HTTPException(409, f"LADO {lado.__version__} is the latest version")
    return plan


def create_app(token: str, port: int, static: Path = STATIC, host: str = "127.0.0.1") -> FastAPI:
    guard = Guard(token, port)
    hub = feed.Hub(feed.Journal())
    app = FastAPI(title="LADO", version=lado.__version__)
    # Kept in memory only: /api/health tells a restarted server, also of the same version.
    started = datetime.datetime.now(datetime.timezone.utc)
    started_at = started.isoformat(timespec="milliseconds")
    open_to_network = not ipaddress.ip_address(host).is_loopback

    @app.exception_handler(state.SchemaError)
    def another_schema(request: Request, error: state.SchemaError) -> JSONResponse:
        """lado.db changed its schema after `database` checked it: state.connect refused it
        and changed nothing. The same 503 as the check's."""
        return JSONResponse({"detail": str(error)}, status_code=503)

    @app.get("/api/health")
    def health() -> Health:
        return Health(ok=True, version=lado.__version__, started_at=started_at)

    @app.get("/api/update", dependencies=[Depends(guard)])
    def update_info() -> UpdateInfo:
        """Whether a newer LADO is out, whether this one can update itself now, and the
        latest update's result. A plain `def`: FastAPI runs it in a worker thread, so the
        check's look at PyPI (once a day) holds up no other request."""
        return update_state(update.check())

    @app.post("/api/update/check", dependencies=[Depends(guard.changes)])
    def check_update() -> UpdateInfo:
        """The update check now, past the day's cache: it goes to the network."""
        return update_state(update.check(force=True))

    @app.get("/api/update/plan", dependencies=[Depends(guard)], responses={409: {"model": Refused}})
    def update_plan() -> UpdatePlan:
        """What an update to the latest LADO would do, as `lado update` prints it; 409 when
        no version is newer. A plain `def`: its look at PyPI runs in a worker thread."""
        return models.update_plan(latest_plan())

    @app.post("/api/update", status_code=202, dependencies=[Depends(guard.changes)])
    def start_update(given: UpdateAsk) -> UpdateStarted:
        """Start `lado update --yes <to>` as a process of its own, which stops this server
        within seconds; 409 when `to` is not the plan's version or this LADO cannot update
        itself now (an update runs, no installer). Its result carries the id answered."""
        plan = latest_plan()
        if plan.to.version != given.to:
            raise HTTPException(
                409, f"LADO {plan.to.version} is the version to update to, not {given.to}"
            )
        refused = self_update.refusal(plan.installer)
        if refused:
            raise HTTPException(409, refused.why)
        id = uuid.uuid4().hex
        requested = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
        self_update.start_detached(given.to, id)
        return UpdateStarted(id=id, requested_at=requested, log=str(self_update.log_path()))

    @app.get("/api/system", dependencies=[Depends(guard)])
    def system() -> SystemInfo:
        """The system panel: this LADO, the machine, the providers and kits, and the report
        to copy into an issue (doctor.system_info, doctor.report)."""
        facts = doctor.system_info()
        up = (datetime.datetime.now(datetime.timezone.utc) - started).total_seconds()
        return SystemInfo(
            version=facts.version,
            python=facts.python,
            os=facts.os,
            machine=facts.machine,
            installer=facts.installer,
            started_at=started_at,
            open_to_network=open_to_network,
            home=facts.home,
            home_set=facts.home_set,
            schema_=facts.schema,
            tmux=TmuxInfo(version=facts.tmux, socket=facts.tmux_socket),
            gui_session=models.gui_session_info(facts.gui_session),
            providers=[launch.provider_info(p, status) for p, status in facts.providers],
            kits=[KitFactInfo(name=k.name, version=k.version, origin=k.origin) for k in facts.kits],
            sessions=SessionCounts(**facts.sessions),
            last=models.update_result_info(facts.last),
            report=doctor.report(facts, open_to_network, up),
        )

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
    def list_kits(where: str | None = None, has_db: bool = Depends(database)) -> list[KitInfo]:
        """The kits a session of the folder `where` can take, one per name."""
        return core(launch.kit_infos, where, has_db)

    @app.get("/api/providers", dependencies=[Depends(guard)])
    def list_providers() -> list[ProviderInfo]:
        """LADO's providers and whether each one's CLI can run here, checked anew."""
        return launch.provider_infos()

    # The Kits page (docs/design/ui.md, Kits): what `lado kits` and `lado marketplaces` do.
    # A request that goes to the network or writes the git cache is a change too.

    refused = {400: {"model": Refused}}

    @app.get("/api/kits/installed", dependencies=[Depends(guard)])
    def installed_kits(has_db: bool = Depends(database)) -> list[InstalledKitInfo]:
        """The installed kits and the built-in ones, each as it loads now."""
        return installed_kits_list(has_db)

    @app.get("/api/kits/available", dependencies=[Depends(guard)])
    def available_kits(has_db: bool = Depends(database)) -> list[OfferInfo]:
        """The kits the enabled marketplaces list, from their clones (no network)."""
        if not has_db:
            return []
        installed = {row.name for row in state.list_kits()}
        return [models.offer_info(offer, installed) for offer in marketplaces.available()]

    @app.get("/api/kits/{name}/remove-preview", dependencies=[Depends(guard)])
    def remove_kit_preview(name: str, has_db: bool = Depends(database)) -> KitUsersInfo:
        """The sessions that use the installed kit, which removing it touches."""
        if not has_db or state.get_kit(name) is None:
            raise HTTPException(404, f'no kit "{name}" is installed')
        return models.kit_users_info(name, runtime.kit_users(name))

    @app.post(
        "/api/kits/plan",
        dependencies=[Depends(guard.changes), Depends(database)],
        responses=refused,
    )
    def plan_kit(given: PlanAsk) -> PlanInfo:
        """What `lado kits add` would do: the kit cloned into the cache, nothing installed."""
        return models.plan_info(kits_core(kits.plan_add, given.spec, given.marketplace, given.pre))

    @app.post(
        "/api/kits/install",
        dependencies=[Depends(guard.changes), Depends(database)],
        responses={**refused, 409: {"description": "the kit changed since the plan"}},
    )
    def install_kit(given: InstallKit) -> InstalledKitInfo:
        """Install the kit of a plan; 409 when it is no longer what the plan showed."""
        return kits_core(install_planned, given)

    @app.post(
        "/api/kits/{name}/plan-update",
        dependencies=[Depends(guard.changes), Depends(database)],
        responses=refused,
    )
    def plan_kit_update(name: str, given: PlanUpdateAsk) -> PlanInfo:
        """What `lado kits update` would do, with the sessions that use the kit."""
        plan = kits_core(kits.plan_update, name, given.tag, given.pre)
        return models.plan_info(plan, runtime.kit_users(name))

    @app.post(
        "/api/kits/{name}/update",
        dependencies=[Depends(guard.changes), Depends(database)],
        responses={**refused, 409: {"description": "the kit changed since the plan"}},
    )
    def update_kit(name: str, given: UpdateKit) -> InstalledKitInfo:
        """Move the kit to the plan's tag; 409 when the tag moved since."""
        return kits_core(update_planned, name, given)

    @app.delete(
        "/api/kits/{name}",
        status_code=204,
        dependencies=[Depends(guard.changes), Depends(database)],
        responses=refused,
    )
    def remove_kit(name: str) -> None:
        """Forget the installed kit, as `lado kits remove` does; its files stay."""
        kits_core(kits.remove, name)

    @app.post("/api/kits/check-updates", dependencies=[Depends(guard.changes), Depends(database)])
    def check_updates() -> list[OutdatedInfo]:
        """Each installed kit against its repository's tags now (the network)."""
        return [models.outdated_info(row) for row in kits.outdated()]

    @app.get("/api/marketplaces", dependencies=[Depends(guard)])
    def list_marketplaces(has_db: bool = Depends(database)) -> list[MarketplaceInfo]:
        """The kit marketplaces and what their clones say (no network)."""
        return marketplace_list(has_db)

    @app.post(
        "/api/marketplaces",
        dependencies=[Depends(guard.changes), Depends(database)],
        responses=refused,
    )
    def add_marketplace(given: NewMarketplace) -> MarketplaceInfo:
        """Add a marketplace: its clone made and its list read first."""
        return models.marketplace_info(kits_core(marketplaces.add, given.name, given.url))

    @app.patch(
        "/api/marketplaces/{name}",
        dependencies=[Depends(guard.changes), Depends(database)],
        responses=refused,
    )
    def change_marketplace(name: str, given: MarketplaceChange) -> MarketplaceInfo:
        """Enable or disable a marketplace."""
        return models.marketplace_info(kits_core(marketplaces.set_enabled, name, given.enabled))

    @app.delete(
        "/api/marketplaces/{name}",
        status_code=204,
        dependencies=[Depends(guard.changes), Depends(database)],
        responses=refused,
    )
    def remove_marketplace(name: str) -> None:
        """Remove a marketplace (never the official one); its installed kits stay."""
        kits_core(marketplaces.remove, name)

    @app.post("/api/marketplaces/update", dependencies=[Depends(guard.changes), Depends(database)])
    def update_marketplaces(given: MarketplaceUpdateAsk) -> list[MarketplaceUpdate]:
        """Bring a marketplace's clone, or each enabled one's, up to date (the network); one
        that fails does not stop the others."""
        return marketplace_updates(given.name)

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

    @app.get("/api/sessions/{name}/about", dependencies=[Depends(guard)])
    def session_about(name: str, has_db: bool = Depends(database)) -> SessionAbout:
        """What the session's head shows besides its settings: its repository's remote and
        branch, its kits' and provider's versions as installed now. Read anew each time."""
        known(name, has_db)
        return launch.session_about(state.get_session(name))

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

    @app.get("/api/sessions/{name}/artifacts", dependencies=[Depends(guard)])
    def session_artifacts(name: str, has_db: bool = Depends(database)) -> list[ArtifactInfo]:
        """The session's artifacts, each as of its latest record."""
        known(name, has_db)
        return [models.artifact_info(*found) for found in artifacts.of_session(name)]

    @app.post(
        "/api/sessions/{name}/artifacts",
        dependencies=[Depends(guard.changes)],
        openapi_extra={
            "requestBody": {
                "required": True,
                "content": {"application/octet-stream": {"schema": {"type": "string"}}},
            }
        },
    )
    async def upload(
        name: str, file_name: str, request: Request, has_db: bool = Depends(database)
    ) -> ArtifactInfo:
        """The human's file, its bytes as the body: an artifact of the session's scope
        (lado.artifacts.upload), for a message to attach. Over the size limit 413, having
        read no more than the limit and one chunk."""
        length = request.headers.get("content-length", "")
        if length.isdigit() and int(length) > artifacts.MAX_SIZE:
            raise too_large()
        data = bytearray()
        async for chunk in request.stream():
            data += chunk
            if len(data) > artifacts.MAX_SIZE:
                raise too_large()
        return await run_in_threadpool(stored, name, file_name, bytes(data), has_db)

    @app.get("/api/limits", dependencies=[Depends(guard)])
    def limits() -> Limits:
        """What the composer checks before an upload, and which files an agent reads."""
        return Limits(
            extensions=artifacts.EXTENSIONS,
            text_types=list(artifacts.TEXT_TYPES),
            agent_images=list(artifacts.AGENT_IMAGES),
            max_size=artifacts.MAX_SIZE,
            max_files=artifacts.MAX_HUMAN_FILES,
            image_limit=artifacts.IMAGE_LIMIT,
            image_max_side=artifacts.IMAGE_MAX_SIDE,
            max_message=runtime.MAX_MESSAGE,
        )

    @app.get("/api/sessions/{name}/artifacts/{artifact}", dependencies=[Depends(guard)])
    def one_artifact(name: str, artifact: str, has_db: bool = Depends(database)) -> ArtifactInfo:
        """One artifact of the session with its latest record."""
        known(name, has_db)
        found = artifacts.of_artifact(name, artifact)
        if found is None:
            raise HTTPException(404, f"no artifact {artifact} in session {name}")
        return models.artifact_info(*found)

    def known_record(name: str, record: str, has_db: bool) -> tuple:
        known(name, has_db)
        found = artifacts.of_record(name, record)
        if found is None:
            raise HTTPException(404, f"no record {record} in session {name}")
        return found

    @app.get("/api/sessions/{name}/records/{record}", dependencies=[Depends(guard)])
    def one_record(name: str, record: str, has_db: bool = Depends(database)) -> RecordView:
        """A record of the session's artifacts, with its artifact as it is now."""
        artifact, found = known_record(name, record, has_db)
        latest = artifacts.of_artifact(name, artifact.id)
        assert latest is not None, "a record's artifact is there"
        return RecordView(artifact=models.artifact_info(*latest), record=models.record_info(found))

    @app.get(
        "/api/sessions/{name}/records/{record}/content",
        dependencies=[Depends(guard)],
        response_class=Response,
        responses={200: {"content": {"application/octet-stream": {}}}},
    )
    def record_content(
        name: str, record: str, download: bool = False, has_db: bool = Depends(database)
    ) -> Response:
        """A record's content, with the headers of _content_headers; `download` makes it a
        download whatever its type."""
        artifact, found = known_record(name, record, has_db)
        headers = _content_headers(found.media_type, artifact.name, download)
        try:
            data = artifacts.content(found)
        except artifacts.ArtifactError as missing:
            failed = {"X-Content-Type-Options": "nosniff", "Cache-Control": "no-store"}
            raise HTTPException(500, str(missing), headers=failed) from missing
        return Response(
            data,
            media_type=_content_type(found.media_type),
            headers={**headers, "Cache-Control": CACHED},
        )

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
        """The human's text to an agent of the session (default: the supervisor), with the
        files uploaded for it, through the same queue and delivery as an agent's message."""
        known(name, has_db)
        return Sent(
            result=core(runtime.write_as_human, name, message.text, message.to, message.artifacts)
        )

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

    app.state.hub = hub
    return app


class Server(uvicorn.Server):
    """uvicorn's server for an app of `create_app`: its shutdown ends the event streams
    first. uvicorn waits for open responses before the app's lifespan shutdown, so that
    would come too late."""

    async def shutdown(self, sockets=None) -> None:
        self.config.app.state.hub.close()
        await super().shutdown(sockets)


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
