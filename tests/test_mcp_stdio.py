import dataclasses
import importlib.util
import os
import subprocess
import sys
import types
from pathlib import Path

import agent_helpers

from lado import mcp_stdio, runtime, state


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
