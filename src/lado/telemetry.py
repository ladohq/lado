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
PROVIDERS_WAIT = 5.0  # of SEND_DEADLINE, the seconds the agent CLIs' --version get in all

# PostHog Cloud EU's batch API and the token of LADO's project there, 304141 (PostHog's
# "Project token", write-only and public by design). The token must be of a project in
# the endpoint's region: `/batch/` takes another region's token and drops its events.
# scripts/check_telemetry.py checks the pair at each release. LADO_TELEMETRY_URL replaces
# the endpoint, for tests, with TEST_TOKEN.
ENDPOINT = "https://eu.i.posthog.com/batch/"
PROJECT_TOKEN = "phc_rFSHMWjPbkNL8t5n2pAMCmvMXKHgxct6VPMkfYxbNhUa"
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


def now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)


def format_time(when: datetime.datetime) -> str:
    """UTC, as every time LADO keeps here and sends: `YYYY-MM-DDTHH:MM:SSZ`."""
    return when.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_time(text: object) -> datetime.datetime | None:
    """A time of format_time, None for anything else."""
    if not isinstance(text, str):
        return None
    try:
        return datetime.datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=datetime.timezone.utc
        )
    except ValueError:
        return None


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
    stored = {"choice": choice, "fields": FIELDS_VERSION, "at": format_time(now())}
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
        line = _journal(where, exc, session, agent)
        if state().on:
            _queue({**scrub(where, exc, provider), "at": line["at"], "lado": line["lado"]})


def _journal(
    where: str, exc: BaseException, session: str | None = None, agent: str | None = None
) -> dict:
    """Append the exception's line to errors.jsonl; the line."""
    import lado

    line = {
        "at": format_time(now()),
        "lado": lado.__version__,
        "where": where,
        "type": _type_name(type(exc)),
        "message": str(exc),
        "traceback": "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
        "session": session,
        "agent": agent,
    }
    bounded_append(journal_path(), json.dumps(line) + "\n", mode=0o600)
    return line


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
    count = min(count, DROPPED_MAX - dropped())  # the count stops at DROPPED_MAX
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


def _journal_only(where: str, exc: BaseException) -> None:
    """A journal line and nothing queued: the sender's own failure, so a broken sender
    cannot feed itself."""
    with contextlib.suppress(Exception):
        _journal(where, exc)


# What was sent and tried: sent.json.


def _sent_path() -> Path:
    return folder() / "sent.json"


def _update_sent(**fields) -> None:
    _write_atomic(_sent_path(), json.dumps({**_read_json(_sent_path()), **fields}))


def last_sent() -> tuple[str | None, str | None]:
    """When the last send went through, and why the last try failed (None when it did
    not)."""
    sent = _read_json(_sent_path())
    return sent.get("sent_at"), sent.get("error")


def _seconds_since(text: object, current: datetime.datetime) -> float | None:
    when = parse_time(text)
    return None if when is None else (current - when).total_seconds()


def _report_due(sent: dict, current: datetime.datetime) -> bool:
    since = _seconds_since(sent.get("report_at"), current)
    return since is None or since >= REPORT_EVERY


def _tried_lately(sent: dict, current: datetime.datetime) -> bool:
    since = _seconds_since(sent.get("tried_at"), current)
    return since is not None and 0 <= since < RETRY_AFTER


# The daily report: counted from lado.db when it is built, never stored.


def _install_id() -> str:
    path = folder() / "id"
    with contextlib.suppress(OSError):
        found = path.read_text().strip()
        if found:
            return found
    import uuid

    made = str(uuid.uuid4())
    _write_atomic(path, made)
    return made


def _installer() -> str:
    from lado import update

    found = update.installer()
    if found:
        return found.kind
    try:
        from importlib.metadata import distribution

        direct = json.loads(distribution("lado").read_text("direct_url.json") or "{}")
    except Exception:
        direct = {}
    return "dev" if "dir_info" in direct else "other"


def _providers() -> dict[str, str]:
    """The installed agent CLIs with their versions ("" when unknown). Each CLI's
    `--version` runs in a thread of its own, and all of them get PROVIDERS_WAIT seconds of
    SEND_DEADLINE: a CLI still running then is reported with no version. Daemon threads,
    so the sender's end does not wait for them."""
    import shutil
    import threading

    from lado import doctor, providers

    registry = [providers.get(name) for name in providers.names()]
    installed = [p for p in registry if shutil.which(p.command)]
    found = {p.name: "" for p in installed}

    def look(provider) -> None:
        with contextlib.suppress(Exception):
            # Killed by its own timeout: a daemon thread ends with the sender and kills
            # nothing then.
            status = doctor.provider_status(provider, shutil.which, PROVIDERS_WAIT)
            found[provider.name] = status.version

    threads = [threading.Thread(target=look, args=(p,), daemon=True) for p in installed]
    for thread in threads:
        thread.start()
    until = time.monotonic() + PROVIDERS_WAIT
    for thread in threads:
        thread.join(max(0.0, until - time.monotonic()))
    return dict(found)


