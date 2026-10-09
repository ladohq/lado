"""The API's models, and each one built from the state: one form of an entity for the REST
API and for the event stream's items (lado.server.feed)."""

import dataclasses
import datetime
import logging
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from lado import (
    artifacts,
    flows,
    gitcache,
    kits,
    marketplaces,
    runs,
    runtime,
    self_update,
    state,
    update,
)

log = logging.getLogger("lado.server")


class Waiting(BaseModel):
    """What in a session not stopped waits for the human, counted: the items of
    /api/waiting (state.waiting_items). A stopped session has none."""

    gates: int  # open gates of its runs
    questions: int  # open questions of its agents (ask_human)
    agents: int  # agents in `waiting`


class SessionInfo(BaseModel):
    name: str
    repo: str
    status: runtime.SessionStatus
    agents: int  # agents the session has now
    waiting: Waiting
    # Whether something moves in it (state.session_activity), only while it runs, else 0
    # and None: its agents in `busy` or `starting`, and since when it works (some busy) or
    # stands still (none) (UTC, ISO 8601); the UI adds the time since.
    busy: int
    activity_since: str | None
    # Its settings, as the next resume takes them unless given anew.
    kits: list[str]
    provider: str
    permission_mode: str | None
    without: list[str]  # "agent:x", "skill:y", "mcp:z", "flow:w"
    # How long it ran (runtime.session_time): its closed spans, and the start of the one it
    # runs in now (UTC, ISO 8601), None unless it runs; the UI adds the time since.
    ran_seconds: int
    running_since: str | None
    stopped_at: str | None  # UTC, ISO 8601: when it was stopped; None unless stopped


class Where(BaseModel):
    """Where a session runs: now only a folder (a full path, `~` allowed)."""

    kind: str  # "folder"; another kind is refused for now
    path: str


NameState = Literal["free", "running", "stopped_here", "taken_elsewhere"]


class FolderInfo(BaseModel):
    """A folder as the New session window checks it."""

    path: str  # as given, `~` expanded
    ok: bool  # a session can start here
    problem: str | None  # why not, as the core says it (runtime.check_repo)
    root: str | None  # its git repository's root
    branch: str | None  # the repository's current branch
    has_commits: bool
    subfolders: list[str]  # its folders' names, no hidden ones, at most SUBFOLDERS
    default_name: str | None  # the name a session started here gets
    # free; running: a session of that name runs; stopped_here: one of this folder can be
    # resumed; taken_elsewhere: a session of another folder has it
    name_state: NameState | None
    # the provider a new session here takes (runtime.suggested_provider); none: the human picks
    provider: "ProviderSuggestion | None"


class ProviderSuggestion(BaseModel):
    name: str
    # last_session: the folder's last session's; only_installed: the one CLI installed
    reason: Literal["last_session", "only_installed"]


class RecentFolder(BaseModel):
    path: str
    session: SessionInfo  # its latest started session


class KitSummary(BaseModel):
    """A kit as it loads now: what every list of kits shows of it."""

    name: str
    version: str
    description: str
    valid: bool
    problem: str | None  # why it is not valid


class KitInfo(KitSummary):
    """A kit a session of a folder can take: the one of each name that wins the lookup."""


KitKind = Literal["git", "folder", "built-in"]


class InstalledKitInfo(KitSummary):
    """An installed kit (its row in lado.db, its files) or a built-in one: the Kits page's
    Installed list and the `kits` items of the change feed."""

    kind: KitKind
    address: str | None  # from git
    tag: str | None
    commit: str | None
    folder: str | None  # a folder kit's
    marketplace: str | None  # the marketplace it was added from, removed since or not
    installed_at: str | None
    updated_at: str | None
    agents: int
    skills: int
    flows: int
    mcp: list[str]  # the MCP servers its agents start
    missing: bool  # its folder (a folder kit's, or a git kit's clone) is gone


class IndexEntryInfo(BaseModel):
    """A kit as its marketplace's index.json describes it (marketplaces.IndexEntry)."""

    address: str
    latest: str | None
    commit: str | None
    lado: str | None
    description: str | None
    agents: dict[str, str] | None
    skills: list[str] | None
    flows: list[str] | None
    mcp: dict[str, str] | None


class OfferInfo(BaseModel):
    """A kit an enabled marketplace lists (the Available list)."""

    name: str
    marketplace: str
    address: str
    installed: bool  # a kit of that name is installed
    index: IndexEntryInfo | None  # None without an index.json entry


class McpInfo(BaseModel):
    name: str
    command: str  # one line


class KitUsersInfo(BaseModel):
    """The sessions that use an installed kit (runtime.kit_users), and what the core says of
    them."""

    running: list[str]
    stopped: list[str]
    running_line: str | None
    stopped_line: str | None


class KitContentsInfo(BaseModel):
    """What a version of a kit holds, by name: an update plan's installed version."""

    agents: list[str]
    skills: list[str]  # its own and its packs'
    flows: list[str]
    mcp: list[str]


