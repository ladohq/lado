"""A bug report for a new GitHub issue (openspec change bug-report): the system info of
`doctor.report`, the page's browser line in the UI, and LADO's errors of the last WINDOW
from the error journal, grouped by kind; and a link to GitHub's new issue form with it, at
most MAX_URL long. The one builder for `lado bug-report` and `GET /api/bug-report`.

Of a journal line it reads only `at`, `lado`, `where`, `type`, `chain`, `stack`,
`fingerprint` and `provider` (`READ`): never the message, traceback, session or agent,
which name the user's work. It sends nothing: the human opens the link, and GitHub's form
is where they submit it."""

import datetime
import json
import os
import sys
from dataclasses import dataclass
from urllib.parse import quote, urlencode

from lado import doctor, gui_session, telemetry

WINDOW = datetime.timedelta(days=30)
MAX_URL = 8000  # characters of the link: GitHub refuses much longer ones
MAX_FRAMES = 12  # of a kind's stack, the innermost
MAX_TITLE = 120
ISSUES_NEW = "https://github.com/ladohq/lado/issues/new"
PRIVATE_REPORT = "https://github.com/ladohq/lado/security/advisories/new"
READ = ("at", "lado", "where", "type", "chain", "stack", "fingerprint", "provider")
WARNING = (
    "This text is for a new public issue on github.com/ladohq/lado. Nothing is sent until you\n"
    "submit it there, and you can edit or delete any of it first. It holds no paths, session or\n"
    "repository names, nor message texts. For a vulnerability, use private reporting instead:\n"
    f"{PRIVATE_REPORT}\n"
)
PLACEHOLDER = "<!-- What did you do, what did you expect, and what happened instead? -->"
WHAT_HAPPENED = f"### What happened\n\n{PLACEHOLDER}\n"
NO_ERRORS = "No LADO errors in the last 30 days."


@dataclass(frozen=True)
class Kind:
    """The journal's lines of one error: by fingerprint, or by type and where for a line
    without one (LADO 0.37)."""

    type: str
    where: str  # of its newest line
    provider: str | None  # of its newest line
    count: int
    first: datetime.datetime
    last: datetime.datetime
    versions: list[str]  # distinct, in the order first seen
    stack: list[str]  # of its newest line, at most MAX_FRAMES innermost; [] without one


@dataclass(frozen=True)
class Report:
    title: str  # "<type> at <where>" of the newest kind, "" with no errors
    text: str  # the whole report, never cut
    body: str  # the link's: `text` with the oldest kinds left out until the link fits
    url: str
    left_out: int  # kinds of errors left out of `body`


def _usable(line: object) -> dict | None:
    """A journal line's fields of READ, or None for a line of another shape."""
    if not isinstance(line, dict):
        return None
    if telemetry.parse_time(line.get("at")) is None:
        return None
    if not isinstance(line.get("type"), str) or not isinstance(line.get("where"), str):
        return None
    kept = {key: line[key] for key in READ if key in line}
    if not isinstance(kept.get("lado"), str):
        kept["lado"] = "unknown"
    stack = kept.get("stack")
    if not (isinstance(stack, list) and all(isinstance(frame, str) for frame in stack)):
        kept.pop("stack", None)
    if not isinstance(kept.get("fingerprint"), str):
        kept.pop("fingerprint", None)
    if not isinstance(kept.get("provider"), str):
        kept["provider"] = None
    return kept


def errors(now: datetime.datetime | None = None) -> list[dict]:
    """The journal's lines of the last WINDOW, oldest first (errors.jsonl.1, then
    errors.jsonl), each with only the fields of READ; a line it cannot read is skipped."""
    since = (now or telemetry.now()) - WINDOW
    path = telemetry.journal_path()
    found = []
    for name in (path.name + ".1", path.name):
        try:
            text = path.with_name(name).read_text(errors="replace")
        except OSError:
            continue
        for raw in text.splitlines():
            try:
                line = _usable(json.loads(raw))
            except ValueError:
                continue
            if line is not None and telemetry.parse_time(line["at"]) >= since:
                found.append(line)
    return found


