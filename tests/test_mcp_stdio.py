import dataclasses
import importlib.util
import io
import json
import os
import queue
import subprocess
import sys
import threading
import time
import types
from pathlib import Path

import agent_helpers
import pytest

from lado import mcp_server, mcp_stdio, runtime, state, telemetry


def _modules_after(code: str) -> set[str]:
    """The modules a fresh Python has loaded after `code`."""
    shown = f"{code}; import sys; print(' '.join(sys.modules))"
    done = subprocess.run([sys.executable, "-c", shown], capture_output=True, text=True, check=True)
    return set(done.stdout.split())


def test_the_tool_set_is_what_the_agent_s_row_says(repo, fake_tmux):
    runtime.start_session(str(repo), "s", None, provider="claude")
    runtime.spawn_worker("s", "task", name="w1")
    agent_helpers.forget_tasks("s")
    lead, worker = state.get_agent("s", "supervisor"), state.get_agent("s", "w1")
    assert mcp_stdio.tool_set(None) == "none"
    assert mcp_stdio.tool_set(worker) == "worker"
    assert mcp_stdio.tool_set(dataclasses.replace(worker, read_only=True)) == "read-only"
    assert mcp_stdio.tool_set(lead) == "supervisor"
    lead_read_only = dataclasses.replace(lead, read_only=True)
    assert mcp_stdio.tool_set(lead_read_only) == "read-only-supervisor"


def test_the_supervisor_s_name_is_the_runtime_s():
    """mcp_stdio does not import lado.runtime: it costs the server's start 0.05 s."""
    assert mcp_stdio.SUPERVISOR == runtime.SUPERVISOR


def test_the_instructions_name_the_agent_and_its_session():
    assert mcp_stdio.instructions("s", "w1") == 'You are agent "w1" in LADO session "s".'


def _fake_packages(tmp_path, monkeypatch):
    """Each package of the key an `__init__.py` of its own in tmp_path, found without an
    import, as mcp_stdio finds the real ones."""
    inits = {}
    for name in mcp_stdio.PACKAGES:
        inits[name] = tmp_path / name / "__init__.py"
        inits[name].parent.mkdir()
        inits[name].write_text("")
    found = {name: types.SimpleNamespace(origin=str(path)) for name, path in inits.items()}
    monkeypatch.setattr(importlib.util, "find_spec", found.get)
    return inits


def test_the_cache_key_changes_with_the_server_s_code_the_packages_and_the_tool_set(
    tmp_path, monkeypatch
):
    inits = _fake_packages(tmp_path, monkeypatch)
    code = tmp_path / "mcp_server.py"
    code.write_text("one")
    monkeypatch.setattr(mcp_stdio, "SERVER_CODE", code)
    keys = {mcp_stdio.cache_key("worker")}
    assert mcp_stdio.cache_key("worker") in keys  # the same parts, the same key
    keys.add(mcp_stdio.cache_key("supervisor"))
    code.write_text("two")
    keys.add(mcp_stdio.cache_key("worker"))
    for name in mcp_stdio.PACKAGES:
        inits[name].write_text(f"# {name} upgraded")
        keys.add(mcp_stdio.cache_key("worker"))
    assert len(keys) == 6


def test_the_cache_key_reads_no_package_s_metadata_and_imports_no_package():
    """importlib.metadata alone costs the start 0.02 s."""
    loaded = _modules_after("from lado import mcp_stdio; mcp_stdio.cache_key('worker')")
    assert not {"importlib.metadata", "mcp", "mcp_types", "pydantic"} & loaded


def test_a_missing_or_invalid_cache_file_is_a_miss(tmp_path):
    assert mcp_stdio.read_cache("k") == {}
    folder = state.home() / "mcp-cache"
    folder.mkdir()
    (folder / "k.json").write_text("{not json")
    assert mcp_stdio.read_cache("k") == {}
    (folder / "k.json").write_text("[1, 2]")
    assert mcp_stdio.read_cache("k") == {}
    (folder / "k.json").write_text('{"2025-06-18": []}')
    assert mcp_stdio.read_cache("k") == {}