class PlanInfo(BaseModel):
    """What an add or update would do (kits.Install), as the CLI shows it before it asks."""

    name: str
    version: str
    description: str
    spec: str  # what an install gives for this plan: its tag pinned
    address: str  # the git address, or the folder
    tag: str | None  # None for a folder
    commit: str | None
    source: str  # "official", "marketplace <name>", "git" or "folder"
    marketplace: str | None
    installed: str | None  # an update's: the tag installed now
    needs_confirmation: bool  # the human must confirm (not official, or a folder)
    current: bool  # an update to the installed version: nothing to do
    versions: list[str]  # from git: the tags it could take, newest first
    agents: list[str]
    skills: list[str]
    flows: list[str]
    mcp: list[McpInfo]
    new_mcp: list[str]  # an update's MCP servers the installed version did not start
    warnings: list[str]  # a moved tag, new MCP servers
    notes: list[str]  # what the core says besides: who gets an update, or that it is current
    users: KitUsersInfo | None  # an update's: the sessions that use the kit
    # An update's installed version (kits.Install.before); null for an add, and when that
    # version or one of its packs is not in the cache: what changes is then not known.
    before: KitContentsInfo | None


class PlanAsk(BaseModel):
    spec: str  # a git address[@tag], a folder, or with `marketplace` a kit's name[@tag]
    marketplace: str | None = None
    pre: bool = False


class InstallKit(BaseModel):
    """An install of what a plan showed: its `spec`, and the commit (git) or the MCP servers
    (a folder) the human saw; another one is 409."""

    spec: str
    marketplace: str | None = None
    commit: str | None = None
    mcp: list[str] | None = None


class PlanUpdateAsk(BaseModel):
    tag: str | None = None  # None: the latest
    pre: bool = False


class UpdateKit(BaseModel):
    tag: str
    commit: str  # the plan's; another one is 409


class OutdatedInfo(BaseModel):
    """An installed kit against its repository's tags now (kits.Outdated)."""

    name: str
    installed: str
    latest: str | None
    pre: str | None
    note: str  # why it was not checked; '' when it was
    warnings: list[str]
    newer: str | None  # the latest release when it is above the installed version


class MarketplaceInfo(BaseModel):
    """A kit marketplace: its row in lado.db and what its clone says (the `marketplaces`
    items of the change feed)."""

    name: str
    url: str  # its address; the official one's too
    enabled: bool
    updated_at: str | None
    official: bool
    kits: int | None  # how many it lists; None without a clone
    index: bool  # its clone has index.json
    problem: str | None  # not fetched, a list or index.json LADO cannot read


class NewMarketplace(BaseModel):
    name: str
    url: str


class MarketplaceChange(BaseModel):
    enabled: bool


class MarketplaceUpdateAsk(BaseModel):
    name: str | None = None  # None: each enabled one


class MarketplaceUpdate(BaseModel):
    """One marketplace's update: the marketplace now, or why it failed."""

    name: str
    marketplace: MarketplaceInfo | None
    error: str | None


class ProviderInfo(BaseModel):
    """A provider of LADO's registry and whether its CLI can run here."""

    name: str
    title: str
    permission_modes: list[str]
    install_hint: str
    installed: bool
    version: str
    detail: str  # its `--version` line, or why there is none
    tested_version: str
    warning: str  # "" unless its version is not the tested one


class SessionCommand(BaseModel):
    name: str
    command: str  # the `lado start` that resumes it


class UpdateResultInfo(BaseModel):
    """The latest update's outcome, as update-result.json keeps it (lado.update)."""

    model_config = ConfigDict(populate_by_name=True)

    id: str | None  # the id the server gave the update it started
    outcome: str  # running, ok, partial, failed, rolled_back, rollback_failed; "" unknown
    from_: str = Field(alias="from")
    to: str
    started_at: str
    ended_at: str | None
    sessions_failed: list[SessionCommand]
    reason: str | None
    database: str | None  # kept, restored, or None
    log: str | None
    tail: list[str]
    problem: str | None  # "written by a newer LADO": nothing else is read


def update_result_info(result: update.Result | None) -> UpdateResultInfo | None:
    if result is None:
        return None
    return UpdateResultInfo(
        id=result.id,
        outcome=result.outcome,
        from_=result.from_,
        to=result.to,
        started_at=result.started_at,
        ended_at=result.ended_at,
        sessions_failed=[SessionCommand(**one) for one in result.sessions_failed],
        reason=result.reason,
        database=result.database,
        log=result.log,
        tail=result.tail,
        problem=result.problem,
    )


class UpdateInfo(BaseModel):
    """This LADO's version, what the update check found (lado.update.check), whether this
    LADO can update itself now (self_update.refusal) and the latest update's result."""

    current: str
    latest: str | None  # the latest release; None before a look found one or with the check off
    available: str | None  # the latest release when it is newer than this LADO
    released: str | None  # the latest release's day, YYYY-MM-DD
    checked_at: str | None  # when the check last looked; None with the check off
    error: str | None  # why the latest look failed
    running: bool  # an update holds its lock
    can_update: bool
    why_not: str | None  # why it cannot
    by_hand: list[str]  # without an installer: the commands that update to `available`
    last: UpdateResultInfo | None


