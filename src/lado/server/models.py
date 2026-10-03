"""The API's models, and each one built from the state: one form of an entity for the REST
API and for the event stream's items (lado.server.feed)."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from lado import runtime, state


class Waiting(BaseModel):
    """What in a session waits for the human: the one definition of "needs you"."""

    gates: int  # open gates of its runs
    questions: int  # open questions of its agents (ask_human)
    agents: int  # agents in `waiting`


class SessionInfo(BaseModel):
    name: str
    repo: str
    status: runtime.SessionStatus
    agents: int  # agents the session has now
    waiting: Waiting


AgentStatus = Literal["starting", "busy", "idle", "waiting", "stopped"]


class AgentInfo(BaseModel):
    name: str
    role: str
    provider: str
    status: AgentStatus
    run: str | None  # the flow run it works for
    task: str | None  # the first line of its task; None for none


class RunEventInfo(BaseModel):
    """What happened to a flow run: its start, a transition, a gate, its end."""

    id: int
    run: str
    kind: str  # flow_start | flow | flow_end | flow_cancel | flow_set | gate_open | ...
    actor: str  # the agent that did it, or lado
    detail: str  # as the core wrote it; the server does not parse it
    created_at: str  # UTC, ISO 8601


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
    created_at: str  # UTC, ISO 8601


class MessageText(BaseModel):
    """The human's text from the composer."""

    to: str = "supervisor"
    text: str


class Answer(BaseModel):
    choice: str | None = None
    text: str | None = None


class Sent(BaseModel):
    result: str  # what became of it: delivered, sent or queued, and why


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
        created_at=_utc(message.created_at),
    )


def _utc(created_at: str) -> str:
    """A time as lado.db keeps it ("YYYY-MM-DD HH:MM:SS", UTC) in ISO 8601."""
    return created_at.replace(" ", "T") + "Z"


def _first_line(text: str | None) -> str | None:
    lines = (text or "").strip().splitlines()
    return lines[0].strip() if lines else None


def agent_info(agent: state.Agent) -> AgentInfo:
    return AgentInfo(
        name=agent.name,
        role=agent.role,
        provider=agent.provider,
        status=agent.status,
        run=agent.run,
        task=_first_line(agent.task),
    )


def run_event_info(event: state.Event) -> RunEventInfo:
    assert event.run is not None, "only a run's event is a RunEventInfo"
    return RunEventInfo(
        id=event.id,
        run=event.run,
        kind=event.kind,
        actor=event.agent,
        detail=event.detail,
        created_at=_utc(event.created_at),
    )


def session_info(sess: state.Session) -> SessionInfo:
    gates, questions, agents = state.waiting_for_human(sess.name)
    return SessionInfo(
        name=sess.name,
        repo=sess.repo,
        status=runtime.session_status(sess),
        agents=len(state.list_agents(sess.name)),
        waiting=Waiting(gates=gates, questions=questions, agents=agents),
    )
