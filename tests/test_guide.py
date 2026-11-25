"""The first-run guide's record (lado.guide): LADO_HOME/guide.json, its changes, and the
facts the server answers with while the guide is not completed."""

import json
import re
import threading
from pathlib import Path

import pytest

from lado import guide, providers, state


def _journal():
    path = state.home() / "errors.jsonl"
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


def _file():
    return state.home() / "guide.json"


def test_no_file_is_no_record():
    assert guide.read() is None


def test_shown_is_a_union_across_threads():
    guide.write(guide.Record(completed=False, shown=(), tips_off=False))
    start = threading.Barrier(8)

    def mark(ids):
        start.wait()
        guide.change("shown", ids)

    threads = [threading.Thread(target=mark, args=([f"hint-{i}", "both"],)) for i in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    found = guide.read()
    assert found is not None
    assert set(found.shown) == {f"hint-{i}" for i in range(8)} | {"both"}
    assert len(found.shown) == 9  # no id twice


def test_complete_tips_off_and_restart():
    guide.write(guide.Record(completed=False, shown=("welcome",), tips_off=False))
    assert guide.change("complete").completed
    assert guide.change("tips_off").tips_off
    again = guide.change("restart")
    assert again == guide.Record(completed=False, shown=("welcome",), tips_off=False)
    assert guide.read() == again


def test_a_change_without_a_record_starts_from_an_empty_one():
    assert guide.change("shown", ["tip-launch"]) == guide.Record(False, ("tip-launch",), False)


@pytest.mark.parametrize("bad", ["", "Welcome", "a b", "x" * 65, "../etc", "tip_launch"])
def test_a_bad_id_is_refused(bad):
    with pytest.raises(ValueError):
        guide.change("shown", [bad])
    assert guide.read() is None


def test_an_unknown_action_is_refused():
    with pytest.raises(ValueError):
        guide.change("forget")


@pytest.mark.parametrize("text", ["{not json", "[]", '{"completed": "yes"}', '{"shown": [1]}'])
def test_a_broken_file_is_no_record_and_journaled(text):
    _file().write_text(text)
    assert guide.read() is None
    lines = _journal()
    assert [line["where"] for line in lines] == ["guide:read"]


def test_a_broken_file_is_replaced_by_the_next_change():
    _file().write_text("{not json")
    assert guide.change("tips_off") == guide.Record(False, (), True)
    assert json.loads(_file().read_text()) == {"completed": False, "shown": [], "tips_off": True}


def test_the_file_is_replaced_atomically(monkeypatch):
    guide.write(guide.Record(completed=False, shown=(), tips_off=False))
    replaced = []
    real = guide.os.replace

    def spy(source, target):
        replaced.append((source, target))
        real(source, target)

    monkeypatch.setattr(guide.os, "replace", spy)
    guide.change("complete")
    [(source, target)] = replaced
    assert str(target) == str(_file())
    assert str(source).startswith(str(state.home())) and str(source) != str(target)
    assert not [p for p in state.home().iterdir() if p.name.endswith(".tmp")]


def test_the_guides_providers_are_the_servers():
    """Each provider whose row the UI's guide has texts for (web/src/guide/hints.ts, `cli:`)
    is one LADO knows by that name."""
    hints = Path(__file__).parent.parent / "web" / "src" / "guide" / "hints.ts"
    named = re.findall(r'^\s*cli: "([a-z0-9-]+)",$', hints.read_text(), re.M)
    assert named == ["claude", "codex"]
    assert set(named) <= set(providers.names())


def test_off_reads_lado_guide():
    assert guide.off({"LADO_GUIDE": "0"})
    assert not guide.off({"LADO_GUIDE": "1"})
    assert not guide.off({})
