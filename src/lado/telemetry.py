"""LADO's own errors and, with the human's yes, usage statistics for its maintainers.

Always, whatever the choice: every unexpected exception of a LADO process (a CLI command,
a hook, a tool of `lado mcp`, a pass of the session loop, a request of the UI server) is a
JSON line in LADO_HOME/errors.jsonl, kept local (`record`). LADO's logs stay bounded
(`bounded_append`, `trim`).

Only while sending is on (`State.on`: the human chose `on` for the current FIELDS, no
DO_NOT_TRACK or LADO_TELEMETRY=0, an endpoint), `record` also queues the error, scrubbed of
anything but LADO's own code (`scrub`), in LADO_HOME/telemetry/outbox/, and a detached
`lado telemetry send` (`kick`, `send`) posts the queued errors and a daily report counted
from lado.db when it is built (`report`), to PostHog (`_post`). Only that process goes to
the network; nothing waits for it and nothing shows its failure but `lado telemetry status`
and the UI's Settings. What waits is bounded (OUTBOX_MAX, OUTBOX_MAX_AGE,
REPORT_MAX_WINDOW, DROPPED_MAX).

Files under LADO_HOME/telemetry/: consent.json ({"choice", "fields", "at"}), id (the
install id), outbox/*.json (one queued error each), dropped (one byte per error the full
queue dropped), sent.json ({"report_at", "sent_at", "tried_at", "error"}), send.lock.
docs/telemetry.md lists FIELDS for the human (a test keeps both the same).

Every hook imports this module: only the standard library and lado.state at its top.
"""

import contextlib
import dataclasses
import datetime
import hashlib
import json
import os
import secrets
import time
import traceback
from collections.abc import Mapping
from pathlib import Path

from lado import state as db

JOURNAL_MAX = 1 << 20  # bytes of a log before it is rotated to <name>.1
OUTBOX_MAX = 200  # queued errors; further ones are only counted (dropped)
OUTBOX_MAX_AGE = 30 * 86400  # seconds a queued error waits before it is dropped
DROPPED_MAX = 1_000_000  # bytes of `dropped`: the count stops there
REPORT_MAX_WINDOW = 30 * 86400  # seconds a daily report counts back at most
REPORT_EVERY = 24 * 3600  # seconds between two daily reports
RETRY_AFTER = 15 * 60  # seconds between two tries of the sender
KICK_EVERY = 10 * 60  # seconds between two kicks of the session loop and the UI server
SEND_TIMEOUT = 2.0  # seconds per network operation, as update.CHECK_TIMEOUT
SEND_DEADLINE = 30  # seconds the sender's process lives at most, DNS included

# PostHog Cloud EU's batch API and LADO's project token (PostHog's "Project token",
# write-only and public by design). LADO_TELEMETRY_URL replaces the endpoint, for tests,
# with TEST_TOKEN.
ENDPOINT = "https://eu.i.posthog.com/batch/"
PROJECT_TOKEN = "phc_tid47HKogUn4hGGQRKGdMD4WWoTRrxDVpDKWxdznowDv"
TEST_TOKEN = "phc_test"

DAILY = "lado_daily"
EXCEPTION = "$exception"

# What LADO sends: each field of the daily report and of an error event, with the FIELDS
# version it came in. The human's yes covers FIELDS_VERSION; a LADO that adds a field bumps
# it, and the question comes again naming the new ones (State.new_fields).
FIELDS_VERSION = 1
FIELDS: dict[str, int] = {
    # The daily report.
    "install": 1,
    "lado": 1,
    "python": 1,
    "os": 1,
    "arch": 1,
    "installer": 1,
    "providers": 1,
    "kits": 1,
    "since": 1,
    "db": 1,
    "sessions": 1,
    "agents": 1,
    "runs": 1,
    "gates": 1,
    "turn_errors": 1,
    "lado_errors": 1,
    "errors_dropped": 1,
    # An error.
    "type": 1,
    "chain": 1,
    "stack": 1,
    "where": 1,
    "provider": 1,
    "fingerprint": 1,
    "count": 1,
    "first_at": 1,
    "last_at": 1,
}

PACKAGE = Path(__file__).resolve().parent
EXTERNAL = "<external>"