def _kits(usable: bool) -> dict:
    """The built-in kits and those from the official marketplace by name; the others only
    counted, as their names may be the user's own."""
    from lado import kits, marketplaces

    named = sorted(found.name for found in kits.builtin_kits())
    other = 0
    for found in kits.installed_kits() if usable else []:
        if found.installed and found.installed.marketplace == marketplaces.OFFICIAL:
            named.append(found.name)
        else:
            other += 1
    return {"named": sorted(named), "other": other}


def _lado_errors(since: str) -> int:
    count = 0
    for path in (journal_path().with_name("errors.jsonl.1"), journal_path()):
        with contextlib.suppress(OSError), open(path) as lines:
            for line in lines:
                # A line of another shape (no object, a time that is no text) is no error.
                with contextlib.suppress(ValueError, AttributeError, TypeError):
                    count += json.loads(line).get("at", "") >= since
    return count


def _properties(fields: dict) -> dict:
    """An event's properties: no person profile, no GeoIP (PostHog)."""
    return {**fields, "$process_person_profile": False, "$geoip_disable": True}


def report(
    current: datetime.datetime | None = None, force: bool = False, drops: int | None = None
) -> dict | None:
    """The daily report as the next send posts it; None when one went out in the last
    REPORT_EVERY (`force`: built anyway, for a preview)."""
    import platform

    import lado

    current = current or now()
    sent = _read_json(_sent_path())
    if not force and not _report_due(sent, current):
        return None
    window = datetime.timedelta(seconds=REPORT_MAX_WINDOW)
    since = parse_time(sent.get("report_at")) or current - datetime.timedelta(days=1)
    since = max(since, current - window)
    usable = db.schema_version() == db.SCHEMA_VERSION
    install = _install_id()
    fields = {
        "install": install,
        "lado": lado.__version__,
        "python": platform.python_version(),
        "os": platform.system().lower(),
        "arch": platform.machine(),
        "installer": _installer(),
        "providers": _providers(),
        "kits": _kits(usable),
        "since": format_time(since),
    }
    counts = None
    if usable:
        with contextlib.suppress(Exception):
            counts = db.usage_counts(since.strftime("%Y-%m-%d %H:%M:%S"))
    if counts is None:
        fields["db"] = "unreadable"
    else:
        fields.update(counts)
    fields["lado_errors"] = _lado_errors(format_time(since))
    fields["errors_dropped"] = dropped() if drops is None else drops
    return {
        "event": DAILY,
        "distinct_id": install,
        "timestamp": format_time(current),
        "properties": _properties(fields),
    }


# The queued errors, one event per fingerprint.


def _expire(current: datetime.datetime) -> None:
    """Drop queued errors older than OUTBOX_MAX_AGE, counted as dropped."""
    oldest = (current.timestamp() - OUTBOX_MAX_AGE) * 10**9
    old = 0
    for path, _ in _queued_files():
        with contextlib.suppress(ValueError, OSError):
            if int(path.name.split("-", 1)[0]) < oldest:
                path.unlink()
                old += 1
    if old:
        _count_dropped(old)


def _frame(text: str) -> dict:
    filename, function, line = text.rsplit(":", 2)
    return {
        "platform": "custom",
        "lang": "python",
        "filename": filename,
        "function": function,
        "lineno": int(line),
        "in_app": True,
    }


def _groups(install: str) -> tuple[list[dict], list[Path]]:
    """The queued errors as PostHog's $exception events, one per fingerprint, and the files
    they come from."""
    groups: dict[str, list[dict]] = {}
    files = []
    for path, event in _queued_files():
        files.append(path)
        groups.setdefault(event.get("fingerprint", ""), []).append(event)
    events = []
    for fingerprint_, group in groups.items():
        last = group[-1]
        frames = [_frame(f) for f in last.get("stack", []) if f != EXTERNAL]
        fields = {
            "$exception_list": [
                {
                    "type": last.get("type"),
                    "value": f"{last.get('type')} in {last.get('where')}",
                    "stacktrace": {"type": "raw", "frames": frames},
                }
            ],
            "$exception_fingerprint": fingerprint_,
            **{key: last.get(key) for key in ("type", "chain", "stack", "where", "provider")},
            "fingerprint": fingerprint_,
            "count": len(group),
            "first_at": group[0].get("at"),
            "last_at": last.get("at"),
            "lado": last.get("lado"),
        }
        events.append(
            {
                "event": EXCEPTION,
                "distinct_id": install,
                "timestamp": last.get("at"),
                "properties": _properties(fields),
            }
        )
    return events, files


