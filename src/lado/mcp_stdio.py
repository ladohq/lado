"""The process of an agent's LADO MCP server (`lado mcp`), lean so that it starts fast.

It imports the standard library and lado.state only; lado.mcp_server and with it the MCP
SDK, whose import is almost all of the server's start, load meanwhile. Until the SDK is up
the front answers the client's `initialize` and its lists of tools, prompts and resources
(without a cursor) from a cache of the SDK's own answers to the same requests (`Front`);
everything else, and everything once the SDK is up, the SDK answers as without the front.
"""

import contextlib
import fcntl
import hashlib
import importlib.util
import json
import os
import queue
import sys
import tempfile
import threading
import traceback
from collections.abc import Callable
from pathlib import Path
from typing import BinaryIO

from lado import state

SUPERVISOR = "supervisor"  # the lead's agent name (lado.runtime.SUPERVISOR)

# The cache of the SDK's answers: what makes them is the server's code (its tools and their
# docstrings), the SDK and pydantic installed, and the agent's tool set.
SERVER_CODE = Path(__file__).with_name("mcp_server.py")
PACKAGES = ("mcp", "mcp_types", "pydantic")
CACHE_FILES = 20  # the newest kept in the cache's folder


def tool_set(me: state.Agent | None) -> str:
    """Which tools the agent's server has (lado.mcp_server.build): none of the agent's own
    without its row, a worker's, or the supervisor's, each read-only or not."""
    if me is None:
        return "none"
    if me.name == SUPERVISOR:
        return "read-only-supervisor" if me.read_only else "supervisor"
    return "read-only" if me.read_only else "worker"


def instructions(session: str, agent: str) -> str:
    """The server's instructions to the agent's CLI."""
    return f'You are agent "{agent}" in LADO session "{session}".'


def cache_key(tools: str) -> str:
    """The key of the SDK's answers to a server of the tool set `tools`. A package is told
    by its `__init__.py`'s path, size and mtime, found without importing it or reading its
    metadata (importlib.metadata alone costs the start 0.02 s)."""
    key = hashlib.sha256(SERVER_CODE.read_bytes())
    for name in PACKAGES:
        spec = importlib.util.find_spec(name)
        origin = spec.origin if spec else None
        if origin:
            found = os.stat(origin)
            key.update(f"\0{name}\0{origin}\0{found.st_size}\0{found.st_mtime_ns}".encode())
        else:
            key.update(f"\0{name}\0missing".encode())
    key.update(f"\0{tools}".encode())
    return key.hexdigest()


def _cache_folder() -> Path:
    return state.home() / "mcp-cache"