def test_a_cache_entry_holds_the_answers_of_each_protocol_version(tmp_path):
    entry = {
        "2025-06-18": {
            "initialize": {"protocolVersion": "2025-06-18"},
            "tools/list": {"tools": []},
        },
        "2025-11-25": {"initialize": {"protocolVersion": "2025-11-25"}},
    }
    mcp_stdio.write_cache("k", entry)
    assert mcp_stdio.read_cache("k") == entry
    assert [p.name for p in (state.home() / "mcp-cache").iterdir()] == ["k.json"]  # no temp


def test_a_cache_write_replaces_the_file_whole(tmp_path, monkeypatch):
    """Agents start in parallel: a reader sees the old file or the new one, never a part."""
    replaced = []
    real = os.replace
    monkeypatch.setattr(os, "replace", lambda a, b: (replaced.append(Path(b).name), real(a, b)))
    mcp_stdio.write_cache("k", {"v": {"initialize": {}}})
    assert replaced == ["k.json"]


def test_the_cache_keeps_its_newest_files(tmp_path):
    folder = state.home() / "mcp-cache"
    for n in range(mcp_stdio.CACHE_FILES + 3):
        mcp_stdio.write_cache(f"k{n}", {"v": {"initialize": {}}})
        os.utime(folder / f"k{n}.json", ns=(n * 10**9, n * 10**9))
    mcp_stdio.write_cache("last", {"v": {"initialize": {}}})
    kept = {p.stem for p in folder.iterdir()}
    newest = {f"k{n}" for n in range(4, mcp_stdio.CACHE_FILES + 3)}
    assert kept == newest | {"last"}


def test_the_front_imports_neither_the_sdk_nor_lado_s_heavy_modules():
    loaded = _modules_after("import lado.mcp_stdio")
    assert not {"mcp", "mcp_types", "pydantic", "lado.mcp_server", "lado.runtime"} & loaded


def test_the_sdk_s_server_still_has_the_private_server_the_front_runs():
    """MCPServer.run_stdio_async runs it; the front does the same on its own streams
    (mcp_server.serve). The SDK is pinned below 3: this fails first when it goes."""
    assert hasattr(mcp_server.build("s", "a"), "_lowlevel_server")


VERSION = "2025-06-18"
INITIALIZE = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": VERSION,
        "capabilities": {},
        "clientInfo": {"name": "test", "version": "1"},
    },
}
INITIALIZED = {"jsonrpc": "2.0", "method": "notifications/initialized"}


def _request(id, method, params=None):
    return {"jsonrpc": "2.0", "id": id, "method": method, **({"params": params} if params else {})}


class _Loader:
    """The SDK's load, held until `go` is set: what the front answers meanwhile is its own."""

    def __init__(self, go=True):
        self.go = threading.Event()
        if go:
            self.go.set()

    def __call__(self):
        assert self.go.wait(10), "never let go"
        return mcp_server


class _Client:
    """A client of a front that runs in a thread, over two pipes."""

    def __init__(self, loader, agent="supervisor", instance="abc"):
        front_in, to_front = os.pipe()
        from_front, front_out = os.pipe()
        self._to_front, self._from_front = os.fdopen(to_front, "w"), os.fdopen(from_front)
        self.code = queue.Queue()
        self.front = mcp_stdio.Front(
            "s",
            agent,
            instance,
            os.fdopen(front_in, "rb"),
            os.fdopen(front_out, "wb"),
            load=loader,
            die=self.code.put,  # not the test's process
        )
        self._received = queue.Queue()
        threading.Thread(target=self._run, daemon=True).start()
        threading.Thread(target=self._receive, daemon=True).start()

    def _run(self):
        try:
            self.code.put(self.front.run())
        except BaseException as error:
            self.code.put(error)

    def _receive(self):
        for line in self._from_front:
            self._received.put(json.loads(line))
        self._received.put(None)

    def send(self, *messages):
        for message in messages:
            self._to_front.write(json.dumps(message) + "\n")
        self._to_front.flush()

    def receive(self, timeout=10):
        return self._received.get(timeout=timeout)

    def nothing_yet(self):
        """Nothing is sent to the client within a moment."""
        with pytest.raises(queue.Empty):
            self._received.get(timeout=0.3)
        return True

    def close(self):
        """End the client's input; the rest the front sends, until it ends, and its code."""
        self._to_front.close()
        rest = []
        while (message := self.receive()) is not None:
            rest.append(message)
        return rest, self.code.get(timeout=10)