def kinds(lines: list[dict]) -> list[Kind]:
    """The lines grouped by kind, the newest kind first."""
    groups: dict[tuple, list[dict]] = {}
    for line in lines:
        key = ("fingerprint", line["fingerprint"]) if "fingerprint" in line else None
        key = key or ("type", line["type"], line["where"])
        groups.setdefault(key, []).append(line)
    found = []
    for group in groups.values():
        group.sort(key=lambda line: telemetry.parse_time(line["at"]))
        newest = group[-1]
        found.append(
            Kind(
                type=newest["type"],
                where=newest["where"],
                provider=newest["provider"],
                count=len(group),
                first=telemetry.parse_time(group[0]["at"]),
                last=telemetry.parse_time(newest["at"]),
                versions=list(dict.fromkeys(line["lado"] for line in group)),
                stack=newest.get("stack", [])[-MAX_FRAMES:],
            )
        )
    found.sort(key=lambda kind: kind.last, reverse=True)
    return found


def _kind_lines(kind: Kind) -> list[str]:
    provider = f" ({kind.provider})" if kind.provider else ""
    count = "once" if kind.count == 1 else f"{kind.count} times"
    first, last = kind.first.strftime("%Y-%m-%d"), kind.last.strftime("%Y-%m-%d")
    days = first if first == last else f"{first} to {last}"
    head = (
        f"- {kind.type} at {kind.where}{provider}, {count}, {days}, LADO {', '.join(kind.versions)}"
    )
    return [head, *(f"  - {frame}" for frame in kind.stack)]


def _errors_section(found: list[Kind], shown: int) -> str:
    if not found:
        return f"### LADO errors (last 30 days)\n{NO_ERRORS}\n"
    total = len(found)
    lines = [f"### LADO errors (last 30 days, {total} {'kind' if total == 1 else 'kinds'})"]
    for kind in found[:shown]:
        lines.extend(_kind_lines(kind))
    if shown < total:
        left = total - shown
        lines.append(
            f"- {left} more {'kind' if left == 1 else 'kinds'} of errors left out: "
            "lado bug-report prints them all"
        )
    return "\n".join(lines) + "\n"


def link(title: str, body: str) -> str:
    return f"{ISSUES_NEW}?{urlencode({'title': title, 'body': body}, quote_via=quote)}"


def build(
    system: doctor.System,
    server: doctor.ServerState | None,
    browser: str | None = None,
    now: datetime.datetime | None = None,
) -> Report:
    """The report of this system and the journal; `browser` is the page's checked line."""
    found = kinds(errors(now))
    head = f"{WHAT_HAPPENED}\n{doctor.report(system, server)}"
    if browser:
        head += browser + "\n"
    title = f"{found[0].type} at {found[0].where}"[:MAX_TITLE] if found else ""
    text = f"{head}\n{_errors_section(found, len(found))}"
    for shown in range(len(found), -1, -1):
        body = f"{head}\n{_errors_section(found, shown)}"
        if len(link(title, body)) <= MAX_URL:
            break
    else:  # even the system info does not fit (never seen): its last lines go
        lines = body.splitlines(keepends=True)
        while lines and len(link(title, "".join(lines))) > MAX_URL:
            lines.pop()
        body = "".join(lines)
    return Report(title, text, body, link(title, body), len(found) - shown)


def can_show_browser(environ: dict[str, str] | None = None) -> bool:
    """Whether a browser opened from this process can show to the human: on macOS when the
    process is in the graphical session, elsewhere when DISPLAY, WAYLAND_DISPLAY or BROWSER
    is set (over ssh `webbrowser` would start a text browser, or fail)."""
    environ = os.environ if environ is None else environ
    if sys.platform == "darwin":
        return gui_session.place() == gui_session.Place.GUI
    return any(environ.get(name) for name in ("DISPLAY", "WAYLAND_DISPLAY", "BROWSER"))
