"""The web UI's first-run guide on the server (docs/design/ui.md, First-run guide): its
record in LADO_HOME/guide.json and the facts its answer carries while it is not completed.

The record is `{"completed", "shown", "tips_off"}`: whether the main guide was completed,
the ids of the hints shown (each once in LADO's lifetime, in every browser) and whether
tips are off. The ids are the guide file's (web/src/guide/hints.ts, the one list of
hints); the server checks only their shape. Changes go through one lock and an atomic
replace, and `shown` is a union, so two tabs marking different hints lose neither. A file
that cannot be read is journaled and counts as no record, never as completed.

No record is made while LADO_GUIDE=0 (`off`): nothing starts by itself, for recording
videos on a live LADO and for every test but the guide's own UI e2e.
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

_lock = threading.Lock()


@dataclasses.dataclass(frozen=True)
class Record:
    completed: bool
    shown: tuple[str, ...]
    tips_off: bool


EMPTY = Record(completed=False, shown=(), tips_off=False)


class Broken(ValueError):
    """guide.json is there but is not a record."""


def off(environ: Mapping[str, str]) -> bool:
    """LADO_GUIDE=0: the guide never starts by itself."""
    return environ.get("LADO_GUIDE") == "0"


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
    """Apply one of ACTIONS to the record (an empty one when there is none) and keep it:
    `shown` adds `ids`, `complete` completes the main guide, `tips_off` turns tips off,
    `restart` makes it not completed with tips on, the shown ids kept. ValueError for an
    unknown action or an id not of ID_RE."""
    if action not in ACTIONS:
        raise ValueError(f"unknown action {action!r}")
    for id in ids:
        if not ID_RE.fullmatch(id):
            raise ValueError(f"not a hint's id: {id!r}")
    with _lock:
        found = read() or EMPTY
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