class PlanAgent(BaseModel):
    name: str
    status: str


class PlanSession(BaseModel):
    name: str
    repo: str
    agents: list[PlanAgent]
    open_runs: int


class UpdatePlan(BaseModel):
    """What an update would do, as `lado update` prints it (self_update.plan)."""

    model_config = ConfigDict(populate_by_name=True)

    from_: str = Field(alias="from")
    to: str
    released: str
    installer: str | None  # its kind; None: only by hand
    command: str | None  # the installer's command
    lost: list[str]  # what that command does not keep of the install
    downgrade: bool  # an older LADO may refuse lado.db
    sessions: list[PlanSession]  # restarted
    gone: list[SessionCommand]  # not stopped, their tmux gone: not restarted
    server: str | None  # the UI server's url, restarted
    socket: str  # the tmux socket whose sessions are seen
    by_hand: list[str]


def update_plan(plan: self_update.Plan) -> UpdatePlan:
    installer = plan.installer
    return UpdatePlan(
        from_=plan.current,
        to=plan.to.version,
        released=plan.to.date,
        installer=installer.kind if installer else None,
        command=plan.command,
        lost=list(installer.lost) if installer else [],
        downgrade=plan.downgrade,
        sessions=[
            PlanSession(
                name=sess.name,
                repo=sess.repo,
                agents=[
                    PlanAgent(name=a.name, status=a.status) for a in state.list_agents(sess.name)
                ],
                open_runs=self_update.open_runs(sess.name),
            )
            for sess in plan.sessions
        ],
        gone=[
            SessionCommand(name=s.name, command=f"lado start {s.repo} --name {s.name}")
            for s in plan.gone
        ],
        server=plan.server["url"] if plan.server else None,
        socket=plan.socket,
        by_hand=plan.by_hand(),
    )


class UpdateAsk(BaseModel):
    to: str  # the plan's version


class UpdateStarted(BaseModel):
    id: str  # the result of this update carries it
    requested_at: str


class TmuxInfo(BaseModel):
    version: str  # or why there is none
    socket: str


class KitFactInfo(BaseModel):
    name: str
    version: str
    origin: str  # built-in, "<name> marketplace", git or folder


class SessionCounts(BaseModel):
    running: int
    stopped: int
    gone: int


class SystemInfo(BaseModel):
    """The system panel's facts (doctor.system_info) and the server's own."""

    version: str
    python: str
    os: str
    machine: str
    installer: str | None  # its kind, None without one (UpdateInfo.why_not says why)
    started_at: str  # the server's start
    open_to_network: bool  # it listens beyond loopback
    home: str
    home_set: bool  # LADO_HOME is set
    schema_: int | None = Field(alias="schema")
    tmux: TmuxInfo
    providers: list[ProviderInfo]
    kits: list[KitFactInfo]
    sessions: SessionCounts
    last: UpdateResultInfo | None
    report: str  # Markdown for an issue: no address, path, session name or token

    model_config = ConfigDict(populate_by_name=True)


class RepoInfo(BaseModel):
    """A repository of a session: now its one folder; a project will have several."""

    path: str
    remote: str | None  # origin's URL through runtime.public_remote; None without one
    branch: str | None  # None on a detached HEAD, or with the folder gone


class SessionKitInfo(BaseModel):
    """A kit of a session as the next agent would take it now (kits.find in its repo)."""

    name: str
    version: str  # "" unless valid
    source: str  # where it is, as `lado kits` says it; "" when it is not found
    valid: bool
    problem: str | None  # why it is not found or does not load


class SessionAbout(BaseModel):
    """What the session's head shows besides its settings: read from git, the kits and
    the provider's CLI when asked, never in the change feed (docs/design/ui.md, Session
    head)."""

    repos: list[RepoInfo]
    kits: list[SessionKitInfo]
    provider: ProviderInfo


class Launch(BaseModel):
    """A new session, as `lado start` takes it."""

    where: Where
    name: str | None = None
    kits: list[str] | None = None
    provider: str | None = None
    permission_mode: str | None = None
    without: list[str] | None = None


class Resume(BaseModel):
    """A stopped session started again; what is given replaces its stored settings."""

    kits: list[str] | None = None
    provider: str | None = None
    permission_mode: str | None = None
    without: list[str] | None = None


class Taken(BaseModel):
    """The detail of a 409 to a new session: the session that has the name."""

    message: str
    status: runtime.SessionStatus
    repo: str


class Refused(BaseModel):
    """The detail of a 400 to a start or resume that the session's kits refuse: why, and
    the --without items that would each resolve it (a name in two kits), if any."""

    message: str
    switch_off: list[str]


class Started(BaseModel):
    session: SessionInfo
    resumed: bool
    changes: list[str]  # the settings a resume replaced
    problems: list[str]  # open runs that cannot go on as they are
    lead: str  # who leads the session, as `lado start` prints it
    # What `lado start` prints as warnings: the kits' supervisors not used, what holds the
    # supervisor before its first hook (e.g. a question of its CLI for the human).
    warnings: list[str]


class Worktree(BaseModel):
    path: str
    branch: str


