"""An agent's terminal over a WebSocket: the endpoint's protocol around lado.terminal.

From the server: the terminal's output as binary frames, and JSON text frames
`{type: "size", cols, rows}` (the window's size: first, and in view whenever it changes) and
`{type: "error", reason}`. From the browser, JSON text: `{type: "input", data}` and
`{type: "resize", cols, rows}`, both only in control; in view, and for a frame it does not
know, the answer is an error frame, and the socket stays open.

Backpressure: the terminal is read again only once its last output was sent.

How a socket ends tells the browser whether to open it again (close codes): 44xx for good,
with the reason (no token, a mode it does not know, no terminal: the agent or its session is
gone or stopped); 45xx for now (the terminal ended but the agent is still there; lado.db of
another schema), to open again after a pause. Another Origin is refused before the upgrade.
The token is checked at the connect, and again once the socket is in `OPEN` (a new token
made while the terminal opened), not later: so a new token closes every open socket
(`close_all`) to be opened again.
"""

import dataclasses
import json
import logging
import time

import anyio
from anyio import to_thread
from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect

from lado import logins, providers, terminal
from lado.server import feed
from lado.server.auth import Guard, Refused

DENIED, BAD_MODE, GONE = 4401, 4400, 4404  # for good
ENDED, UNAVAILABLE = 4500, 4503  # for now: open again after a pause
SIZE_EVERY = 1.0  # seconds between two looks at the window's size, in view
LOOK_EVERY = 0.5  # seconds between two looks at a login window (watch_login)
WATCH_LAST = 5.0  # the most a socket waits for its watch once its output ended (_run)
REASON_BYTES = 123  # the most a close frame's reason holds
OPEN: set[WebSocket] = set()  # the sockets accepted with a terminal, until they end

log = logging.getLogger("lado.server")


async def _admitted(ws: WebSocket, guard: Guard) -> bool:
    """Whether the token and the Origin let the socket in; else it is refused, saying why."""
    try:
        guard.check(ws, changes=True)
    except Refused as refused:
        if refused.status == 403:
            await ws.close(1008)  # before the upgrade: another page gets nothing
            return False
        await _end(ws, DENIED, refused.detail)
        return False
    return True


async def serve(ws: WebSocket, guard: Guard, session: str, agent: str, mode: str) -> None:
    if not await _admitted(ws, guard):
        return
    if mode not in terminal.MODES:
        await _end(ws, BAD_MODE, f"mode is {' or '.join(terminal.MODES)}, not {mode}")
        return
    problem = await to_thread.run_sync(feed.schema_problem)
    if problem:
        await _end(ws, UNAVAILABLE, problem)
        return
    # The server never makes lado.db: without one (or while it is made) there is no session.
    if not await to_thread.run_sync(feed.database_made):
        await _end(ws, GONE, f'unknown session "{session}"')
        return
    await _serve(ws, guard, lambda: terminal.open(session, agent, mode))


async def serve_login(ws: WebSocket, guard: Guard, provider: str) -> None:
    """A provider's login window (lado.logins), always in control; it ends for good once
    the window is gone (its command ended, or Close). Besides the terminal's frames: once
    `{type: "prompt", link, code, expires, lines}` when its action shows a code (also on a
    reconnect), and `{type: "ended", status, said}` before it closes because its command
    ended (lado.logins.look)."""
    if await _admitted(ws, guard):
        await _serve(
            ws, guard, lambda: terminal.open_login(provider), lambda: watch_login(ws, provider)
        )


async def watch_login(ws: WebSocket, name: str) -> None:
    """Look at the login window every LOOK_EVERY seconds: send its prompt once it is there,
    and how its command ended, which ends the window and so the socket's output."""
    try:
        provider = providers.get(name)
    except ValueError:
        return
    prompted = False
    while True:
        found = await to_thread.run_sync(logins.look, provider, not prompted)
        if found is None:
            return  # gone (Close): the output ends
        try:
            if found.prompt and not prompted:
                prompted = True
                await ws.send_json({"type": "prompt", **dataclasses.asdict(found.prompt)})
            if found.ended:
                await ws.send_json({"type": "ended", **dataclasses.asdict(found.ended)})
                return
        except (WebSocketDisconnect, RuntimeError):
            return  # the browser went
        await anyio.sleep(LOOK_EVERY)


