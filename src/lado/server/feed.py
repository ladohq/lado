"""The UI server's change feed: what changed, for GET /api/events (Server-Sent Events).

Where the changes come from is a `Source`, the server's only one: "the changes after
position N" and "the latest position". Now that is the journal SQLite triggers write in
lado.db (`Journal`, state.CHANGES), read only, so a change by any process is in it; remote
workers' events will come through the same interface later.

One `Hub` per server reads the source every POLL seconds and hands each batch to every open
stream. A batch keeps one change per row, (kind, session, key), with its latest id. Each
change goes out as `{kind, session, key, op, item}`: `item` is the row as it is now, in the
form of its REST model, or null when the row is gone (whatever `op` says) or its kind has
no model yet (ITEMS).

What the UI shows but lado.db does not keep is derived (DERIVED): the hub computes it every
DERIVED_EVERY seconds and sends a change when it differs. Such a synthetic change has no
`id:` line, so the browser keeps its position, and a stream resumed from a position gets the
current value of everything derived after its replay: a change while it was away is not
lost. The rules for the start of a stream are in `stream`.
"""

import asyncio
import json
import logging
import sqlite3
import time
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from typing import Protocol

from anyio import to_thread

from lado import loop, runtime, state
from lado.server import models

POLL = 0.25  # seconds between two reads of the source
DERIVED_EVERY = 3.0  # seconds between two computations of what is derived
KEEPALIVE = 15.0  # seconds of quiet after which a stream gets a comment line
FAILED_PASSES = 3  # reads of the source that fail in a row before the open streams end

log = logging.getLogger("lado.server")


@dataclass(frozen=True)
class Change:
    kind: str  # sessions | agents | messages | runs | gates | notes | events
    session: str
    key: str  # the row in its session; '' for the session itself
    op: str  # insert | update | delete: for information, the item tells what is there
    id: int | None = None  # its position in the journal; None for a synthetic one


class Source(Protocol):
    """Where the server gets changes from."""

    def problem(self) -> str | None:
        """Why changes cannot be read now (lado.db of another schema), or None."""

    def exists(self) -> bool:
        """Whether there is anything yet; the server never creates it."""

    def last(self) -> int:
        """The latest position, 0 for none."""

    def after(self, position: int) -> list[Change] | None:
        """The changes after `position`, oldest first; None when the source no longer has
        that position (dropped from the journal, or never there)."""


def schema_problem() -> str | None:
    """Why the server cannot read lado.db: another schema version. It never migrates. A
    file of version 0 is being made by another process: nothing there yet, no problem."""
    version = state.schema_version()
    if not version or version == state.SCHEMA_VERSION:
        return None
    return (
        f"{state.home() / 'lado.db'} has schema version {version}, this server knows "
        f"{state.SCHEMA_VERSION}: upgrade LADO or restart `lado server`"
    )


def database_made() -> bool:
    """Whether lado.db is there with its schema (not still being made)."""
    return bool(state.schema_version())


class Journal:
    """The change journal in lado.db, read only."""

    def problem(self) -> str | None:
        return schema_problem()

    def exists(self) -> bool:
        return database_made()

    def _read(self, position: int) -> tuple[int, int, list[Change]]:
        """The first and last id in the journal and the changes after `position`."""
        if not self.exists():
            return 0, 0, []
        path = state.home() / "lado.db"
        db = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True, timeout=10)
        try:
            db.execute("BEGIN")  # one snapshot for both reads
            first, last = db.execute("SELECT min(id), max(id) FROM changes").fetchone()
            rows = db.execute(
                "SELECT id, kind, session, key, op FROM changes WHERE id > ? ORDER BY id",
                (position,),
            ).fetchall()
            db.execute("COMMIT")
        finally:
            db.close()
        changes = [Change(kind, session, key, op, id) for id, kind, session, key, op in rows]
        return first or 0, last or 0, changes

    def last(self) -> int:
        return self._read(0)[1] if self.exists() else 0

    def after(self, position: int) -> list[Change] | None:
        first, last, changes = self._read(position)
        if position > last or (first and position < first - 1):
            return None
        return changes


def _session_item(session: str, key: str) -> dict | None:
    sess = state.get_session(session)
    return None if sess is None else models.session_info(sess).model_dump(mode="json")


def _agent_item(session: str, key: str) -> dict | None:
    agent = state.get_agent(session, key)
    return None if agent is None else models.agent_info(agent).model_dump(mode="json")


