"""Artifacts: named documents of a session that agents write and read, kept by LADO
(docs/design/artifacts.md). The only module the rest of LADO calls for them: it checks
names, scopes, rights and limits, resolves bare and full names, and calls the store, chosen
in `store()`. Nothing else touches the store or its tables.

An artifact is in a scope of its session: a flow run's (its name) or the session's (''). Its
full name is `<run>/<name>`, or `<name>` in the session's scope; it is parsed by its last
`/`, since a run's name holds one. Every write is a record; agents see the latest.
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from lado import state

SESSION_SCOPE = ""
SUPERVISOR = "supervisor"  # the lead's agent name (lado.runtime.SUPERVISOR)
NAME = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}")
SUMMARY_LIMIT = state.SUMMARY_LIMIT  # characters in a title or a summary
MAX_SIZE = 25 * 1024 * 1024  # bytes in a record
READ_LIMIT = 100_000  # characters read_artifact gives at once
CREATED, UNCHANGED = "created", "unchanged"
MEDIA_TYPE = re.compile(r"[A-Za-z0-9][\w.+-]*/[A-Za-z0-9][\w.+-]*")
# The media type of a file or a name by its extension: one table, not the system's
# mimetypes, which differ between machines and take .ts for video. Code is text, so
# read_artifact gives it as such (is_text).
EXTENSIONS = {
    "md": "text/markdown",
    "markdown": "text/markdown",
    "txt": "text/plain",
    "log": "text/plain",
    "json": "application/json",
    "yaml": "text/yaml",
    "yml": "text/yaml",
    "csv": "text/csv",
    "html": "text/html",
    "htm": "text/html",
    "svg": "image/svg+xml",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "gif": "image/gif",
    "webp": "image/webp",
    "pdf": "application/pdf",
    "py": "text/x-python",
    "ts": "text/typescript",
    "tsx": "text/typescript",
    "js": "text/javascript",
    "sh": "text/x-shellscript",
    "toml": "text/x-toml",
    "xml": "text/xml",
}
TEXT_TYPES = ("application/json", "image/svg+xml")  # text besides text/*


class ArtifactError(RuntimeError):
    """A write, read or attachment LADO refuses; the text says why and what to do."""


@dataclass(frozen=True)
class Artifact:
    id: str
    session: str
    scope: str  # the run's name, SESSION_SCOPE for the session's
    name: str
    title: str | None = None

    @property
    def full_name(self) -> str:
        return full_name(self.scope, self.name)


@dataclass(frozen=True)
class Record:
    """One write of an artifact's content; never changed."""

    id: str
    artifact: str
    session: str
    hash: str  # sha256 hex of the content
    size: int
    media_type: str
    author: str
    run: str | None = None  # in a run's scope: the run, its state and that state's visit
    state: str | None = None
    visit: int | None = None
    summary: str | None = None
    created_at: str = ""  # UTC, "YYYY-MM-DD HH:MM:SS.SSS"


@dataclass(frozen=True)
class Written:
    artifact: Artifact
    record: Record
    unchanged: bool  # its content equals the previous record's

    @property
    def full_name(self) -> str:
        return self.artifact.full_name

    @property
    def status(self) -> str:
        return UNCHANGED if self.unchanged else CREATED

    @property
    def size(self) -> int:
        return self.record.size

    @property
    def media_type(self) -> str:
        return self.record.media_type


@dataclass(frozen=True)
class Usage:
    """What a store holds, for `lado doctor`."""

    artifacts: int
    records: int
    bytes: int
    orphans: int  # content no record refers to, older than the store removes it at
    orphan_bytes: int


class Store(Protocol):
    """Where artifacts are kept, at the level of artifacts: a backend owns their names,
    records and content alike, and LADO keeps only their opaque ids (attachments)."""

    def write(
        self,
        session: str,
        scope: str,
        name: str,
        data: bytes,
        media_type: str,
        *,
        author: str,
        run: str | None,
        state: str | None,
        visit: int | None,
        summary: str | None,
        title: str | None,
    ) -> Written: ...

    def latest(self, session: str, scope: str, name: str) -> tuple[Artifact, Record] | None: ...

    def record(self, record_id: str) -> tuple[Artifact, Record] | None:
        """A record with its artifact."""

    def content(self, record_id: str) -> bytes: ...

    def list(self, session: str, scope: str | None = None) -> list[tuple[Artifact, Record]]:
        """The session's artifacts (or one scope's) with their latest records."""

    def remove_session(self, session: str) -> int:
        """Remove everything of the session; returns how many artifacts."""

    def usage(self) -> Usage: ...