async def _serve(ws: WebSocket, guard: Guard, opener, watch=None) -> None:
    try:
        term = await to_thread.run_sync(opener)
    except terminal.NoTerminal as none:
        await _end(ws, GONE, str(none))
        return
    try:
        await ws.accept()
        OPEN.add(ws)
        # Checked again where `close_all` finds it: a new token made while the terminal
        # opened came after the first check and before the socket was there to close.
        try:
            guard.check(ws)
        except Refused as refused:
            await _say_and_close(ws, DENIED, refused.detail)
            return
        await ws.send_json(_size(term.size))
        await _run(ws, term, watch)
    finally:
        OPEN.discard(ws)
        with anyio.CancelScope(shield=True):  # also when the server stops
            await to_thread.run_sync(term.close)


async def close_all() -> None:
    """A new token: every open terminal socket closes to be opened again, and its reconnect
    is checked against the token the browser has now."""
    for ws in list(OPEN):
        await _close(ws, ENDED, "a new link was made: the terminal opens again")


async def _end(ws: WebSocket, code: int, reason: str) -> None:
    """Accept only to say why it ends: the browser cannot read a refused upgrade."""
    await ws.accept()
    await _say_and_close(ws, code, reason)


async def _say_and_close(ws: WebSocket, code: int, reason: str) -> None:
    await ws.send_json({"type": "error", "reason": reason})
    await ws.close(code, reason.encode()[:REASON_BYTES].decode(errors="ignore"))


def _size(size: tuple[int, int]) -> dict:
    return {"type": "size", "cols": size[0], "rows": size[1]}


async def _run(ws: WebSocket, term, watch=None) -> None:
    """Stream until the output ends or the browser goes. `watch` (a login window's) runs
    beside them; when the output ends it may still have to say how (the window ends as it
    is read), so the socket closes after it, or after WATCH_LAST at most."""
    ended = False
    watched = anyio.Event()

    async def out() -> None:
        nonlocal ended
        try:
            await output(ws, term)
            ended = True
        except (WebSocketDisconnect, RuntimeError, OSError):
            pass  # the browser went while output was sent
        if ended and watch is not None:
            with anyio.move_on_after(WATCH_LAST):
                await watched.wait()
        scope.cancel()

    async def into() -> None:
        await take_input(ws, term)
        scope.cancel()

    async def look() -> None:
        try:
            await watch()
        finally:
            watched.set()

    async with anyio.create_task_group() as group:
        scope = group.cancel_scope
        group.start_soon(out)
        group.start_soon(into)
        if watch is not None:
            group.start_soon(look)
    if ended:
        why = await to_thread.run_sync(_why_ended, term)
        if why is None:
            await _close(ws, ENDED, "the terminal closed; it opens again")
        else:
            await _close(ws, GONE, str(why))


def _why_ended(term) -> terminal.NoTerminal | None:
    if term.keep:  # a login window's
        return terminal.login_ended(term.agent)
    return terminal.ended(term.session, term.agent)


async def _close(ws: WebSocket, code: int, reason: str) -> None:
    try:
        await ws.close(code, reason.encode()[:REASON_BYTES].decode(errors="ignore"))
    except (RuntimeError, WebSocketDisconnect):
        pass  # the browser went first


async def output(ws, term) -> None:
    """Send the terminal's output until it ends; the next read waits for the last send. In
    view also the window's size when it changes."""
    looked = time.monotonic()
    while True:
        data = await to_thread.run_sync(term.read)
        if data is None:
            return
        if data:
            await ws.send_bytes(data)
        if term.mode == terminal.VIEW and time.monotonic() - looked >= SIZE_EVERY:
            looked = time.monotonic()
            size = await to_thread.run_sync(term.follow_window)
            if size:
                await ws.send_json(_size(size))


async def take_input(ws: WebSocket, term) -> None:
    """Act on the browser's frames until it goes."""
    while True:
        message = await ws.receive()
        if message["type"] == "websocket.disconnect":
            return
        problem = await _act(term, message.get("text"))
        if problem:
            await ws.send_json({"type": "error", "reason": problem})


async def _act(term, text: str | None) -> str | None:
    """Do what the frame says; what is wrong with it, or None."""
    try:
        frame = json.loads(text) if text is not None else None
    except ValueError:
        frame = None
    kind = frame.get("type") if isinstance(frame, dict) else None
    if kind == "input" and isinstance(frame.get("data"), str):
        if term.mode != terminal.CONTROL:
            return "this terminal is open to view: take control to type"
        await to_thread.run_sync(term.write, frame["data"].encode())
        return None
    if kind == "resize" and _dimension(frame.get("cols")) and _dimension(frame.get("rows")):
        if term.mode != terminal.CONTROL:
            return "the size of a terminal open to view follows the agent's window"
        await to_thread.run_sync(term.resize, (frame["cols"], frame["rows"]))
        return None
    return (
        'a frame is JSON text: {"type": "input", "data": <text>} or '
        '{"type": "resize", "cols": <n>, "rows": <n>}'
    )


def _dimension(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and 1 <= value <= 1000