def _message_item(session: str, key: str) -> dict | None:
    message = state.get_message(session, int(key))
    if message is None:
        return None
    return models.message_info(message).model_dump(mode="json", by_alias=True)


def _event_item(session: str, key: str) -> dict | None:
    event = state.get_event(session, int(key))
    return None if event is None else models.run_event_info(event).model_dump(mode="json")


def _gate_item(session: str, key: str) -> dict | None:
    gate = state.get_gate(int(key))
    if gate is None or gate.session != session:
        return None
    return models.gate_info(gate).model_dump(mode="json")


def _run_item(session: str, key: str) -> dict | None:
    run = state.get_run(session, key)
    return None if run is None else models.run_info(run).model_dump(mode="json")


def _note_item(session: str, key: str) -> dict | None:
    note = state.get_note(session, int(key))
    return None if note is None else models.note_info(note).model_dump(mode="json")


# The kinds whose REST model exists, and how to build an item of it. Others' items are null.
ITEMS: dict[str, Callable[[str, str], dict | None]] = {
    "sessions": _session_item,
    "agents": _agent_item,
    "messages": _message_item,
    "events": _event_item,
    "gates": _gate_item,
    "runs": _run_item,
    "notes": _note_item,
}


def _the_session(session: str) -> list[str]:
    return [""]


def _open_runs(session: str) -> list[str]:
    return [run.name for run in state.list_runs(session, open_only=True)]


# A change of kind X also changes the items of kind Y of the same session whose keys the
# function gives. The session's item ('') counts its agents and what waits for the human in
# it (open gates and questions, agents in `waiting`); each such item asks tmux for its
# status (runtime.session_status): collapsed, once per session in a batch. Who acts in an
# open run (runs.acting) depends on the session's agents: any change of one, as the agent
# that was a run's worker may be deleted already (runtime.close_worker), so its run cannot
# be told.
ALSO: dict[str, list[tuple[str, Callable[[str], list[str]]]]] = {
    "agents": [("sessions", _the_session), ("runs", _open_runs)],
    "gates": [("sessions", _the_session)],
    "messages": [("sessions", _the_session)],
}


def _session_statuses() -> dict[Change, object]:
    return {
        Change("sessions", sess.name, "", "update"): runtime.session_status(sess)
        for sess in state.list_sessions()
        if not sess.stopped_at
    }


# What the UI shows but lado.db does not keep: each function gives the change of every item
# it derives with its current value. A field the UI shows that no table holds belongs here.
#   sessions.status  runtime.session_status: tmux_gone, loop_down (tmux, the loop's lock)
DERIVED: list[Callable[[], dict[Change, object]]] = [_session_statuses]


def derived() -> dict[Change, object]:
    values: dict[Change, object] = {}
    for compute in DERIVED:
        values.update(compute())
    return values


def collapse(changes: list[Change]) -> list[Change]:
    """One change per row, with its latest id, in the order of those ids; with the changes
    ALSO adds. Reads lado.db for their keys, once per kind and session."""
    latest: dict[tuple[str, str, str], Change] = {}
    keys: dict[tuple[str, str], list[str]] = {}
    for change in changes:
        ones = [change]
        for kind, of in ALSO.get(change.kind, []):
            if (kind, change.session) not in keys:
                keys[kind, change.session] = of(change.session)
            for key in keys[kind, change.session]:
                ones.append(Change(kind, change.session, key, "update", change.id))
        for one in ones:
            row = (one.kind, one.session, one.key)
            latest.pop(row, None)
            latest[row] = one
    return list(latest.values())


Event = tuple[Change, dict | None]  # a change and its item


def events(changes: list[Change]) -> list[Event]:
    """The changes, collapsed, each with its item. Reads lado.db: call it in a thread."""
    out = []
    for change in collapse(changes):
        build = ITEMS.get(change.kind)
        out.append((change, build(change.session, change.key) if build else None))
    return out


def encode(name: str, data: dict, id: int | None) -> str:
    head = "" if id is None else f"id: {id}\n"
    return f"{head}event: {name}\ndata: {json.dumps(data)}\n\n"


def encode_change(event: Event) -> str:
    change, item = event
    data = {
        "kind": change.kind,
        "session": change.session,
        "key": change.key,
        "op": change.op,
        "item": item,
    }
    return encode("change", data, change.id)