class StopPreview(BaseModel):
    agents: list[str]  # the agents a stop closes
    dropped: int  # messages no agent got, dropped by a stop now
    open_runs: list[str]  # they stay
    worktrees: list[Worktree]  # they stay on disk


class Stopped(BaseModel):
    dropped: int


class ForgetPreview(BaseModel):
    open_runs: list[str]  # dropped with the session (force)
    worktrees: list[Worktree]  # left on disk


class Forgotten(BaseModel):
    open_runs: list[str]
    worktrees: list[Worktree]


AgentStatus = Literal["starting", "busy", "idle", "background", "waiting", "stopped"]


class AgentInfo(BaseModel):
    name: str
    role: str
    provider: str
    status: AgentStatus
    run: str | None  # the flow run it works for
    task: str | None  # the first line of its task; None for none
    # Why it has its status, as far as LADO knows (runtime.status_reason): in `waiting`, why
    # it waits after failed messages and what the human can do (None when it waits for the
    # human in its terminal, a prompt); in `stopped`, why its process ended. Else None.
    status_reason: str | None
    branch: str | None  # a worker's; None for the supervisor, which works in the repo
    worktree: str | None  # a worker's folder; None for the supervisor
    spawned_at: str  # UTC, ISO 8601: its latest spawn
    since: str  # UTC, ISO 8601: when it got its status, as `lado ls` says


class CommitInfo(BaseModel):
    sha: str
    subject: str
    at: str  # UTC, ISO 8601


class WorkInfo(BaseModel):
    """Where a worker's work stands in git when asked (runtime.work_state): what finishing
    it goes by."""

    branch: str
    base: str  # the repo's current branch
    ahead: int  # commits not in base: 0 means merged
    behind: int
    uncommitted: int  # paths with changes in its worktree
    last_commit: CommitInfo


class AgentDetails(BaseModel):
    task: str | None  # the whole task
    # The state of its work now; None for an agent without a branch of its own (the
    # supervisor), or when git cannot tell, and then work_problem says why.
    work: WorkInfo | None
    work_problem: str | None


class FinishPreviewInfo(BaseModel):
    """What finishing the worker would do now (runtime.finish_preview)."""

    removes_worktree: bool  # else only its window closes: its run keeps the worktree
    refused: str | None  # why it cannot finish without discarding its work
    work: WorkInfo | None


class Finish(BaseModel):
    discard: bool = False


class Transition(BaseModel):
    """A flow event's move, as state.transition reads its detail."""

    from_state: str
    outcome: str
    to_state: str


class RunEventInfo(BaseModel):
    """What happened to a flow run: its start, a transition, a gate, its end."""

    id: int
    run: str
    kind: str  # flow_start | flow | flow_end | flow_cancel | flow_set | gate_open | ...
    actor: str  # the agent that did it, or lado
    # As the core wrote it. The server does not parse it, but for a transition: read by
    # state.transition next to its writer, so the UI gets the move without a parser of its own.
    detail: str
    transition: Transition | None  # only of a flow event whose detail is one
    created_at: str  # UTC, ISO 8601


class RecordInfo(BaseModel):
    """One write of an artifact's content; never changed (docs/design/artifacts.md)."""

    id: str
    media_type: str
    size: int  # bytes
    hash: str  # sha256 hex of the content
    author: str
    run: str | None  # in a run's scope: the run and its state it was written in
    state: str | None
    summary: str | None  # what changed, one line
    created_at: str  # UTC, ISO 8601


class ArtifactInfo(BaseModel):
    """A named document of the session, as of its latest record."""

    id: str
    session: str
    scope: str  # the run's name, '' for the session's
    name: str
    full_name: str  # <run>/<name>, or <name> in the session's scope
    title: str | None
    latest: RecordInfo


class RecordView(BaseModel):
    """A record with its artifact as it is now."""

    artifact: ArtifactInfo
    record: RecordInfo


class AttachmentInfo(BaseModel):
    """An artifact as a message or a note has it attached: the record it was at then. It
    changed since when its artifact's latest record has another hash (the UI compares)."""

    artifact: str  # the artifact's id
    record: str  # the attached record's id
    full_name: str
    name: str
    scope: str
    title: str | None
    media_type: str
    size: int
    hash: str


class NoteInfo(BaseModel):
    """A note a run's step reported, with the state it was reported from: the record of
    the step (state.NOTES_STEP)."""

    id: int
    run: str
    state: str
    kind: Literal["report", "override"]  # override: kept, but never a state's report
    actor: str  # who reported it; '' in notes from before LADO 0.18
    outcome: str  # '' in notes from before LADO 0.18 and for the human's flow-set
    # Where the outcome leads; a loop limit kept the run out of it when its next note is
    # the loop gate's answer. '' in notes from before LADO 0.18.
    target: str
    summary: str
    body: str
    attachments: list[AttachmentInfo]
    created_at: str  # UTC, ISO 8601


