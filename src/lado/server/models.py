"""The API's models, and each one built from the state: one form of an entity for the REST
API and for the event stream's items (lado.server.feed)."""

from typing import Literal

from pydantic import BaseModel

from lado import runtime, state


class SessionInfo(BaseModel):
    name: str
    repo: str
    status: runtime.SessionStatus
    agents: int  # agents the session has now


AgentStatus = Literal["starting", "busy", "idle", "waiting", "stopped"]


class AgentInfo(BaseModel):
    name: str
    role: str
    provider: str
    status: AgentStatus


class History(BaseModel):
    text: str  # the window's last lines, its screen included, oldest first
    alternate: bool  # a full-screen program: its history is inside it, not here


def agent_info(agent: state.Agent) -> AgentInfo:
    return AgentInfo(name=agent.name, role=agent.role, provider=agent.provider, status=agent.status)


def session_info(sess: state.Session) -> SessionInfo:
    return SessionInfo(
        name=sess.name,
        repo=sess.repo,
        status=runtime.session_status(sess),
        agents=len(state.list_agents(sess.name)),
    )
