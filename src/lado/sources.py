"""Kit sources: places kits come from besides the project, LADO_HOME/kits and LADO itself.

A source gives LADO a local directory to read kits from. Kinds:

    path    a local folder, read in place and never copied (for developing kits)
    git     a repository cloned into LADO_HOME/sources/<name>; ref: tag, branch or commit

A source may name the folders its skills come from (`skills`, relative paths such as
skills/engineering); other skills in it are not used.

Sources are registered in LADO_HOME/sources.yaml, in the order they were added. Only the
Source classes know what a kind means; everything else asks a source for its directory.
"""

import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

import yaml

from lado import state

REGISTRY = "sources.yaml"
SOURCE_KEYS = {"name", "kind", "location", "ref", "skills"}
NAME = re.compile(r"[a-z0-9][a-z0-9_-]*")  # a source name is also a kit name (skill packs)
VERSION_TAG = re.compile(r"v(\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?)")
# git@host:owner/repo: an scp-like git address.
SCP_LIKE = re.compile(r"[\w.-]+@[\w.-]+:")


class SourceError(RuntimeError):
    pass


@dataclass(frozen=True)
class Source:
    name: str
    location: str
    ref: str | None = None
    skills: tuple[str, ...] = ()  # folders to take skills from; empty: all of skills/

    kind: ClassVar[str]

    def path(self) -> Path:
        """The local directory that holds the source's kits."""
        raise NotImplementedError

    def fetch(self) -> None:
        """Make path() ready when the source is added."""
        raise NotImplementedError

    def update(self) -> str:
        """Bring path() up to date; returns what happened."""
        raise NotImplementedError

    def delete(self) -> str:
        """Clean up when the source is removed; returns what happened to its files."""
        raise NotImplementedError

    def revision(self) -> str | None:
        """What is checked out now, if the kind has revisions."""
        return None

    def versions(self) -> list[str]:
        """Versions the source gives to what is checked out now (e.g. tags vX.Y.Z)."""
        return []

    def describe(self) -> str:
        ref = f" @{self.ref}" if self.ref else ""
        skills = f" skills: {', '.join(self.skills)}" if self.skills else ""
        return f"{self.kind} {self.location}{ref}{skills}"


class PathSource(Source):
    kind = "path"

    def path(self) -> Path:
        return Path(self.location)

    def fetch(self) -> None:
        if self.ref:
            raise SourceError(f"{self.location}: a local folder has no ref; drop @{self.ref}")
        if not self.path().is_dir():
            raise SourceError(f"{self.location} is not a folder")

    def update(self) -> str:
        return f"nothing to update; read in place from {self.location}"

    def delete(self) -> str:
        return f"kept the folder {self.location}"


class GitSource(Source):
    kind = "git"

    def path(self) -> Path:
        return state.home() / "sources" / self.name

    def fetch(self) -> None:
        clone = self.path()
        if clone.exists():
            raise SourceError(f"{clone} already exists; delete it or choose another --name")
        clone.parent.mkdir(parents=True, exist_ok=True)
        try:
            _git(None, "clone", "--quiet", self.location, str(clone))
            if self.ref:
                self._checkout()
        except SourceError as exc:
            shutil.rmtree(clone, ignore_errors=True)
            raise SourceError(f"cannot get {self.describe()}: {exc}") from None

    def update(self) -> str:
        if not self.path().is_dir():
            self.fetch()
        else:
            _git(self.path(), "fetch", "--quiet", "--tags", "--force", "origin")
            self._checkout()
        return f"at {self.revision()}"

    def delete(self) -> str:
        shutil.rmtree(self.path(), ignore_errors=True)
        return f"deleted the clone {self.path()}"

    def revision(self) -> str | None:
        if not self.path().is_dir():
            return None
        return _git(self.path(), "rev-parse", "--short", "HEAD")

    def versions(self) -> list[str]:
        if not self.path().is_dir():
            return []
        tags = _git(self.path(), "tag", "--points-at", "HEAD").split()
        return [m.group(1) for t in tags if (m := VERSION_TAG.fullmatch(t))]

    def _checkout(self) -> None:
        """Check out the ref (a branch at its remote head), or the remote's default branch.
        The clone stays on a detached HEAD: LADO only reads it."""
        target = self.ref or "origin/HEAD"
        if self.ref and _git(self.path(), "branch", "--remotes", "--list", f"origin/{self.ref}"):
            target = f"origin/{self.ref}"
        try:
            _git(self.path(), "rev-parse", "--verify", "--quiet", f"{target}^{{commit}}")
        except SourceError:
            raise SourceError(f'no tag, branch or commit "{self.ref}" in {self.location}') from None
        _git(self.path(), "checkout", "--quiet", "--detach", target)


