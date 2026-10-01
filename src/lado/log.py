"""`lado log`: a session's messages and agent events as one time-ordered feed."""

import time
from collections.abc import Callable
from datetime import datetime, timezone

from lado import state
from lado.runtime import LadoError

Entry = state.Event | state.Message

FOLLOW_INTERVAL = 1.0  # seconds between polls of the database


class Feed:
    """Reads the entries of a session that were not read yet."""

    def __init__(self, session: str, agent: str | None = None):
        self.session = session
        self.agent = agent
        self.last_event = 0
        self.last_message = 0

    def read(self) -> list[Entry]:
        events = state.list_events(self.session, self.last_event)
        messages = state.list_messages(self.session, self.last_message)
        if events:
            self.last_event = events[-1].id
        if messages:
            self.last_message = messages[-1].id
        entries = sorted([*events, *messages], key=lambda e: e.created_at)
        return [e for e in entries if self.agent is None or self.agent in _agents(e)]


def show(
    session: str,
    agent: str | None = None,
    last: int | None = None,
    follow: bool = False,
    sleep: Callable[[float], None] = time.sleep,
) -> None:
    """Print the session's feed (the `last` entries only, if given); with `follow`, keep
    printing new entries until Ctrl-C or until the session is stopped."""
    if state.get_session(session) is None:
        names = ", ".join(s.name for s in state.list_sessions()) or "none"
        raise LadoError(f'unknown session "{session}"; sessions: {names}')
    feed = Feed(session, agent)
    entries = feed.read()
    for entry in entries if last is None else entries[max(len(entries) - last, 0) :]:
        print(format_entry(entry), flush=True)
    try:
        while follow:
            sleep(FOLLOW_INTERVAL)
            if state.get_session(session) is None:
                print(f'Session "{session}" stopped.')
                return
            for entry in feed.read():
                print(format_entry(entry), flush=True)
    except KeyboardInterrupt:
        pass


def format_entry(entry: Entry) -> str:
    at = _local_time(entry.created_at)
    if isinstance(entry, state.Message):
        body = "".join(f"\n    {line}" for line in entry.body.splitlines())
        return f"{at} {entry.sender} → {entry.recipient} [{entry.state}] {entry.title}{body}"
    if entry.kind == state.STATUS:
        return f"{at} {entry.agent}: {entry.detail}"
    detail = f" ({entry.detail})" if entry.detail else ""
    run = f" {entry.run}" if entry.run else ""
    return f"{at} {entry.agent}: {entry.kind}{run}{detail}"


def _agents(entry: Entry) -> tuple[str, ...]:
    if isinstance(entry, state.Message):
        return (entry.sender, entry.recipient)
    return (entry.agent,)


def _local_time(utc: str) -> str:
    when = datetime.fromisoformat(utc).replace(tzinfo=timezone.utc)
    return when.astimezone().strftime("%H:%M:%S")
