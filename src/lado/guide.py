"""The web UI's first-run guide on the server (docs/design/ui.md, First-run guide): its
record in LADO_HOME/guide.json and the facts its answer carries while it is not completed.

The record is `{"completed", "shown", "tips_off"}`: whether the main guide was completed,
the ids of the hints shown (each once in LADO's lifetime, in every browser) and whether
tips are off. The ids are the guide file's (web/src/guide/hints.ts, the one list of
hints); the server checks only their shape. Changes go through one lock and an atomic
replace, and `shown` is a union, so two tabs marking different hints lose neither. A file
that cannot be read is journaled and counts as no record, never as completed.

While LADO_GUIDE=0 (`off`) a GET makes no record and computes no facts: nothing starts by
itself, for recording videos on a live LADO and for every test but the guide's own UI e2e;
Help → Getting started still writes one (`restart`).

The facts (`facts`) are whether a model is connected (a model server saved, or an agent
CLI logged in as the server's login check read it) and whether an author signs commits
(LADO's or git's own), as Settings shows them. With no record, the first answer waits up
to WAIT seconds for the first login check since the server started and makes the record
once the model is known: completed when one is connected, so a LADO set up before the
guide never sees its welcome; while it is not known (the check did not end in time, or it
failed), the answer is completed and nothing is written, and a mark made meanwhile (a
tip shown) starts from that completed record (`UNKNOWN`), never from a guide to run. A
completed guide costs one file read.
"""

import contextlib
import dataclasses
import json
import os
import re
import secrets
import threading
from collections.abc import Mapping, Sequence
from pathlib import Path

from lado import state, telemetry

ID_RE = re.compile(r"[a-z0-9-]{1,64}")
ACTIONS = ("shown", "complete", "tips_off", "restart")
WAIT = 20.0  # seconds the first answer waits for the first login check

_lock = threading.Lock()
_missing: set[str] = set()  # the hints whose missing marker was journaled, per server


@dataclasses.dataclass(frozen=True)
class Record:
    completed: bool
    shown: tuple[str, ...]
    tips_off: bool


EMPTY = Record(completed=False, shown=(), tips_off=False)
# No record yet, the model's fact unknown: the guide counts as completed.
UNKNOWN = Record(completed=True, shown=(), tips_off=False)


@dataclasses.dataclass(frozen=True)
class Facts:
    model: bool | None  # None: the first login check has not ended within WAIT
    author: bool


class Broken(ValueError):
    """guide.json is there but is not a record."""


class GuideMarkerMissing(Exception):
    """A hint's condition held, but no visible element carried its marker (the UI's
    report: `<id>: <marker>`)."""


def off(environ: Mapping[str, str] | None = None) -> bool:
    """LADO_GUIDE=0 (in `environ`, else os.environ): the guide never starts by itself."""
    return (os.environ if environ is None else environ).get("LADO_GUIDE") == "0"


def path() -> Path:
    return state.home() / "guide.json"


def read() -> Record | None:
    """The record; None with no file, or with one that cannot be read (journaled)."""
    try:
        text = path().read_text()
    except FileNotFoundError:
        return None
    except OSError as error:
        telemetry.record("guide:read", error)
        return None
    try:
        return _parse(text)
    except (ValueError, Broken) as error:
        telemetry.record("guide:read", error)
        return None


def _parse(text: str) -> Record:
    data = json.loads(text)
    if not isinstance(data, dict):
        raise Broken(f"guide.json holds a {type(data).__name__}, not an object")
    completed, shown, tips_off = (
        data.get("completed", False),
        data.get("shown", []),
        data.get("tips_off", False),
    )
    if not isinstance(completed, bool) or not isinstance(tips_off, bool):
        raise Broken("guide.json: completed and tips_off are true or false")
    if not isinstance(shown, list) or not all(isinstance(i, str) for i in shown):
        raise Broken("guide.json: shown is a list of ids")
    return Record(completed=completed, shown=tuple(shown), tips_off=tips_off)


