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
"""

import json
import logging
import time

import anyio
from anyio import to_thread
from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect

from lado import terminal
from lado.server import feed
from lado.server.auth import Guard, Refused

DENIED, BAD_MODE, GONE = 4401, 4400, 4404  # for good
ENDED, UNAVAILABLE = 4500, 4503  # for now: open again after a pause
SIZE_EVERY = 1.0  # seconds between two looks at the window's size, in view
REASON_BYTES = 123  # the most a close frame's reason holds

log = logging.getLogger("lado.server")


async def serve(ws: WebSocket, guard: Guard, session: str, agent: str, mode: str) -> None:
    try:
        guard.check(ws, changes=True)
    except Refused as refused:
        if refused.status == 403:
            await ws.close(1008)  # before the upgrade: another page gets nothing
            return
        await _end(ws, DENIED, refused.detail)
        return
    if mode not in terminal.MODES:
        await _end(ws, BAD_MODE, f"mode is {' or '.join(terminal.MODES)}, not {mode}")
        return
    problem = await to_thread.run_sync(feed.schema_problem)
    if problem:
        await _end(ws, UNAVAILABLE, problem)
        return
    try:
        term = await to_thread.run_sync(terminal.open, session, agent, mode)
    except terminal.NoTerminal as none:
        await _end(ws, GONE, str(none))
        return
    try:
        await ws.accept()
        await ws.send_json(_size(term.size))
        await _run(ws, term)
    finally:
        with anyio.CancelScope(shield=True):  # also when the server stops
            await to_thread.run_sync(term.close)


async def _end(ws: WebSocket, code: int, reason: str) -> None:
    """Accept only to say why it ends: the browser cannot read a refused upgrade."""
    await ws.accept()
    await ws.send_json({"type": "error", "reason": reason})
    await ws.close(code, reason.encode()[:REASON_BYTES].decode(errors="ignore"))


def _size(size: tuple[int, int]) -> dict:
    return {"type": "size", "cols": size[0], "rows": size[1]}


async def _run(ws: WebSocket, term) -> None:
    ended = False

    async def out() -> None:
        nonlocal ended
        try:
            await output(ws, term)
            ended = True
        except (WebSocketDisconnect, RuntimeError, OSError):
            pass  # the browser went while output was sent
        scope.cancel()

    async def into() -> None:
        await take_input(ws, term)
        scope.cancel()

    async with anyio.create_task_group() as group:
        scope = group.cancel_scope
        group.start_soon(out)
        group.start_soon(into)
    if ended:
        why = await to_thread.run_sync(terminal.ended, term.session, term.agent)
        if why is None:
            await _close(ws, ENDED, "the terminal closed; it opens again")
        else:
            await _close(ws, GONE, str(why))


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