def _cold(agent="supervisor"):
    """A first start: the SDK answers the handshake and the tools, and the cache keeps them."""
    client = _Client(_Loader(), agent)
    client.send(INITIALIZE, INITIALIZED, _request(2, "tools/list"))
    answers = [client.receive(), client.receive()]
    assert client.close() == ([], 0)
    return answers


def _ready(instance="abc"):
    return [e for e in state.list_events("s") if (e.kind, e.detail) == (state.MCP_READY, instance)]


@pytest.fixture
def session(repo, fake_tmux):
    runtime.start_session(str(repo), "s", None, provider="claude")
    runtime.spawn_worker("s", "task", name="w1")
    agent_helpers.forget_tasks("s")
    with state.connect() as db:
        db.execute("DELETE FROM events WHERE kind = ?", (state.MCP_READY,))


def _entry(agent="supervisor"):
    key = mcp_stdio.cache_key(mcp_stdio.tool_set(state.get_agent("s", agent)))
    return key, mcp_stdio.read_cache(key)


def test_a_cold_start_is_served_by_the_sdk_and_fills_the_cache(session):
    initialized, tools = _cold()
    assert initialized["id"] == 1 and initialized["result"]["protocolVersion"] == VERSION
    assert initialized["result"]["instructions"] == mcp_stdio.instructions("s", "supervisor")
    assert tools["id"] == 2 and "spawn_worker" in {t["name"] for t in tools["result"]["tools"]}
    _, entry = _entry()
    without_instructions = dict(initialized["result"])
    del without_instructions["instructions"]
    assert entry == {VERSION: {"initialize": without_instructions, "tools/list": tools["result"]}}
    assert len(_ready()) == 1  # the SDK's list_tools recorded it


def test_a_warm_start_answers_the_handshake_and_the_tools_before_the_sdk_loads(session):
    initialized, tools = _cold()
    with state.connect() as db:
        db.execute("DELETE FROM events WHERE kind = ?", (state.MCP_READY,))
    loader = _Loader(go=False)
    client = _Client(loader)
    client.send(INITIALIZE)
    assert client.receive() == initialized
    client.send(INITIALIZED, _request(2, "tools/list"))
    assert client.receive() == tools
    assert len(_ready()) == 1  # by the front, before the SDK
    client.send(_request(3, "tools/call", {"name": "list_agents", "arguments": {}}))
    assert client.nothing_yet()  # a tool call waits for the SDK
    loader.go.set()
    called = client.receive()
    assert called["id"] == 3 and "result" in called
    client.send(_request(4, "tools/list"))  # the SDK's now, and it records nothing more
    assert client.receive() == {**tools, "id": 4}
    # One answer per request: the SDK's to the replayed initialize is not passed on.
    assert client.close() == ([], 0)
    assert len(_ready()) == 1


def test_a_worker_is_not_answered_from_the_supervisor_s_entry(session):
    _cold("supervisor")
    loader = _Loader(go=False)
    client = _Client(loader, agent="w1")
    client.send(INITIALIZE)
    assert client.nothing_yet()
    loader.go.set()
    assert client.receive()["result"]["instructions"] == mcp_stdio.instructions("s", "w1")
    client.send(INITIALIZED, _request(2, "tools/list"))
    assert "spawn_worker" not in {t["name"] for t in client.receive()["result"]["tools"]}
    assert client.close() == ([], 0)


def test_the_front_does_not_answer_a_list_with_a_cursor_or_another_request(session):
    _cold()
    loader = _Loader(go=False)
    client = _Client(loader)
    client.send(INITIALIZE)
    client.receive()
    client.send(INITIALIZED, _request(2, "tools/list", {"cursor": "next"}), _request(3, "ping"))
    assert client.nothing_yet()
    loader.go.set()
    assert {client.receive()["id"], client.receive()["id"]} == {2, 3}
    assert client.close() == ([], 0)