def store() -> Store:
    """The one place the store is chosen: there is one backend, the local one."""
    from lado import artifacts_local

    return artifacts_local.LocalStore(state.home())


def full_name(scope: str, name: str) -> str:
    return f"{scope}/{name}" if scope else name


def parse(given: str) -> tuple[str | None, str]:
    """A name as given: its scope (None for a bare name) and its name, by the last `/`."""
    scope, slash, name = given.strip().rpartition("/")
    if not NAME.fullmatch(name):
        raise ArtifactError(
            f'"{given}" is no artifact name: a name is 1-64 characters of a-z, 0-9, "-", "_"'
            ' and ".", starting with a letter or a digit; in a run\'s scope its full name is'
            ' "<run>/<name>"'
        )
    return (scope if slash else None), name


def is_text(media_type: str) -> bool:
    """Whether read_artifact gives the content as text."""
    return media_type.startswith("text/") or media_type in TEXT_TYPES


def write(
    session: str,
    agent: str,
    name: str,
    content: str | None = None,
    file: str | None = None,
    media_type: str | None = None,
    summary: str | None = None,
    title: str | None = None,
) -> Written:
    """Write a record of artifact `name` for `agent`: `content` (text) or the bytes of
    `file`, a path relative to the folder LADO started the agent in, or absolute."""
    me = _agent(session, agent)
    scope, bare = parse(name)
    run = _writable(session, me, scope, bare)
    title, summary = _line("title", title), _line("summary", summary)
    if media_type is not None and not MEDIA_TYPE.fullmatch(media_type.strip()):
        raise ArtifactError(f'media_type "{media_type}" is no media type, e.g. "text/markdown"')
    if (content is None) == (file is None):
        raise ArtifactError("give exactly one of content and file")
    if content is not None:
        data = content.encode()
        _check_size(len(data))
        guessed = _by_extension(bare) or "text/markdown"
    else:
        # From the agent's folder, not this process's: `lado mcp` may run elsewhere. An
        # absolute path stays as it is.
        path = Path(me.cwd, file)
        data = _read_file(path)
        guessed = _by_extension(path.name) or _by_extension(bare) or "application/octet-stream"
    return store().write(
        session,
        run.name if run else SESSION_SCOPE,
        bare,
        data,
        (media_type or "").strip().lower() or guessed,
        author=me.name,
        run=run.name if run else None,
        state=run.state if run else None,
        visit=run.visits.get(run.state) if run else None,
        summary=summary,
        title=title,
    )


def _writable(session: str, agent: state.Agent, scope: str | None, name: str) -> state.Run | None:
    """The run whose scope `agent` writes `name` of `scope` (None: bare) to, None for the
    session's, or why it may not: a run's worker writes only to its run's, another worker
    only to the session's, the supervisor to the session's and any open run's; nobody to a
    closed run's (docs/design/artifacts.md, Names and scopes)."""
    if agent.run:
        own = agent.run
        if scope not in (None, own):
            raise ArtifactError(
                f'{agent.name} may write only to run {own}\'s scope: "{name}" or "{own}/{name}"'
            )
        scope = own
    elif agent.name != SUPERVISOR:
        if scope:
            raise ArtifactError(
                f'{agent.name} may write only to the session\'s scope: a bare name, "{name}"'
            )
        return None
    if not scope:
        return None
    allowed = (
        f"; {agent.name} may write to the session's scope (\"{name}\") and an open run's"
        f' ("<run>/{name}")'
        if agent.name == SUPERVISOR
        else ""
    )
    run = state.get_run(session, scope)
    if run is None:
        raise ArtifactError(f'no run "{scope}" in session {session}{allowed}')
    if run.status not in state.OPEN:
        raise ArtifactError(
            f"run {run.name} is {run.status}: its artifacts are no longer written{allowed}"
        )
    return run


def read(
    session: str, agent: str, name: str, from_line: int | None = None, to_line: int | None = None
) -> dict:
    """read_artifact's result: the latest content of a text artifact as `agent` names it."""
    artifact, record = find(session, name, _agent(session, agent))
    about = {"name": artifact.full_name, "media_type": record.media_type, "size": record.size}
    if not is_text(record.media_type):
        return {**about, "binary": True, "note": "cannot be read as text"}
    lines = store().content(record.id).decode(errors="replace").splitlines(keepends=True)
    first = 1 if from_line is None else from_line
    last = len(lines) if to_line is None else to_line
    if first < 1 or (to_line is not None and last < first):
        raise ArtifactError("from_line and to_line count from 1, from_line first")
    if first > max(len(lines), 1):
        raise ArtifactError(f"{artifact.full_name} has {len(lines)} lines")
    content, taken, cut = "", first - 1, False
    for line in lines[first - 1 : last]:
        if len(content) + len(line) > READ_LIMIT:
            if not content:  # one line over the limit: as much of it as fits
                content, taken = line[:READ_LIMIT], taken + 1
            cut = True
            break
        content, taken = content + line, taken + 1
    return {
        **about,
        "lines": len(lines),
        "from_line": first,
        "to_line": taken,
        "content": content,
        "cut": cut,
    }