class FlowStateInfo(BaseModel):
    """A state of a run's flow, as the run's snapshot has it."""

    name: str
    kind: Literal["work", "gate", "end"]
    agent: str | None  # work: the role that acts
    gate: Literal["approval", "choice"] | None
    ask: str | None  # gate: the question for the human
    outcomes: dict[str, str]  # outcome -> the state it leads to
    max_visits: int | None
    reads: list[str]  # the run's artifacts it shows, by their bare names
    produces: list[str]  # work: the artifacts its step must write


class RunInfo(BaseModel):
    """A flow run: where it is, who acts and its flow."""

    name: str
    flow: str
    kit: dict[str, str]  # name, version and source of the flow's kit
    task: str
    state: str
    status: Literal["active", "waiting", "ended", "cancelled"]
    reason: str  # why it waits for the human, or was cancelled
    # Who acts next, as the core says it (runs.acting): the supervisor, a worker,
    # "<role> (not spawned)", "human", or '' for a closed run. The UI does not parse it.
    acting: str
    visits: dict[str, int]  # state -> times entered
    gate: int | None  # the id of its open gate
    worktree: str
    branch: str
    language: str  # the human's language, for the notes; '' for none given
    created_at: str  # UTC, ISO 8601
    since: str  # UTC, ISO 8601: its latest event, since when it is where it is
    ended_at: str | None  # an ended or cancelled run's: its latest event
    states: list[FlowStateInfo]  # in the order the flow declares them; [] with a problem
    problem: str | None  # why its flow snapshot cannot be read; None when it can


class GateInfo(BaseModel):
    """A flow run's question to the human: open while `answer` is None."""

    id: int
    run: str
    state: str  # the gate state, or the state a loop limit kept the run out of
    kind: Literal["approval", "choice", "loop"]
    question: str
    options: list[str]
    note: str  # the note of the step that led to the gate
    note_body: str
    attachments: list[AttachmentInfo]  # that note's, kept with it (by its id)
    # The full names of the run's artifacts the gate state reads, but those attached to the
    # note (runs.gate_reads): only while it is open, since what the human saw when
    # answering is not kept. Names only: the UI shows each one's latest record from the
    # feed's artifacts. A loop limit reads none; None too when its run's flow cannot be
    # read (problem).
    reads: list[str] | None
    answer: str | None  # an option, or how it was closed otherwise (overridden, cancelled)
    comment: str
    answered_by: str | None
    created_at: str  # UTC, ISO 8601
    answered_at: str | None
    problem: str | None  # why its run's flow snapshot cannot be read; None when it can


class GateAnswer(BaseModel):
    option: str
    comment: str = ""


class History(BaseModel):
    text: str  # the window's last lines, its screen included, oldest first
    alternate: bool  # a full-screen program: its history is inside it, not here


class MessageInfo(BaseModel):
    """A message, a question to the human (kind "question") or an answer to one."""

    model_config = ConfigDict(populate_by_name=True)

    id: int
    from_: str = Field(alias="from")
    to: str
    kind: Literal["message", "question"]
    summary: str
    body: str
    state: Literal["pending", "sent", "delivered", "read", "dropped", "failed"]
    choices: list[str] | None
    free_answer: bool
    question_state: Literal["open", "answered", "dismissed", "closed"] | None
    answered_by: int | None  # the answer's or dismissal's id
    reply_to: int | None  # an answer's or dismissal's: the question's id
    choice: str | None
    reply_state: Literal["replied", "missing"] | None  # missing: replied only in its terminal
    attachments: list[AttachmentInfo]
    created_at: str  # UTC, ISO 8601


class MessagePage(BaseModel):
    """A page of a session's messages, oldest first, and whether messages that match come
    before its first one."""

    items: list[MessageInfo]
    earlier: bool


class MessageText(BaseModel):
    """The human's text from the composer, with the full names of the files uploaded for
    it (POST …/artifacts); the text may be empty when there are some."""

    to: str = "supervisor"
    text: str
    artifacts: list[str] = []


class Limits(BaseModel):
    """What the composer checks before an upload and how it marks a file, all the core's
    (lado.artifacts, lado.runtime): the UI keeps no copy."""

    extensions: dict[str, str]  # a file name's extension -> its media type
    text_types: list[str]  # read as text besides text/*
    agent_images: list[str]  # the images read_artifact shows an agent
    max_size: int  # bytes of a file
    max_files: int  # files of a message
    image_limit: int  # bytes of an image an agent is shown
    image_max_side: int  # px
    max_message: int  # characters of a message's text; a longer paste becomes a file


class Answer(BaseModel):
    choice: str | None = None
    text: str | None = None


class Sent(BaseModel):
    result: str  # what became of it: delivered, sent or queued, and why


class WaitingItem(BaseModel):
    """One thing that waits for the human (Needs you): an open gate, an open question to
    the human or an agent in `waiting`, with the one of `gate`, `question`, `agent` its
    kind names."""

    session: str
    kind: Literal["gate", "question", "agent"]
    # gate:<id>, question:<id>, agent:<session>/<name>@<since>: a new wait of the same agent
    # is a new item
    key: str
    since: str  # UTC, ISO 8601: when it opened, or the agent got `waiting`
    gate: GateInfo | None = None
    question: MessageInfo | None = None
    agent: AgentInfo | None = None