@dataclasses.dataclass
class _Built:
    events: list[dict]
    files: list[Path]  # the queued errors' files the events carry
    report: bool
    dropped: int  # the drop count the report carries


def _build(current: datetime.datetime | None = None) -> _Built:
    current = current or now()
    _expire(current)
    drops = dropped()
    daily = report(current, drops=drops)
    errors, files = _groups(_install_id())
    events = ([daily] if daily else []) + errors
    return _Built(events, files, daily is not None, drops if daily else 0)


def batch(current: datetime.datetime | None = None) -> list[dict]:
    """The events the next send posts: the daily report when due, then the queued errors."""
    return _build(current).events


def preview(current: datetime.datetime | None = None) -> dict:
    """What `lado telemetry show` and the UI show: the daily report (also when it is not
    due yet) and the queued errors, as the next send posts them."""
    current = current or now()
    _expire(current)
    errors, _ = _groups(_install_id())
    return {"report": report(current, force=True), "errors": errors}


# The sender: `lado telemetry send`, a detached process, the only one that goes to the
# network.


class _Deadline(BaseException):
    """SEND_DEADLINE passed. No `except Exception` of the build may swallow it: the try
    must end where it is, never reach the network after its deadline."""


@contextlib.contextmanager
def _deadline(seconds: float):
    """End what runs inside after `seconds` (urllib's timeout does not cover DNS), on the
    main thread only."""
    import signal
    import threading

    if threading.current_thread() is not threading.main_thread():
        yield
        return

    def expired(signum, frame):
        raise _Deadline(f"no answer within {seconds:g} s")

    previous = signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


def _open(request, timeout: float):
    import urllib.request

    return urllib.request.urlopen(request, timeout=timeout)


def _post(events: list[dict], environ: Mapping[str, str] | None = None) -> None:
    """Post `events` to PostHog's batch API (or LADO_TELEMETRY_URL's); raises unless the
    answer is 2xx."""
    import urllib.request

    environ = os.environ if environ is None else environ
    url = _url(environ)
    if url is None:
        raise OSError("no statistics endpoint")
    body = json.dumps({"api_key": _token(environ), "batch": events}).encode()
    request = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"}, method="POST"
    )
    with _open(request, SEND_TIMEOUT) as answer:
        answer.read()
        if not 200 <= answer.status < 300:
            raise OSError(f"HTTP {answer.status}")


def _reason(exc: BaseException) -> str:
    """Why a try failed, one short line, for `status` and Settings only."""
    import urllib.error

    if isinstance(exc, urllib.error.HTTPError):
        return f"HTTP {exc.code}"
    if isinstance(exc, urllib.error.URLError):
        return str(exc.reason)[:200]
    return (str(exc) or _type_name(type(exc)))[:200]


def send() -> int:
    """`lado telemetry send`: post what is due, one sender at a time (a second one exits),
    at most one try per RETRY_AFTER, within SEND_DEADLINE. What it sent is removed only
    after a 2xx; a failure keeps everything and is kept for `status`. Silent; always 0."""
    import fcntl
    import http.client

    try:
        folder().mkdir(parents=True, exist_ok=True)
        lock = open(folder() / "send.lock", "a")
    except OSError:
        return 0
    with lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            return 0
        if not state().on:
            return 0
        current = now()
        if _tried_lately(_read_json(_sent_path()), current):
            return 0
        try:
            _update_sent(tried_at=format_time(current))
            with _deadline(SEND_DEADLINE):
                built = _build(current)
                if built.events:
                    _post(built.events)
        except (OSError, http.client.HTTPException, _Deadline) as exc:
            with contextlib.suppress(Exception):
                _update_sent(error=_reason(exc))
            return 0
        except Exception as exc:
            _journal_only("telemetry:send", exc)
            with contextlib.suppress(Exception):
                _update_sent(error=f"the sender failed: {_type_name(type(exc))}")
            return 0
        if not built.events:
            return 0  # nothing went: the last send and the last failure stay as they were
        with contextlib.suppress(Exception):
            for path in built.files:
                with contextlib.suppress(OSError):
                    path.unlink()
            if built.dropped:
                _subtract_dropped(built.dropped)
            done = {"sent_at": format_time(current), "error": None}
            if built.report:
                done["report_at"] = format_time(current)
            _update_sent(**done)
    return 0


