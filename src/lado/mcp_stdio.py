"""The process of an agent's LADO MCP server (`lado mcp`), lean so that it starts fast.

It imports the standard library and lado.state only; lado.mcp_server and with it the MCP
SDK, whose import is almost all of the server's start, load later.
"""

import hashlib
import importlib.util
import json
import os
import tempfile
from pathlib import Path

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