def message_info(message: state.Message) -> MessageInfo:
    return MessageInfo(
        id=message.id,
        from_=message.sender,
        to=message.recipient,
        kind=message.kind,
        summary=message.title,
        body=message.body,
        state=message.state,
        choices=message.choices,
        free_answer=message.free_answer,
        question_state=message.question_state,
        answered_by=message.answered_by,
        reply_to=message.reply_to,
        choice=message.choice,
        reply_state=message.reply_state,
        attachments=attachment_infos(state.message_attachments(message.id))
        if message.attachments
        else [],
        created_at=_utc(message.created_at),
    )


def record_info(record: artifacts.Record) -> RecordInfo:
    return RecordInfo(
        id=record.id,
        media_type=record.media_type,
        size=record.size,
        hash=record.hash,
        author=record.author,
        run=record.run,
        state=record.state,
        summary=record.summary,
        created_at=_utc(record.created_at),
    )


def artifact_info(artifact: artifacts.Artifact, latest: artifacts.Record) -> ArtifactInfo:
    return ArtifactInfo(
        id=artifact.id,
        session=artifact.session,
        scope=artifact.scope,
        name=artifact.name,
        full_name=artifact.full_name,
        title=artifact.title,
        latest=record_info(latest),
    )


def attachment_infos(rows: list[tuple[str, str]]) -> list[AttachmentInfo]:
    """The attachments of a message or a note, by the core's one builder."""
    return [attachment_info(a) for a in artifacts.attached(rows)]


def attachment_info(attached: artifacts.Attachment) -> AttachmentInfo:
    artifact, record = attached.artifact, attached.record
    return AttachmentInfo(
        artifact=artifact.id,
        record=record.id,
        full_name=artifact.full_name,
        name=artifact.name,
        scope=artifact.scope,
        title=artifact.title,
        media_type=record.media_type,
        size=record.size,
        hash=record.hash,
    )


def _utc(created_at: str) -> str:
    """A time as lado.db keeps it ("YYYY-MM-DD HH:MM:SS", UTC) in ISO 8601."""
    return created_at.replace(" ", "T") + "Z"


def db_second(when: datetime.datetime, after: bool = False) -> str:
    """The start of the second of `when` (UTC when it names no zone), or with `after` of the
    next second, as lado.db keeps times: a time from the UI has milliseconds that a row of
    the same second may not have."""
    if when.tzinfo is not None:
        when = when.astimezone(datetime.timezone.utc)
    second = when.replace(microsecond=0, tzinfo=None)
    if after:
        second += datetime.timedelta(seconds=1)
    return second.strftime("%Y-%m-%d %H:%M:%S")


def _first_line(text: str | None) -> str | None:
    lines = (text or "").strip().splitlines()
    return lines[0].strip() if lines else None


def _iso(when: datetime.datetime) -> str:
    """A UTC time in ISO 8601, as _utc gives lado.db's."""
    return when.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def agent_info(agent: state.Agent) -> AgentInfo:
    spawned, since = state.agent_times(agent.session, agent.name)
    added = _utc(agent.created_at)  # an agent written without LADO's runtime has no events
    worker = agent.branch is not None
    return AgentInfo(
        name=agent.name,
        role=agent.role,
        provider=agent.provider,
        status=agent.status,
        run=agent.run,
        task=_first_line(agent.task),
        status_reason=(
            runtime.status_reason(agent.session, agent.name)
            if agent.status in (state.WAITING, state.STOPPED)
            else None
        ),
        branch=agent.branch,
        worktree=agent.cwd if worker else None,
        spawned_at=_iso(spawned) if spawned else added,
        since=_iso(since) if since else added,
    )


def work_info(work: runtime.WorkState) -> WorkInfo:
    return WorkInfo(
        branch=work.branch,
        base=work.base,
        ahead=work.ahead,
        behind=work.behind,
        uncommitted=work.uncommitted,
        last_commit=CommitInfo(
            sha=work.last_commit.sha,
            subject=work.last_commit.subject,
            at=_iso(work.last_commit.at),
        ),
    )


def agent_details(agent: state.Agent) -> AgentDetails:
    if agent.branch is None:
        return AgentDetails(task=agent.task, work=None, work_problem=None)
    try:
        work = runtime.work_state(agent.session, agent.name)
    except runtime.LadoError as error:
        return AgentDetails(task=agent.task, work=None, work_problem=str(error))
    return AgentDetails(task=agent.task, work=work_info(work), work_problem=None)


def finish_preview_info(preview: runtime.FinishPreview) -> FinishPreviewInfo:
    return FinishPreviewInfo(
        removes_worktree=preview.removes_worktree,
        refused=preview.refused,
        work=work_info(preview.work) if preview.work else None,
    )


def waiting_item(waits: state.Waits) -> WaitingItem:
    since = _utc(waits.since)
    if waits.gate is not None:
        key, kind = f"gate:{waits.gate.id}", "gate"
    elif waits.question is not None:
        key, kind = f"question:{waits.question.id}", "question"
    else:
        assert waits.agent is not None, "a wait is a gate, a question or an agent"
        key, kind = f"agent:{waits.session}/{waits.agent.name}@{since}", "agent"
    return WaitingItem(
        session=waits.session,
        kind=kind,
        key=key,
        since=since,
        gate=gate_info(waits.gate) if waits.gate else None,
        question=message_info(waits.question) if waits.question else None,
        agent=agent_info(waits.agent) if waits.agent else None,
    )