@dataclasses.dataclass(frozen=True)
class State:
    choice: str | None  # "on" | "off" | None, as stored
    chosen_at: str | None
    fields_ok: bool  # the stored yes covers FIELDS_VERSION
    off_by: str | None  # "DO_NOT_TRACK=<value>" | "LADO_TELEMETRY=0" | None
    endpoint: bool
    fields: int = 0  # the FIELDS version the stored choice was made for

    @property
    def on(self) -> bool:
        return self.choice == "on" and self.fields_ok and not self.off_by and self.endpoint

    @property
    def chosen(self) -> str | None:
        """The choice as it counts: None while not made, also a yes to older fields."""
        if self.choice == "on" and not self.fields_ok:
            return None
        return self.choice

    @property
    def ask(self) -> bool:
        return self.chosen is None and not self.off_by and self.endpoint

    @property
    def new_fields(self) -> list[str]:
        """The fields the stored yes does not cover."""
        if self.choice != "on" or self.fields_ok:
            return []
        return [name for name, since in FIELDS.items() if since > self.fields]


def folder() -> Path:
    return db.home() / "telemetry"


def journal_path() -> Path:
    return db.home() / "errors.jsonl"


def _outbox() -> Path:
    return folder() / "outbox"


def off_by(environ: Mapping[str, str]) -> str | None:
    """The variable that switches sending off, as `NAME=value`, or None."""
    dnt = environ.get("DO_NOT_TRACK", "")
    if dnt not in ("", "0"):
        return f"DO_NOT_TRACK={dnt}"
    if environ.get("LADO_TELEMETRY") == "0":
        return "LADO_TELEMETRY=0"
    return None


def _url(environ: Mapping[str, str]) -> str | None:
    if environ.get("LADO_TELEMETRY_URL"):
        return environ["LADO_TELEMETRY_URL"]
    return ENDPOINT if PROJECT_TOKEN else None


def _token(environ: Mapping[str, str]) -> str:
    return TEST_TOKEN if environ.get("LADO_TELEMETRY_URL") else PROJECT_TOKEN


def _read_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def state(environ: Mapping[str, str] | None = None) -> State:
    environ = os.environ if environ is None else environ
    stored = _read_json(folder() / "consent.json")
    choice = stored.get("choice") if stored.get("choice") in ("on", "off") else None
    fields = stored.get("fields") if isinstance(stored.get("fields"), int) else 0
    return State(
        choice=choice,
        chosen_at=stored.get("at") if choice else None,
        fields_ok=fields >= FIELDS_VERSION,
        off_by=off_by(environ),
        endpoint=_url(environ) is not None,
        fields=fields,
    )


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _iso(when: datetime.datetime) -> str:
    return when.strftime("%Y-%m-%dT%H:%M:%SZ")


def _write_atomic(path: Path, text: str, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{secrets.token_hex(4)}.tmp")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    try:
        with os.fdopen(fd, "w") as file:
            file.write(text)
        os.replace(temporary, path)
    except BaseException:
        with contextlib.suppress(OSError):
            temporary.unlink()
        raise


def choose(choice: str) -> None:
    """Keep the human's choice, for the current FIELDS; `off` also drops what is queued."""
    if choice not in ("on", "off"):
        raise ValueError(f"the choice is on or off, not {choice!r}")
    stored = {"choice": choice, "fields": FIELDS_VERSION, "at": _iso(_now())}
    _write_atomic(folder() / "consent.json", json.dumps(stored))
    if choice == "off":
        clear()


def clear() -> None:
    """Drop the queued errors and the drop count."""
    with contextlib.suppress(FileNotFoundError):
        for path in _outbox().iterdir():
            with contextlib.suppress(OSError):
                path.unlink()
    with contextlib.suppress(OSError):
        (folder() / "dropped").unlink()


def bounded_append(path: Path, text: str, limit: int | None = None, mode: int = 0o644) -> None:
    """Append `text` to `path` in one write, first renaming a file over `limit` bytes
    (JOURNAL_MAX) to `<name>.1` (replacing an older one). Never raises: a log must not break
    its writer."""
    try:
        rotate(path, limit)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, mode)
        try:
            os.write(fd, text.encode())
        finally:
            os.close(fd)
    except Exception:
        pass


def rotate(path: Path, limit: int | None = None) -> None:
    """Rename `path` to `<name>.1` (replacing an older one) when it is over `limit` bytes
    (JOURNAL_MAX). Never raises."""
    with contextlib.suppress(OSError):
        if path.stat().st_size > (JOURNAL_MAX if limit is None else limit):
            os.replace(path, path.with_name(path.name + ".1"))