def _subtract_dropped(count: int) -> None:
    """The drops a report carried went out: those added since stay."""
    left = max(0, dropped() - count)
    path = folder() / "dropped"
    if left:
        _write_atomic(path, "x" * left)
    else:
        with contextlib.suppress(OSError):
            path.unlink()


def kick() -> None:
    """Start a detached `lado telemetry send` when sending is on, something is due and no
    try came in the last RETRY_AFTER. Cheap: a few files read, no network. Never raises."""
    with contextlib.suppress(Exception):
        if not state().on:
            return
        current = now()
        sent = _read_json(_sent_path())
        if _tried_lately(sent, current):
            return
        if not _report_due(sent, current) and not any(_outbox().glob("*.json")):
            return
        import subprocess

        from lado import interpreter

        subprocess.Popen(
            interpreter.run_module("lado.cli", "telemetry", "send"),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,  # not ended with the command, the loop or the server
            close_fds=True,
        )


# What the human sees: the question, `lado telemetry status`.

DOCS = "https://github.com/ladohq/lado/blob/main/docs/telemetry.md"
QUESTION = (
    "LADO can send anonymous usage statistics and its own errors to its maintainers,\n"
    "so they see how many people use it, which versions run and which errors to fix first.\n"
    "Never paths, repository or session names, messages, prompts or keys.\n"
    f"See what is sent: lado telemetry show · {DOCS}\n"
)
ON = "statistics: on (lado telemetry off to stop)"
OFF = "statistics: off"
IN_AGENT = "lado telemetry on|off is for the human, not an agent"


def ask_if_needed(stdin=None, stderr=None) -> None:
    """Ask the human once, on a terminal, before `lado start` or `lado ui` do their work:
    only while the choice is not made, nothing switches it off, there is an endpoint, and
    not inside an agent. Enter or n is off, y is on; EOF or Ctrl-C keeps no choice."""
    import sys

    stdin = sys.stdin if stdin is None else stdin
    stderr = sys.stderr if stderr is None else stderr
    now_ = state()
    if not now_.ask or os.environ.get("LADO_AGENT"):
        return
    try:
        if not (stdin.isatty() and stderr.isatty()):
            return
    except (AttributeError, ValueError):
        return
    new = now_.new_fields
    if new:
        stderr.write(f"LADO now also sends: {', '.join(new)}.\n")
    stderr.write(QUESTION + "Send them? [y/N] ")
    stderr.flush()
    try:
        answer = stdin.readline()
    except KeyboardInterrupt:
        stderr.write("\n")
        return
    if not answer:  # EOF
        stderr.write("\n")
        return
    yes = answer.strip().lower() in ("y", "yes")
    choose("on" if yes else "off")
    stderr.write(f"{ON if yes else OFF}\n")
    stderr.flush()


def _local(text: str | None) -> str:
    when = parse_time(text)
    return when.astimezone().strftime("%Y-%m-%d %H:%M") if when else "never"


def _plural(count: int, word: str) -> str:
    return f"{count} {word}{'' if count == 1 else 's'}"


def status_lines(now_: State | None = None) -> list[str]:
    """`lado telemetry status`: whether it sends and why not; when on, the last send, what
    waits and the last failure."""
    now_ = now_ or state()
    chosen = now_.chosen
    if now_.off_by:
        return [f"statistics: off: {now_.off_by} is set (your choice: {chosen or 'not chosen'})"]
    if not now_.endpoint:
        return ["statistics: off: this LADO has no statistics endpoint"]
    if chosen == "off":
        return [OFF]
    if chosen is None:
        return ["statistics: not chosen (lado telemetry on|off)"]
    day = (now_.chosen_at or "")[:10]
    sent = _read_json(_sent_path())
    reports = 1 if _report_due(sent, now()) else 0
    lines = [
        f"statistics: on (chosen {day})",
        f"last sent: {_local(sent.get('sent_at'))} · waiting: {_plural(reports, 'report')}, "
        f"{_plural(len(_queued_files()), 'error')}",
    ]
    if sent.get("error"):
        lines.append(f"last try failed: {sent['error']}")
    return lines