def run_event_info(event: state.Event) -> RunEventInfo:
    assert event.run is not None, "only a run's event is a RunEventInfo"
    move = state.transition(event.detail) if event.kind == state.FLOW else None
    return RunEventInfo(
        id=event.id,
        run=event.run,
        kind=event.kind,
        actor=event.agent,
        detail=event.detail,
        transition=None
        if move is None
        else Transition(from_state=move[0], outcome=move[1], to_state=move[2]),
        created_at=_utc(event.created_at),
    )


def note_info(note: state.Note) -> NoteInfo:
    return NoteInfo(
        id=note.id,
        run=note.run,
        state=note.state,
        kind=note.kind,
        actor=note.actor,
        outcome=note.outcome,
        target=note.target,
        summary=note.summary,
        body=note.body,
        attachments=attachment_infos(state.note_attachments(note.id)) if note.attachments else [],
        created_at=_utc(note.created_at),
    )


def flow_state_info(found: flows.State) -> FlowStateInfo:
    return FlowStateInfo(
        name=found.name,
        kind=found.kind,
        agent=found.agent or None,
        gate=found.gate or None,
        ask=found.ask or None,
        outcomes=found.outcomes,
        max_visits=found.max_visits,
        reads=list(found.reads),
        produces=list(found.produces),
    )


_logged: set[tuple[str, str]] = set()  # (session, message) of the problems logged already


def _unreadable(session: str, error: runs.SnapshotError) -> str:
    """The problem of an item built without its run's flow, logged once: the feed builds
    the item again on every change of the run or of its session's agents."""
    problem = str(error)
    if (session, problem) not in _logged:
        _logged.add((session, problem))
        log.warning("session %s: %s", session, problem)
    return problem


def run_info(run: state.Run) -> RunInfo:
    last = state.last_run_event(run.session, run.name)
    since = _utc(last.created_at if last else run.created_at)
    gate = state.open_gate(run.session, run.name) if run.status == state.WAITING else None
    acting, _ = runs.acting_or_problem(run)
    problem = None
    try:
        states = [flow_state_info(s) for s in runs.flow_of(run).states.values()]
    except runs.SnapshotError as error:
        problem = _unreadable(run.session, error)
        states = []
    return RunInfo(
        name=run.name,
        flow=run.flow,
        kit=run.kit,
        task=run.task,
        state=run.state,
        status=run.status,
        reason=run.reason,
        acting=acting,
        visits=run.visits,
        gate=gate.id if gate else None,
        worktree=run.worktree,
        branch=run.branch,
        language=run.language,
        created_at=_utc(run.created_at),
        since=since,
        ended_at=since if run.status not in state.OPEN else None,
        states=states,
        problem=problem,
    )


def gate_info(gate: state.Gate) -> GateInfo:
    reads = problem = None
    if gate.answer is None:
        try:
            reads = [artifacts.full_name(gate.run, name) for name in runs.gate_reads(gate)]
        except runs.SnapshotError as error:
            problem = _unreadable(gate.session, error)
    return GateInfo(
        id=gate.id,
        run=gate.run,
        state=gate.state,
        kind=gate.kind,
        question=gate.question,
        options=gate.options,
        note=gate.note,
        note_body=gate.note_body,
        attachments=[attachment_info(a) for a in runs.gate_attachments(gate)],
        reads=reads,
        answer=gate.answer,
        comment=gate.comment,
        answered_by=gate.answered_by or None,
        created_at=_utc(gate.created_at),
        answered_at=_utc(gate.answered_at) if gate.answered_at else None,
        problem=problem,
    )


def session_info(sess: state.Session) -> SessionInfo:
    gates, questions, agents = state.waiting_for_human(sess.name)
    status = runtime.session_status(sess)
    ran = runtime.session_time(sess, status)
    busy, since = (
        state.session_activity(sess.name) if status == runtime.SessionStatus.RUNNING else (0, None)
    )
    return SessionInfo(
        name=sess.name,
        repo=sess.repo,
        status=status,
        agents=len(state.list_agents(sess.name)),
        waiting=Waiting(gates=gates, questions=questions, agents=agents),
        busy=busy,
        activity_since=_iso(since) if since else None,
        kits=sess.kits,
        provider=sess.provider,
        permission_mode=sess.permission_mode,
        without=sess.without,
        ran_seconds=ran.ran_seconds,
        running_since=_iso(ran.running_since) if ran.running_since else None,
        stopped_at=_utc(sess.stopped_at) if sess.stopped_at else None,
    )


def worktrees(found: dict[str, str]) -> list[Worktree]:
    return [Worktree(path=path, branch=branch) for path, branch in found.items()]


def started(done: runtime.Started) -> Started:
    return Started(
        session=session_info(state.get_session(done.session.name) or done.session),
        resumed=done.resumed,
        changes=done.changes,
        problems=done.problems,
        lead=done.lead,
        warnings=done.warnings,
    )