def trim(path: Path, limit: int | None = None) -> None:
    """Bound a log another process keeps open with O_APPEND (the UI server's output): over
    `limit` (JOURNAL_MAX), copy it to `<name>.1` and empty it in place, so that process's
    next write lands at its new end. A line written during the copy may be lost. Never
    raises."""
    try:
        if path.stat().st_size <= (JOURNAL_MAX if limit is None else limit):
            return
        rotated = path.with_name(path.name + ".1")
        temporary = rotated.with_name(rotated.name + ".tmp")
        with open(path, "rb") as source, open(temporary, "wb") as target:
            while chunk := source.read(1 << 16):
                target.write(chunk)
        os.chmod(temporary, os.stat(path).st_mode & 0o777)
        os.replace(temporary, rotated)
        os.truncate(path, 0)
    except Exception:
        pass


def _type_name(cls: type) -> str:
    return f"{cls.__module__}.{cls.__qualname__}".removeprefix("builtins.")


def _frames(exc: BaseException) -> list[str]:
    """The traceback's frames of LADO's package, as `lado/<file>:<function>:<line>`; each run
    of other frames one EXTERNAL."""
    stack: list[str] = []
    for frame, line in traceback.walk_tb(exc.__traceback__):
        try:
            relative = Path(frame.f_code.co_filename).resolve().relative_to(PACKAGE)
        except (ValueError, OSError):
            if not stack or stack[-1] != EXTERNAL:
                stack.append(EXTERNAL)
            continue
        stack.append(f"lado/{relative.as_posix()}:{frame.f_code.co_name}:{line}")
    return stack


def fingerprint(type_: str, stack: list[str]) -> str:
    """The error's group: its type and LADO's frames by file and function, not by line, so a
    line that moves keeps the group."""
    places = [frame.rsplit(":", 1)[0] for frame in stack if frame != EXTERNAL]
    return hashlib.sha256("\n".join([type_, *places]).encode()).hexdigest()[:16]


def scrub(where: str, exc: BaseException, provider: str | None) -> dict:
    """What an error event carries: its type, its causes' types, LADO's frames, where, the
    provider, its fingerprint. Never its text, locals or arguments."""
    type_ = _type_name(type(exc))
    chain = []
    cause = exc.__cause__ or exc.__context__
    while cause is not None and len(chain) < 3:
        chain.append(_type_name(type(cause)))
        cause = cause.__cause__ or cause.__context__
    stack = _frames(exc)
    return {
        "type": type_,
        "chain": chain,
        "stack": stack,
        "where": where[:200],
        "provider": provider,
        "fingerprint": fingerprint(type_, stack),
    }


def record(
    where: str,
    exc: BaseException,
    provider: str | None = None,
    session: str | None = None,
    agent: str | None = None,
) -> None:
    """An unexpected exception of a LADO process: a line in errors.jsonl, and, while sending
    is on, a queued error event. `state.SchemaError` is the upgrade path's refusal, no error.
    Never raises."""
    if isinstance(exc, db.SchemaError):
        return
    with contextlib.suppress(Exception):
        import lado

        version = lado.__version__
        line = {
            "at": _iso(_now()),
            "lado": version,
            "where": where,
            "type": _type_name(type(exc)),
            "message": str(exc),
            "traceback": "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
            "session": session,
            "agent": agent,
        }
        bounded_append(journal_path(), json.dumps(line) + "\n", mode=0o600)
        if state().on:
            _queue({**scrub(where, exc, provider), "at": line["at"], "lado": version})


def _queue(event: dict) -> None:
    outbox = _outbox()
    outbox.mkdir(parents=True, exist_ok=True)
    if sum(1 for path in outbox.iterdir() if path.suffix == ".json") >= OUTBOX_MAX:
        _count_dropped(1)
        return
    name = f"{time.time_ns()}-{os.getpid()}-{secrets.token_hex(4)}.json"
    _write_atomic(outbox / name, json.dumps(event))


def _count_dropped(count: int) -> None:
    path = folder() / "dropped"
    with contextlib.suppress(FileNotFoundError):
        count = min(count, DROPPED_MAX - path.stat().st_size)
    count = min(count, DROPPED_MAX)
    if count <= 0:
        return
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        os.write(fd, b"x" * count)
    finally:
        os.close(fd)


def _queued_files() -> list[tuple[Path, dict]]:
    """The queued errors with their files, oldest first; a file that does not read is
    skipped (one being written is still a .tmp)."""
    try:
        paths = sorted(p for p in _outbox().iterdir() if p.suffix == ".json")
    except FileNotFoundError:
        return []
    found = []
    for path in paths:
        event = _read_json(path)
        if event:
            found.append((path, event))
    return found


def queued() -> list[dict]:
    return [event for _, event in _queued_files()]


def dropped() -> int:
    try:
        return (folder() / "dropped").stat().st_size
    except OSError:
        return 0
