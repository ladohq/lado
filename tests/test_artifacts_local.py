import hashlib
import os
import time

import pytest

from lado import artifacts, artifacts_local, state

HOUR = artifacts_local.ORPHAN_AGE


@pytest.fixture
def store(lado_home):
    for session in ("s", "t"):
        state.add_session(state.Session(session, "/r", None, provider="claude"))
    return artifacts_local.LocalStore(state.home())


def _write(store, name, data, session="s"):
    return store.write(
        session,
        "",
        name,
        data,
        "text/plain",
        author="supervisor",
        run=None,
        state=None,
        visit=None,
        summary=None,
        title=None,
    )


def _file(store, data: bytes):
    digest = hashlib.sha256(data).hexdigest()
    return store.root / digest[:2] / digest


def _age(path, seconds):
    then = time.time() - seconds
    os.utime(path, (then, then))


def test_equal_content_is_stored_once_and_a_write_refreshes_its_time(store):
    _write(store, "a", b"same")
    path = _file(store, b"same")
    _age(path, 2 * HOUR)
    written = _write(store, "b", b"same")
    assert [p.name for p in store.root.glob("*/*")] == [path.name]
    assert time.time() - path.stat().st_mtime < 60
    assert store.content(written.record.id) == b"same"
    assert (written.record.hash, written.record.size) == (path.name, 4)


def test_a_write_whose_file_a_removal_took_writes_it_again(store, monkeypatch):
    _write(store, "a", b"kept")
    path = _file(store, b"kept")
    # A removal takes the file just after this write found it there and refreshed its time.
    put = store._put

    def put_then_lose(data):
        digest = put(data)
        path.unlink()
        monkeypatch.setattr(store, "_put", put)
        return digest

    monkeypatch.setattr(store, "_put", put_then_lose)
    written = _write(store, "b", b"kept")
    assert store.content(written.record.id) == b"kept"


def test_content_missing_from_the_store_is_a_loud_error(store):
    written = _write(store, "a", b"gone")
    _file(store, b"gone").unlink()
    with pytest.raises(artifacts.ArtifactError, match="content of a is missing from the store"):
        store.content(written.record.id)


def test_removing_a_session_keeps_other_sessions_shared_content_and_new_orphans(store):
    _write(store, "only-s", b"only s")
    _write(store, "shared", b"shared")
    _write(store, "shared", b"shared", session="t")
    _write(store, "fresh", b"fresh")
    for data in (b"only s", b"shared"):
        _age(_file(store, data), 2 * HOUR)
    old_orphan = store.root / "ab" / ("ab" + "0" * 62)
    old_orphan.parent.mkdir()
    old_orphan.write_bytes(b"crash")
    _age(old_orphan, 2 * HOUR)
    assert store.remove_session("s") == 3
    assert store.list("s") == []
    assert [a.name for a, _ in store.list("t")] == ["shared"]
    assert not _file(store, b"only s").exists() and not old_orphan.exists()
    assert _file(store, b"shared").exists()
    assert _file(store, b"fresh").exists()  # no record, but not an hour old: a later forget
    store.remove_session("s")  # again: nothing left, no error
    assert _file(store, b"fresh").exists()


def test_usage_counts_artifacts_records_bytes_and_old_orphans(store):
    assert store.usage() == artifacts.Usage(0, 0, 0, 0, 0)
    _write(store, "a", b"12345")
    _write(store, "a", b"12345")
    _write(store, "b", b"123")
    orphan = store.root / "cd" / ("cd" + "0" * 62)
    orphan.parent.mkdir()
    orphan.write_bytes(b"1234567")
    young = store.root / "cd" / ("cd" + "1" * 62)
    young.write_bytes(b"12")
    _age(orphan, 2 * HOUR)
    assert store.usage() == artifacts.Usage(2, 3, 17, 1, 7)


def test_the_list_gives_each_artifact_with_its_latest_record_by_scope(store):
    _write(store, "b", b"1")
    _write(store, "a", b"1")
    latest = _write(store, "b", b"2")
    store.write(
        "s",
        "feature/x",
        "a",
        b"x",
        "text/plain",
        author="w1",
        run="feature/x",
        state="design",
        visit=1,
        summary=None,
        title=None,
    )
    listed = [(a.full_name, r.hash) for a, r in store.list("s")]
    assert listed == [
        ("a", hashlib.sha256(b"1").hexdigest()),
        ("b", latest.record.hash),
        ("feature/x/a", hashlib.sha256(b"x").hexdigest()),
    ]
    assert [a.full_name for a, _ in store.list("s", "feature/x")] == ["feature/x/a"]