KINDS: dict[str, type[Source]] = {k.kind: k for k in (PathSource, GitSource)}


def registered() -> list[Source]:
    """The registered sources, in the order they were added."""
    path = state.home() / REGISTRY
    if not path.exists():
        return []
    try:
        data = yaml.safe_load(path.read_text()) or {}
    except yaml.YAMLError as exc:
        raise SourceError(f"{path}: invalid YAML: {exc}") from None
    entries = data.get("sources") if isinstance(data, dict) else None
    if not isinstance(entries, list):
        raise SourceError(f"{path}: expected `sources:` with a list of sources")
    found = []
    for entry in entries:
        if (
            not isinstance(entry, dict)
            or set(entry) - SOURCE_KEYS
            or entry.get("kind") not in KINDS
            or not isinstance(entry.get("name"), str)
            or not isinstance(entry.get("location"), str)
            or not isinstance(entry.get("skills", []), list)
        ):
            raise SourceError(f"{path}: invalid source {entry!r}")
        skills = tuple(_skill_folder(str(f)) for f in entry.get("skills", []))
        kind = KINDS[entry["kind"]]
        found.append(kind(entry["name"], entry["location"], entry.get("ref"), skills))
    return found


def get(name: str) -> Source:
    for source in registered():
        if source.name == name:
            return source
    names = ", ".join(s.name for s in registered()) or "none"
    raise SourceError(f'no source "{name}"; sources: {names}')


def add(spec: str, name: str | None = None, skills: list[str] | None = None) -> Source:
    """Register a git URL or a local folder, optionally with @ref, and fetch it. `skills`:
    folders inside it to take skills from, instead of all of skills/."""
    folders = tuple(_skill_folder(f) for f in skills or [])
    location, ref = _split_ref(spec)
    if _is_git(location):
        kind, default = "git", re.split(r"[/:]", location.rstrip("/"))[-1].removesuffix(".git")
        if Path(location).exists():  # a local repository
            location = str(Path(location).resolve())
    else:
        location = str(Path(location).expanduser().resolve())
        kind, default = "path", Path(location).name
    name = name or re.sub(r"[^a-z0-9_-]+", "-", default.lower()).strip("-")
    if not NAME.fullmatch(name):
        raise SourceError(
            f'"{name}" is not a valid source name; use lowercase letters, digits, - or _ (--name)'
        )
    taken = registered()
    if any(s.name == name for s in taken):
        raise SourceError(f'a source named "{name}" already exists; choose another --name')
    source = KINDS[kind](name, location, ref, folders)
    source.fetch()
    _save([*taken, source])
    return source


def remove(name: str) -> tuple[Source, str]:
    """Unregister a source; returns it and what happened to its files."""
    source = get(name)
    _save([s for s in registered() if s.name != name])
    return source, source.delete()


def _save(found: list[Source]) -> None:
    entries = []
    for s in found:
        entry = {"name": s.name, "kind": s.kind, "location": s.location}
        if s.ref:
            entry["ref"] = s.ref
        if s.skills:
            entry["skills"] = list(s.skills)
        entries.append(entry)
    (state.home() / REGISTRY).write_text(yaml.safe_dump({"sources": entries}, sort_keys=False))


def _skill_folder(folder: str) -> str:
    """A folder inside the source: relative, without "..", in / form."""
    path = Path(folder)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise SourceError(f'"{folder}": skills folders are relative paths inside the source')
    return path.as_posix()


def _split_ref(spec: str) -> tuple[str, str | None]:
    """ "<location>@<ref>" -> (location, ref). An @ that belongs to the address (git@host:...,
    ssh://user@host/...) is not a ref: a ref comes after the repository path."""
    location, at, ref = spec.rpartition("@")
    if not at or not ref or ":" in ref:
        return spec, None
    if not re.search(r"[/:]", location.split("://", 1)[-1]):
        return spec, None
    return location, ref


def _is_git(location: str) -> bool:
    return "://" in location or bool(SCP_LIKE.match(location)) or location.endswith(".git")


def _git(cwd: Path | None, *args: str) -> str:
    where = ["-C", str(cwd)] if cwd else []
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}  # fail instead of asking for a password
    result = subprocess.run(
        ["git", *where, *args], capture_output=True, text=True, check=False, env=env
    )
    if result.returncode != 0:
        raise SourceError(result.stderr.strip() or f"git {' '.join(args)} failed")
    return result.stdout.strip()