def listed(session: str, agent: str, run: str | None = None) -> list[dict]:
    """list_artifacts' result: the artifacts of `run`'s scope, else of the scope a bare
    name means for `agent`, each as of its latest record."""
    if run:
        if state.get_run(session, run) is None:
            raise ArtifactError(f'no run "{run}" in session {session}')
        scope = run
    else:
        scope = _agent(session, agent).run or SESSION_SCOPE
    return [
        {
            "name": artifact.full_name,
            "title": artifact.title,
            "media_type": record.media_type,
            "size": record.size,
            "author": record.author,
            "time": f"{record.created_at} UTC",
            "summary": record.summary,
        }
        for artifact, record in store().list(session, scope)
    ]


def resolve_attachments(session: str, agent: str, names: list[str] | None) -> list[tuple[str, str]]:
    """Each name `agent` attaches (bare or full, as in `find`) as its artifact's id and its
    latest record's, once each, in order; a name not found refuses them all."""
    if not names:
        return []
    me = _agent(session, agent)
    attached = []
    for name in names:
        artifact, record = find(session, name, me)
        if (artifact.id, record.id) not in attached:
            attached.append((artifact.id, record.id))
    return attached


def attached(attachments: list[tuple[str, str]]) -> list[dict]:
    """What read_messages says of each attachment: its full name, title, the attached
    record's media type and size, and whether the artifact's content changed since (its
    latest record's hash differs from the attached one's)."""
    described = []
    for _, record_id in attachments:
        found = store().record(record_id)
        if found is None:
            continue  # its session was forgotten: so was the message
        artifact, record = found
        _, latest = store().latest(artifact.session, artifact.scope, artifact.name)
        described.append(
            {
                "name": artifact.full_name,
                "title": artifact.title,
                "media_type": record.media_type,
                "size": record.size,
                "changed": latest.hash != record.hash,
            }
        )
    return described


def attached_line(attachments: list[tuple[str, str]]) -> str:
    """One line naming the attachments, each changed one with "(changed since)"; '' for
    none. For a flow step's notes and `lado answer`."""
    if not attachments:
        return ""
    names = [
        a["name"] + (" (changed since)" if a["changed"] else "") for a in attached(attachments)
    ]
    return f"Artifacts: {', '.join(names)}"


def find(session: str, name: str, agent: state.Agent | None = None) -> tuple[Artifact, Record]:
    """The artifact a name means, with its latest record: a bare name is in the scope of
    `agent`'s run, else the session's."""
    scope, bare = parse(name)
    if scope is None:
        scope = (agent.run if agent else None) or SESSION_SCOPE
    found = store().latest(session, scope, bare)
    if found is None:
        raise ArtifactError(f'no artifact "{full_name(scope, bare)}" in session {session}')
    return found


def _line(field: str, text: str | None) -> str | None:
    """A title or a summary: one line of at most SUMMARY_LIMIT characters; None for none."""
    text = (text or "").strip()
    if "\n" in text or len(text) > SUMMARY_LIMIT:
        raise ArtifactError(f"{field} must be one line of at most {SUMMARY_LIMIT} characters")
    return text or None


def _check_size(size: int) -> None:
    if size > MAX_SIZE:
        raise ArtifactError(f"the content is {size} bytes, the limit is {MAX_SIZE} bytes")


def _read_file(path: Path) -> bytes:
    if not path.exists():
        raise ArtifactError(f"no file {path}")
    if not path.is_file():
        raise ArtifactError(f"{path} is not a regular file")
    _check_size(path.stat().st_size)
    data = path.read_bytes()
    _check_size(len(data))  # it may have grown since
    return data


def _by_extension(name: str) -> str | None:
    stem, dot, extension = name.rpartition(".")
    return EXTENSIONS.get(extension.lower()) if dot and stem else None


def _agent(session: str, name: str) -> state.Agent:
    agent = state.get_agent(session, name)
    if agent is None:
        raise ArtifactError(f'no agent "{name}" in session {session}')
    return agent