class Hub:
    """Reads the source for all of a server's streams: one loop while any stream is open."""

    def __init__(self, source: Source):
        self.source = source
        self._queues: set[asyncio.Queue[list[Event] | None]] = set()
        self._task: asyncio.Task | None = None
        self._lock = asyncio.Lock()
        self._position = 0
        self._derived: dict[Change, object] | None = None
        self._derived_at = 0.0
        self._errors = loop.RepeatedErrors(log.warning)  # one traceback, then counts
        self._failures = 0  # failing reads in a row

    async def subscribe(self) -> asyncio.Queue[list[Event] | None]:
        """A queue that gets each batch of events, and None when the stream must end."""
        async with self._lock:
            if self._task is None:
                # Before the stream reads its start: what it starts from is not missed.
                self._position = await to_thread.run_sync(self.source.last)
                self._derived = None
                self._failures = 0
                self._task = asyncio.create_task(self._run())
            queue: asyncio.Queue[list[Event] | None] = asyncio.Queue()
            self._queues.add(queue)
            return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        self._queues.discard(queue)
        if not self._queues and self._task is not None:
            self._task.cancel()
            self._task = None

    def _send(self, batch: list[Event] | None) -> None:
        for queue in self._queues:
            queue.put_nowait(batch)

    async def _run(self) -> None:
        while True:
            await asyncio.sleep(POLL)
            try:
                await self._pass()
            except Exception:
                self.failed()
            else:
                self._failures = 0
                self._errors.worked()

    def failed(self) -> None:
        """Note the error being handled. After FAILED_PASSES in a row the streams end: the
        browser comes again, gets 503 with the reason and shows it, instead of a stream
        that stays open with nothing in it. The count starts again for the streams after."""
        self._errors.failed()
        self._failures += 1
        if self._failures >= FAILED_PASSES:
            self._failures = 0
            self._send(None)

    async def _pass(self) -> None:
        if await to_thread.run_sync(self.source.problem):
            self._send(None)  # a new stream is answered 503
            return
        changes = await to_thread.run_sync(self.source.after, self._position)
        if changes is None:  # the source went past us: the streams start over
            self._position = await to_thread.run_sync(self.source.last)
            self._send(None)
            return
        if changes:
            batch = await to_thread.run_sync(events, changes)
            # Only once the batch is made: a pass that fails reads the same changes again.
            self._position = changes[-1].id or self._position
            self._send(batch)
        if time.monotonic() - self._derived_at >= DERIVED_EVERY:
            self._derived_at = time.monotonic()
            await self._derive()

    async def _derive(self) -> None:
        if not await to_thread.run_sync(self.source.exists):
            return
        current = await to_thread.run_sync(derived)
        before = self._derived
        self._derived = current
        if before is None:
            return
        # A row new since the last computation came through the journal already.
        changed = [c for c, value in current.items() if c in before and before[c] != value]
        if changed:
            self._send(await to_thread.run_sync(events, changed))

    def snapshots(self) -> list[Event]:
        """Everything derived, as it is now. Reads lado.db: call it in a thread."""
        return events(list(derived())) if self.source.exists() else []


class Unavailable(Exception):
    """The source cannot be read now: the stream is refused (503) with the reason."""


async def check(hub: Hub) -> None:
    """Before a stream: Unavailable when the source cannot be read now."""
    try:
        await to_thread.run_sync(hub.source.last)
    except Exception as error:
        hub.failed()
        raise Unavailable(f"reading changes failed: {error}") from error


async def stream(hub: Hub, position: int | None) -> AsyncIterator[str]:
    """One stream's text. With no position, or one the source no longer has, it starts with
    `reset` at the latest position, taken before it is sent: the UI loads its data on reset
    and gets every change after it. From a position the source has, it sends what came
    after it, then everything derived as it is now."""
    queue = await hub.subscribe()
    try:
        source = hub.source
        changes = None if position is None else await to_thread.run_sync(source.after, position)
        if changes is None:
            sent = await to_thread.run_sync(source.last)
            yield encode("reset", {}, sent)
        else:
            sent = position
            for event in await to_thread.run_sync(events, changes):
                yield encode_change(event)
                sent = max(sent, event[0].id or 0)
            for event in await to_thread.run_sync(hub.snapshots):
                yield encode_change(event)
        while True:
            try:
                batch = await asyncio.wait_for(queue.get(), KEEPALIVE)
            except asyncio.TimeoutError:
                yield ": keep-alive\n\n"
                continue
            if batch is None:
                return
            fresh = [e for e in batch if e[0].id is None or e[0].id > sent]
            for event in fresh:
                yield encode_change(event)
            sent = max([sent, *(e[0].id or 0 for e in fresh)])
    finally:
        hub.unsubscribe(queue)