def write(record: Record) -> None:
    """Replace the record at once: a temporary file in LADO_HOME, then os.replace."""
    target = path()
    text = json.dumps(
        {"completed": record.completed, "shown": list(record.shown), "tips_off": record.tips_off}
    )
    temporary = target.with_name(f".{target.name}.{secrets.token_hex(4)}.tmp")
    try:
        temporary.write_text(text)
        os.replace(temporary, target)
    except BaseException:
        with contextlib.suppress(OSError):
            temporary.unlink()
        raise


def change(action: str, ids: Sequence[str] = ()) -> Record:
    """Apply one of ACTIONS to the record (UNKNOWN when there is none: the first GET did
    not know the model yet) and keep it: `shown` adds `ids`, `complete` completes the main
    guide, `tips_off` turns tips off, `restart` makes it not completed with tips on, the
    shown ids kept. ValueError for an unknown action or an id not of ID_RE."""
    if action not in ACTIONS:
        raise ValueError(f"unknown action {action!r}")
    for id in ids:
        if not ID_RE.fullmatch(id):
            raise ValueError(f"not a hint's id: {id!r}")
    with _lock:
        found = read() or UNKNOWN
        if action == "shown":
            new = tuple(i for i in dict.fromkeys(ids) if i not in found.shown)
            found = dataclasses.replace(found, shown=found.shown + new)
        elif action == "complete":
            found = dataclasses.replace(found, completed=True)
        elif action == "tips_off":
            found = dataclasses.replace(found, tips_off=True)
        else:
            found = dataclasses.replace(found, completed=False, tips_off=False)
        write(found)
        return found


def facts(has_db: bool, wait: float | None = None) -> Facts:
    """Whether a model is connected and an author signs commits (`has_db`: lado.db is
    there, which is not made); the model's fact waits up to `wait` (WAIT) seconds for the
    first login check since the server started, which it starts unless one did."""
    from lado import commit_authors
    from lado.server import git_entries, provider_check

    author = (has_db and commit_authors.lado() is not None) or git_entries.git_author() is not None
    if has_db and state.model_servers():
        return Facts(model=True, author=author)
    ended = provider_check.first(WAIT if wait is None else wait)
    logged_in = any(
        row.ready and row.cli.installed and row.login.state == "yes"
        for row in provider_check.snapshot().providers
    )
    return Facts(model=True if logged_in else (False if ended else None), author=author)


def now(
    has_db: bool, environ: Mapping[str, str] | None = None
) -> tuple[bool, Record, Facts | None]:
    """What GET /api/guide answers: whether the guide may start by itself, the record, and
    the facts while it is not completed. With no record it is made once the model's fact
    is known (completed when a model is connected); until then the guide counts as
    completed and nothing is written. Under LADO_GUIDE=0 nothing is computed or made."""
    auto = not off(environ)
    found = read()
    if not auto:
        return auto, found or UNKNOWN, None
    if found is None:
        known = facts(has_db)
        if known.model is None:
            return auto, UNKNOWN, None
        found = _first(completed=known.model)
        return auto, found, None if found.completed else known
    return auto, found, None if found.completed else facts(has_db)


def _first(completed: bool) -> Record:
    """Make the record, unless another answer made it meanwhile."""
    with _lock:
        found = read()
        if found is None:
            found = dataclasses.replace(EMPTY, completed=completed)
            write(found)
        return found


def missing(id: str, marker: str) -> None:
    """Journal a marker the UI did not find, once per hint while the server runs."""
    with _lock:
        if id in _missing:
            return
        _missing.add(id)
    telemetry.record("ui:guide", GuideMarkerMissing(f"{id}: {marker}"))


def forget_missing() -> None:
    """Forget which missing markers were journaled (tests)."""
    with _lock:
        _missing.clear()