def read_cache(key: str) -> dict[str, dict]:
    """The cached answers of `key`, by the protocol version the client asked for: each the
    result of `initialize` (without its instructions) and of the list methods the SDK
    answered. A file that is not there or not such a mapping is no answers."""
    try:
        entry = json.loads((_cache_folder() / f"{key}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(entry, dict) or not all(isinstance(v, dict) for v in entry.values()):
        return {}
    return entry


def write_cache(key: str, entry: dict[str, dict]) -> None:
    """Write `key`'s answers whole (agents start in parallel: a reader sees the old file or
    the new one), then remove all but the CACHE_FILES newest files."""
    folder = _cache_folder()
    folder.mkdir(exist_ok=True)
    handle, temp = tempfile.mkstemp(dir=folder, prefix=f".{key}.", suffix=".tmp")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as file:
            json.dump(entry, file)
        os.replace(temp, folder / f"{key}.json")
    except BaseException:
        Path(temp).unlink(missing_ok=True)
        raise
    files = sorted(folder.glob("*.json"), key=_mtime, reverse=True)
    for old in files[CACHE_FILES:]:
        old.unlink(missing_ok=True)


def _mtime(path: Path) -> int:
    try:
        return path.stat().st_mtime_ns
    except OSError:  # removed by another agent's write meanwhile
        return 0


# What the front answers from the cache: their answers depend on the server's code, the SDK
# and the tool set only. A list with a cursor (a next page) is the SDK's.
LISTS = ("tools/list", "prompts/list", "resources/list", "resources/templates/list")
CHECK = "lado-check-"  # the ids of the front's own requests to the SDK


class CacheMismatch(RuntimeError):
    """The SDK answered otherwise than the cache had it: a cause of its answers the cache's
    key misses."""


def _load_server():
    from lado import mcp_server

    return mcp_server


def _die(code: int) -> None:
    sys.stderr.flush()
    os._exit(code)  # the main thread may wait on the SDK, which waits on this thread


def _message(line: bytes) -> dict | None:
    try:
        message = json.loads(line)
    except ValueError:
        return None
    return message if isinstance(message, dict) else None


def _line(message: dict) -> bytes:
    return json.dumps(message, ensure_ascii=False, separators=(",", ":")).encode() + b"\n"


def _id(message: dict) -> str | None:
    """A request's or an answer's id as a key: 1 and "1" are two ids."""
    return json.dumps(message["id"]) if message.get("id") is not None else None


def _write_all(fd: int, data: bytes) -> None:
    view = memoryview(data)
    while view:
        view = view[os.write(fd, view) :]


class Front:
    """The server's stdin and stdout, the SDK behind two pipes.

    A reader thread takes the client's lines. Until the SDK is up it answers `initialize`
    and each of LISTS without a cursor from the cache, when the cache has them, and keeps
    every other line, and the `initialize` too, for the SDK. Once the main thread has
    loaded and built the server (`load`, lado.mcp_server) the SDK gets those lines in the
    order the client sent them, then a request of the front's own (CHECK) for each list it
    answered, then every line as it comes. A writer thread passes the SDK's lines on to the
    client but its answers to what the front answered, and takes the cache's answers from
    them: a missing one is written to the cache, one that differs from the cache's replaces
    it and is journaled (`mcp:cache`), once a process; the client gets nothing more (the
    server says `listChanged: false`). A client whose first message is not `initialize` is
    the SDK's alone.

    `mcp_ready` is recorded once: by the front when it answers the first `tools/list`, and
    then the server is built without the launch's instance; else by the server's
    `list_tools`. A failure of a thread of the front is journaled (`mcp:stdio`) and ends
    the process (`die`): the client never waits on a dead thread."""

    def __init__(
        self,
        session: str,
        agent: str,
        instance: str,
        wire_in: BinaryIO,
        wire_out: BinaryIO,
        load: Callable = _load_server,
        die: Callable[[int], object] = _die,
    ):
        self._agent = (session, agent)
        self._instance = instance
        self._in, self._out = wire_in, wire_out
        self._load, self._die = load, die
        # The lock of the front's state, and of the moment the SDK takes over; the second
        # of the wire to the client, one line at a time. Taken in that order, if both.
        self._lock = threading.Lock()
        self._out_lock = threading.Lock()
        self._backlog: list[bytes | None] = []  # the SDK's lines until it is up; None: EOF
        self._to_sdk: queue.Queue[bytes | None] = queue.Queue()  # once it is up
        self._up = False
        self._on: bool | None = None  # by the client's first message: is it `initialize`
        self._key: str | None = None  # None: no cache this time
        self._entry: dict[str, dict] = {}
        self._version: str | None = None  # the protocol version the client asked for
        self._greeted = False  # the front answered `initialize`
        self._served: list[str] = []  # the LISTS the front answered
        self._answered: dict[str, str] = {}  # the SDK's answers to drop: id -> method
        self._asked: dict[str, str] = {}  # the SDK's answers to cache: id -> method
        self._ready = False  # the front recorded mcp_ready
        self._journaled = False
        self._gone = False  # the client closed the wire

    def run(self) -> int:
        """Serve until the client's input ends; an error of the SDK's load, its build or
        its run is raised (`lado mcp` then ends with its traceback)."""
        threading.Thread(target=self._guarded, args=(self._read,), daemon=True).start()
        server = self._load()
        sdk_in, front_to_sdk = os.pipe()
        sdk_to_front, sdk_out = os.pipe()
        session, agent = self._agent
        with self._lock:
            built = server.build(session, agent, "" if self._ready else self._instance)
            self._up = True
            for line in self._backlog:
                if line is not None:
                    self._to_sdk.put(line)
            for n, method in enumerate(self._served, 1):
                check = {"jsonrpc": "2.0", "id": f"{CHECK}{n}", "method": method}
                self._answered[_id(check)] = method
                self._to_sdk.put(_line(check))
            if None in self._backlog:
                self._to_sdk.put(None)
        args = (self._feed, front_to_sdk)
        threading.Thread(target=self._guarded, args=args, daemon=True).start()
        args = (self._write, os.fdopen(sdk_to_front, "rb"))
        writer = threading.Thread(target=self._guarded, args=args, daemon=True)
        writer.start()
        server.serve(built, os.fdopen(sdk_in, "rb"), os.fdopen(sdk_out, "wb"))
        writer.join()
        with self._out_lock, contextlib.suppress(OSError):
            self._out.close()
        return 0

    def _guarded(self, work: Callable, *args) -> None:
        try:
            work(*args)
        except BaseException as error:
            traceback.print_exc()
            from lado import telemetry

            session, agent = self._agent
            telemetry.record("mcp:stdio", error, session=session, agent=agent)
            self._die(1)

    def _read(self) -> None:
        self._prepare()
        for line in iter(self._in.readline, b""):
            self._take(line)
        with self._lock:
            self._for_sdk(None)

    def _prepare(self) -> None:
        session, agent = self._agent
        try:
            try:
                me = state.get_agent(session, agent)
            except state.SchemaError:
                me = None  # as in lado.mcp_server.build
            key = cache_key(tool_set(me))
            entry = read_cache(key)
        except Exception as error:  # no cache this time; the SDK answers all
            self._journal(error)
            return
        with self._lock:
            self._key, self._entry = key, entry

    def _for_sdk(self, line: bytes | None) -> None:
        if self._up:
            self._to_sdk.put(line)
        else:
            self._backlog.append(line)

    def _take(self, line: bytes) -> None:
        message = _message(line)
        with self._lock:
            if self._on is None:
                self._on = message is not None and message.get("method") == "initialize"
            if not self._on or message is None:
                self._for_sdk(line)
                return
            method, id = message.get("method"), _id(message)
            params = message.get("params")
            params = params if isinstance(params, dict) else {}
            reply = None
            if id is not None and method == "initialize" and self._version is None:
                version = params.get("protocolVersion")
                self._version = version if isinstance(version, str) else ""
                cached = self._cached(method)
                if cached is not None:
                    reply = {**cached, "instructions": instructions(*self._agent)}
                    self._answered[id] = method
                    self._greeted = True
                else:
                    self._asked[id] = method
                self._for_sdk(line)  # the SDK is initialized by the client's own request
            elif id is not None and method in LISTS and "cursor" not in params:
                cached = self._cached(method) if self._greeted else None
                if cached is not None:
                    reply = cached
                    if method not in self._served:
                        self._served.append(method)
                    if method == "tools/list":
                        self._record_ready()
                else:
                    self._asked[id] = method
                    self._for_sdk(line)
            else:
                self._for_sdk(line)
            if reply is not None:
                self._wire(_line({"jsonrpc": "2.0", "id": message["id"], "result": reply}))

    def _cached(self, method: str) -> dict | None:
        """The cache's answer, while the front answers: until the SDK is up."""
        if self._up or self._key is None or not self._version:
            return None
        answer = self._entry.get(self._version, {}).get(method)
        return answer if isinstance(answer, dict) else None

    def _record_ready(self) -> None:
        session, agent = self._agent
        if self._instance and not self._ready:
            try:
                state.add_event(session, agent, state.MCP_READY, self._instance)
            except state.SchemaError:
                pass  # nothing is recorded; each tool call then says why (lado.mcp_server)
        self._ready = True

    def _wire(self, line: bytes) -> None:
        with self._out_lock:
            if self._gone:
                return
            try:
                self._out.write(line)
                self._out.flush()
            except BrokenPipeError:
                self._gone = True  # the SDK ends at the end of the client's input

    def _feed(self, fd: int) -> None:
        try:
            while (line := self._to_sdk.get()) is not None:
                _write_all(fd, line if line.endswith(b"\n") else line + b"\n")
        except BrokenPipeError:
            pass  # the SDK ended
        finally:
            os.close(fd)

    def _write(self, sdk: BinaryIO) -> None:
        with sdk:
            for line in sdk:
                if self._passes(line):
                    self._wire(line)

    def _passes(self, line: bytes) -> bool:
        """Whether the SDK's line goes to the client; takes the cache's answers from it."""
        message = _message(line)
        if message is None or "method" in message or (id := _id(message)) is None:
            return True  # a request or notification of the SDK's own
        with self._lock:
            given = id in self._answered
            method = self._answered.pop(id, None) or self._asked.pop(id, None)
            learned = self._learn(method, message, given) if method else None
        if learned:
            entry, contradicted = learned
            try:
                write_cache(self._key, entry)
            except Exception as error:
                self._journal(error)
            if contradicted:
                self._journal(CacheMismatch(f"the SDK's answer to {method} is not the cache's"))
        return not given

    def _learn(self, method: str, message: dict, given: bool) -> tuple[dict, bool] | None:
        """The cache's entry with the SDK's answer to `method`, and whether it contradicts
        the cache's; None when it holds that answer already."""
        if self._key is None or not self._version:
            return None
        result = message.get("result")
        if not isinstance(result, dict):  # an error
            if not given:
                return None
            # The front answered what the SDK refuses: none of the version's answers holds.
            self._entry.pop(self._version, None)
            return self._entry, True
        if method == "initialize":
            result = {k: v for k, v in result.items() if k != "instructions"}
        answers = self._entry.setdefault(self._version, {})
        cached = answers.get(method)
        if cached == result:
            return None
        answers[method] = result
        return self._entry, cached is not None

    def _journal(self, error: Exception) -> None:
        if self._journaled:
            return
        self._journaled = True
        from lado import telemetry

        session, agent = self._agent
        telemetry.record("mcp:cache", error, session=session, agent=agent)


def claim_stdio() -> tuple[BinaryIO, BinaryIO]:
    """The client's input and the wire to it, the front's alone. fd 0 then reads the null
    device and fd 1 writes to stderr, as the SDK's stdio_server leaves them, so that a
    tool's child process neither takes the client's input nor writes onto the wire."""
    wire_in = fcntl.fcntl(0, fcntl.F_DUPFD_CLOEXEC, 3)
    wire_out = fcntl.fcntl(1, fcntl.F_DUPFD_CLOEXEC, 3)
    null = os.open(os.devnull, os.O_RDONLY)
    os.dup2(null, 0)
    os.close(null)
    os.dup2(2, 1)
    return os.fdopen(wire_in, "rb"), os.fdopen(wire_out, "wb")


def main() -> int:
    session, agent = os.environ.get("LADO_SESSION"), os.environ.get("LADO_AGENT")
    if not session or not agent:
        raise SystemExit("lado mcp is started by LADO agents; LADO_SESSION/LADO_AGENT not set")
    wire_in, wire_out = claim_stdio()
    return Front(session, agent, os.environ.get("LADO_INSTANCE", ""), wire_in, wire_out).run()


if __name__ == "__main__":
    # The module's own copy, not a second one under __main__: lado.mcp_server imports it.
    from lado import mcp_stdio

    sys.exit(mcp_stdio.main())
