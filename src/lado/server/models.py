"""The API's models, and each one built from the state: one form of an entity for the REST
API and for the event stream's items (lado.server.feed)."""

from pydantic import BaseModel

from lado import runtime, state


class SessionInfo(BaseModel):
    name: str
    repo: str
    status: runtime.SessionStatus
    agents: int  # agents the session has now


def session_info(sess: state.Session) -> SessionInfo:
    return SessionInfo(
        name=sess.name,
        repo=sess.repo,
        status=runtime.session_status(sess),
        agents=len(state.list_agents(sess.name)),
    )
