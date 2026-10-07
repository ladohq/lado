"""The local artifact store: metadata in lado.db (through lado.state), content in files by
hash under LADO_HOME/artifacts (docs/design/artifacts.md, The local backend).

A content file is written to a temporary file in its folder, fsynced and renamed, before
the record that refers to it; its bytes never change, and equal content is stored once. A
file no record refers to (a crash between file and row, a forgotten session) is removed
only once its modification time is more than ORPHAN_AGE old: a writer that finds its file
there sets the time to now, so a removal never takes the file of a write in progress, and a
writer whose file went all the same writes it again.
"""

import hashlib
import os
import tempfile
import time
from pathlib import Path

from lado import state as lado_state  # `write` has a parameter "state"
from lado.artifacts import Artifact, ArtifactError, Record, Usage, Written

ORPHAN_AGE = 3600  # seconds
Paths = list[Path]  # named here: inside LocalStore, `list` is its method


class LocalStore:
    def __init__(self, home: Path):
        self.root = home / "artifacts"

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
    ) -> Written:
        digest = self._put(data)
        record = {
            "hash": digest,
            "size": len(data),
            "media_type": media_type,
            "author": author,
            "run": run,
            "state": state,
            "visit": visit,
            "summary": summary,
        }
        rows, unchanged = lado_state.write_artifact(session, scope, name, title, record)
        if not self._path(digest).exists():
            self._put(data)  # a removal took it between the time update and the row
        return Written(*_pair(rows), unchanged)

    def latest(self, session: str, scope: str, name: str) -> tuple[Artifact, Record] | None:
        rows = lado_state.latest_artifact(session, scope, name)
        return _pair(rows) if rows else None

    def artifact(self, artifact_id: str) -> tuple[Artifact, Record] | None:
        rows = lado_state.artifact_by_id(artifact_id)
        return _pair(rows) if rows else None

    def record(self, record_id: str) -> tuple[Artifact, Record] | None:
        rows = lado_state.artifact_record(record_id)
        return _pair(rows) if rows else None

    def content(self, record_id: str) -> bytes:
        found = self.record(record_id)
        if found is None:
            raise ArtifactError(f"no record {record_id} in the store")
        artifact, record = found
        try:
            return self._path(record.hash).read_bytes()
        except FileNotFoundError:
            raise ArtifactError(
                f"content of {artifact.full_name} is missing from the store"
                f" ({self._path(record.hash)})"
            ) from None

    def list(self, session: str, scope: str | None = None) -> list[tuple[Artifact, Record]]:
        return [_pair(rows) for rows in lado_state.list_artifacts(session, scope)]

    def remove_session(self, session: str) -> int:
        removed = lado_state.remove_artifacts(session)
        self._collect()
        return removed

    def usage(self) -> Usage:
        artifacts, records = lado_state.artifact_counts()
        size = sum(path.stat().st_size for path in self._files())
        orphans = self._orphans()
        return Usage(artifacts, records, size, len(orphans), sum(o.stat().st_size for o in orphans))

    def _path(self, digest: str) -> Path:
        return self.root / digest[:2] / digest

    def _put(self, data: bytes) -> str:
        """Store the content, once: its hash."""
        digest = hashlib.sha256(data).hexdigest()
        path = self._path(digest)
        try:
            os.utime(path)
            return digest
        except FileNotFoundError:
            pass
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=".tmp-")
        try:
            with os.fdopen(fd, "wb") as out:
                out.write(data)
                out.flush()
                os.fsync(out.fileno())
            os.replace(temporary, path)
        except BaseException:
            Path(temporary).unlink(missing_ok=True)
            raise
        return digest

    def _files(self) -> Paths:
        if not self.root.is_dir():
            return []
        return [p for p in self.root.glob("*/*") if p.is_file()]

    def _orphans(self) -> Paths:
        """Files no record refers to whose modification time is older than ORPHAN_AGE."""
        used = lado_state.artifact_hashes()
        old = time.time() - ORPHAN_AGE
        return [p for p in self._files() if p.name not in used and p.stat().st_mtime < old]

    def _collect(self) -> None:
        for orphan in self._orphans():
            orphan.unlink(missing_ok=True)


def _pair(rows: tuple[dict, dict]) -> tuple[Artifact, Record]:
    artifact, record = rows
    fields = {k: record[k] for k in Record.__dataclass_fields__}
    return Artifact(**artifact), Record(**fields)