def _skill_names(kit: kits.Kit) -> list[str]:
    """Its own skills and those of its packs that are fetched."""
    packs = [name for pack in kit.packs.values() for name in (pack.skills or {})]
    return [*kit.skills, *packs]


def installed_kit_info(found: kits.Found) -> InstalledKitInfo:
    """An installed kit (`found.installed`) or a built-in one, loaded from its files; one
    that does not load says why. Reads only its own row and files."""
    row = found.installed
    try:
        kit: kits.Kit | None = found.load()
        problem = None
    except kits.KitError as exc:
        kit, problem = None, str(exc)
    kind: KitKind = "built-in" if row is None else "git" if row.address else "folder"
    return InstalledKitInfo(
        name=found.name,
        version=kit.version if kit else "",
        description=kit.description if kit else "",
        valid=kit is not None,
        problem=problem,
        kind=kind,
        address=row.address if row else None,
        tag=row.tag if row else None,
        commit=row.commit if row else None,
        folder=row.folder if row else None,
        marketplace=row.marketplace if row else None,
        installed_at=_utc(row.installed_at) if row and row.installed_at else None,
        updated_at=_utc(row.updated_at) if row and row.updated_at else None,
        agents=len(kit.agents) if kit else 0,
        skills=len(_skill_names(kit)) if kit else 0,
        flows=len(kit.flows) if kit else 0,
        mcp=kits.mcp_names(kit) if kit else [],
        missing=row is not None and not found.path.is_dir(),
    )


def kit_users_info(kit: str, users: runtime.KitUsers) -> KitUsersInfo:
    return KitUsersInfo(
        running=users.running,
        stopped=users.stopped,
        running_line=users.running_line(kit),
        stopped_line=users.stopped_line(kit),
    )


def plan_info(plan: kits.Install, users: runtime.KitUsers | None = None) -> PlanInfo:
    """A plan as the UI shows it; an update's with the sessions that use the kit."""
    if plan.tag is None:
        spec = plan.address
    elif plan.marketplace and plan.installed is None:
        spec = f"{plan.name}@{plan.tag}"
    else:
        spec = f"{plan.address}@{plan.tag}"
    notes = []
    if plan.current:
        notes.append(kits.current_line(plan))
    elif users is not None:
        notes.append(kits.update_line(plan, users.running))
    return PlanInfo(
        name=plan.name,
        version=plan.kit.version,
        description=plan.kit.description,
        spec=spec,
        address=plan.address,
        tag=plan.tag,
        commit=plan.commit,
        source=plan.source,
        marketplace=plan.marketplace,
        installed=plan.installed,
        needs_confirmation=plan.needs_confirmation,
        current=plan.current,
        versions=list(plan.versions),
        agents=list(plan.kit.agents),
        skills=_skill_names(plan.kit),
        flows=list(plan.kit.flows),
        mcp=[McpInfo(name=name, command=" ".join(m.command)) for name, m in plan.mcp.items()],
        new_mcp=list(plan.new_mcp),
        warnings=[*plan.warnings, *kits.new_mcp_warnings(plan)],
        notes=notes,
        users=None if users is None else kit_users_info(plan.name, users),
        before=None if plan.before is None else kit_contents_info(plan.before),
    )


def kit_contents_info(kit: kits.Kit) -> KitContentsInfo:
    return KitContentsInfo(
        agents=list(kit.agents),
        skills=_skill_names(kit),
        flows=list(kit.flows),
        mcp=kits.mcp_names(kit),
    )


def outdated_info(row: kits.Outdated) -> OutdatedInfo:
    above = (
        row.latest
        and row.latest != row.installed
        and gitcache.sorted_versions([row.installed, row.latest])[-1] == row.latest
    )
    return OutdatedInfo(
        newer=row.latest if above else None,
        name=row.name,
        installed=row.installed,
        latest=row.latest,
        pre=row.pre,
        note=row.note,
        warnings=list(row.warnings),
    )


def offer_info(offer: marketplaces.Offer, installed: set[str]) -> OfferInfo:
    entry = offer.entry
    return OfferInfo(
        name=offer.name,
        marketplace=offer.marketplace,
        address=offer.address,
        installed=offer.name in installed,
        index=None if entry is None else IndexEntryInfo(**dataclasses.asdict(entry)),
    )


def marketplace_info(market: state.Marketplace) -> MarketplaceInfo:
    """A marketplace and what its clone says now; never the network."""
    problems = []
    try:
        listed = marketplaces.listed(market)
    except marketplaces.MarketplaceError as exc:
        listed, problems = None, [str(exc)]
    found = marketplaces.index(market)
    if found.problem and found.problem not in problems:
        problems.append(found.problem)
    return MarketplaceInfo(
        name=market.name,
        url=marketplaces.url(market),
        enabled=market.enabled,
        updated_at=_utc(market.updated_at) if market.updated_at else None,
        official=market.name == marketplaces.OFFICIAL,
        kits=None if listed is None else len(listed),
        index=found.present,
        problem="; ".join(problems) or None,
    )