def test_a_client_that_starts_without_the_handshake_is_the_sdk_s_alone(session):
    _cold()
    loader = _Loader(go=False)
    client = _Client(loader)
    client.send(_request(2, "tools/list"), INITIALIZE)
    assert client.nothing_yet()
    loader.go.set()
    assert {client.receive()["id"], client.receive()["id"]} == {1, 2}
    assert client.close() == ([], 0)


def test_another_protocol_version_is_the_sdk_s_and_is_cached_on_its_own(session):
    _cold()
    other = {**INITIALIZE, "params": {**INITIALIZE["params"], "protocolVersion": "2025-03-26"}}
    loader = _Loader(go=False)
    client = _Client(loader)
    client.send(other)
    assert client.nothing_yet()
    loader.go.set()
    assert client.receive()["result"]["protocolVersion"] == "2025-03-26"
    assert client.close() == ([], 0)
    assert set(_entry()[1]) == {VERSION, "2025-03-26"}


def test_a_cached_answer_the_sdk_contradicts_is_replaced_and_journaled_once(session, monkeypatch):
    _, tools = _cold()
    key, entry = _entry()
    edited = {"tools": [{"name": "edited", "inputSchema": {"type": "object"}}]}
    entry[VERSION]["tools/list"] = edited
    entry[VERSION]["initialize"]["serverInfo"]["name"] = "edited"
    mcp_stdio.write_cache(key, entry)
    journaled = []
    monkeypatch.setattr(telemetry, "record", lambda where, exc, **_: journaled.append(where))
    loader = _Loader(go=False)
    client = _Client(loader)
    client.send(INITIALIZE, INITIALIZED, _request(2, "tools/list"))
    client.receive()
    assert client.receive() == {"jsonrpc": "2.0", "id": 2, "result": edited}
    loader.go.set()
    deadline = time.monotonic() + 10
    while _entry()[1][VERSION]["tools/list"] != tools["result"]:
        assert time.monotonic() < deadline, "the SDK's tools never replaced the cached ones"
        time.sleep(0.02)
    # Nothing more to the client: no notification, no second answer.
    assert client.close() == ([], 0)
    assert journaled == ["mcp:cache"]
    assert _entry()[1][VERSION]["initialize"]["serverInfo"]["name"] == "lado"


def test_a_failing_load_ends_the_front_with_its_error(session):
    def load():
        raise ImportError("no mcp")

    client = _Client(load)
    client.send(INITIALIZE)
    assert isinstance(client.code.get(timeout=10), ImportError)  # raised by run, as by main


def test_a_failure_of_the_front_s_threads_is_journaled_and_ends_the_process(session, monkeypatch):
    journaled, ended = [], queue.Queue()
    monkeypatch.setattr(telemetry, "record", lambda where, exc, **_: journaled.append(where))

    class Broken(io.BytesIO):
        def readline(self, *_):
            raise RuntimeError("broken")

    front = mcp_stdio.Front(
        "s", "supervisor", "abc", Broken(), io.BytesIO(), load=_Loader(False), die=ended.put
    )
    threading.Thread(target=front.run, daemon=True).start()
    assert ended.get(timeout=10) == 1
    assert journaled == ["mcp:stdio"]


def test_the_front_owns_the_process_s_stdin_and_stdout():
    """As the SDK's stdio_server does: a tool's child process reads no input of the client
    and writes nothing onto the wire."""
    code = (
        "import os; from lado import mcp_stdio; wire_in, wire_out = mcp_stdio.claim_stdio(); "
        "os.write(1, b'stray'); assert os.read(0, 9) == b''; "
        "wire_out.write(wire_in.readline()); wire_out.flush()"
    )
    done = subprocess.run(
        [sys.executable, "-c", code], input=b"line\n", capture_output=True, check=True
    )
    assert (done.stdout, done.stderr) == (b"line\n", b"stray")
