"""The git cache: repositories LADO takes kits and skill packs from, one clone per version.

A git address is always pinned to a tag or a commit (`<address>@<ref>`), never a branch:
what a kit gets must not depend on when it was fetched. Each (address, ref) is cloned once
into

    LADO_HOME/cache/<repo>-<sha256(address)[:8]>/<quote(ref)>/

and read from there ever after, offline too: a clone that is there is never fetched again.
A clone is made in a temporary folder beside it and renamed into place, so no process sees
half a clone; of two processes cloning at once, the one that loses removes its copy.
Nothing removes old clones yet.

Skill packs (kits.fetch) and `lado kits add/update` both use fetch_pinned. A kit is pinned
to a version tag vX.Y.Z (VERSION_TAG); remote_tags is the one look at a remote's tags, the
only network use besides cloning: the latest version (latest, by semver precedence) and
whether a tag was moved since its clone was made.

The clone of a marketplace (lado.marketplaces) follows its main branch instead:
clone_branch makes it, refresh brings it up to date. All of LADO's git commands run here.
"""

import hashlib
import os
import re
import shutil
import subprocess
import tempfile
from collections.abc import Iterable
from pathlib import Path
from urllib.parse import quote, unquote

from lado import state

VERSION_TAG = re.compile(r"v(\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?)")
# git@host:owner/repo: an scp-like git address.
SCP_LIKE = re.compile(r"[\w.-]+@[\w.-]+:")


class GitError(RuntimeError):
    pass


def root() -> Path:
    return state.home() / "cache"


def is_git(location: str) -> bool:
    """A git address: a URL, git@host:..., or a path ending in .git."""
    return "://" in location or bool(SCP_LIKE.match(location)) or location.endswith(".git")


def split_ref(spec: str) -> tuple[str, str | None]:
    """ "<location>@<ref>" -> (location, ref). An @ that belongs to the address (git@host:...,
    ssh://user@host/...) is not a ref: a ref comes after the repository path."""
    location, at, ref = spec.rpartition("@")
    if not at or not ref or ":" in ref:
        return spec, None
    if not re.search(r"[/:]", location.split("://", 1)[-1]):
        return spec, None
    return location, ref


def clone_dir(address: str, ref: str) -> Path:
    """Where the clone of `address` at `ref` is (or will be)."""
    name = re.split(r"[/:]", address.rstrip("/"))[-1].removesuffix(".git") or "repo"
    digest = hashlib.sha256(address.encode()).hexdigest()[:8]
    return root() / f"{name}-{digest}" / quote(ref, safe="")


def fetch_pinned(address: str, ref: str) -> Path:
    """The clone of `address` checked out at the tag or commit `ref`; cloned on first use."""
    target = clone_dir(address, ref)
    if target.is_dir():
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = Path(tempfile.mkdtemp(prefix=f".{target.name}-", dir=target.parent))
    try:
        _clone(address, ref, temp)
        try:
            os.rename(temp, target)
        except OSError:
            if not target.is_dir():
                raise
            shutil.rmtree(temp, ignore_errors=True)  # another process was first
    except (GitError, OSError) as exc:
        shutil.rmtree(temp, ignore_errors=True)
        raise GitError(f"cannot get {address}@{ref}: {exc}") from None
    return target


def _clone(address: str, ref: str, folder: Path) -> None:
    _git(None, "clone", "--quiet", "--no-checkout", address, str(folder))
    if _git(folder, "branch", "--remotes", "--list", f"origin/{ref}"):
        raise GitError(f"{ref} is a branch of {address}; pin a tag or a commit")
    try:
        _git(folder, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}")
    except GitError:
        raise GitError(f'no tag or commit "{ref}"') from None
    # A detached HEAD: LADO only reads the clone.
    _git(folder, "checkout", "--quiet", "--detach", ref)


def clone_root(path: Path) -> Path | None:
    """The clone in the cache that `path` is in, or None when it is not in the cache."""
    try:
        parts = Path(path).resolve().relative_to(root().resolve()).parts
    except ValueError:
        return None
    return root().resolve() / parts[0] / parts[1] if len(parts) >= 2 else None


def address(clone: Path) -> str:
    """The address `clone` was cloned from."""
    return _git(clone, "remote", "get-url", "origin")


def ref(clone: Path) -> str:
    """The tag or commit `clone` was pinned to: its folder's name."""
    return unquote(clone.name)


def versions(clone: Path) -> list[str]:
    """The versions the tags vX.Y.Z on the clone's commit give it."""
    tags = _git(clone, "tag", "--points-at", "HEAD").split()
    return [m.group(1) for t in tags if (m := VERSION_TAG.fullmatch(t))]


def _precedence(version: str) -> tuple:
    """The sort key of a version X.Y.Z[-pre] by semver precedence: a pre-release is lower
    than its release; its dot-separated identifiers compare in turn, numbers as numbers and
    lower than words, and a longer list is higher when the rest is equal."""
    core, _, pre = version.partition("-")
    numbers = tuple(int(n) for n in core.split("."))
    if not pre:
        return (numbers, (1,))
    ids = tuple((0, int(i), "") if i.isdigit() else (1, 0, i) for i in pre.split("."))
    return (numbers, (0, ids))


def sorted_versions(tags: Iterable[str]) -> list[str]:
    """The version tags vX.Y.Z[-pre] among `tags`, lowest first."""
    found = [t for t in tags if VERSION_TAG.fullmatch(t)]
    return sorted(found, key=lambda t: _precedence(t[1:]))


def latest(tags: Iterable[str], pre: bool = False) -> str | None:
    """The highest release tag among `tags`, or with `pre` the highest version tag of all;
    None when there is none."""
    found = [t for t in sorted_versions(tags) if pre or "-" not in t]
    return found[-1] if found else None


def remote_tags(address: str) -> dict[str, str]:
    """Each tag of the repository at `address` with the commit it points to (an annotated
    tag's commit, not its tag object). Uses the network."""
    try:
        output = _git(None, "ls-remote", "--tags", address)
    except GitError as exc:
        raise GitError(f"cannot read the tags of {address}: {exc}") from None
    tags: dict[str, str] = {}
    for line in output.splitlines():
        commit, _, name = line.partition("\t")
        name = name.removeprefix("refs/tags/")
        if name.endswith("^{}"):
            tags[name[:-3]] = commit
        else:
            tags.setdefault(name, commit)
    return tags


def clone_branch(address: str, folder: Path) -> None:
    """Clone `address` at its main branch into `folder`, which must not exist; made in a
    temporary folder beside it and renamed, so no one sees half a clone."""
    folder.parent.mkdir(parents=True, exist_ok=True)
    temp = Path(tempfile.mkdtemp(prefix=f".{folder.name}-", dir=folder.parent))
    try:
        _git(None, "clone", "--quiet", address, str(temp))
        os.rename(temp, folder)
    except (GitError, OSError) as exc:
        shutil.rmtree(temp, ignore_errors=True)
        raise GitError(f"cannot clone {address}: {exc}") from None


def refresh(folder: Path) -> None:
    """Bring a clone made by clone_branch to its remote's main branch now."""
    try:
        _git(folder, "fetch", "--quiet", "--prune", "origin")
        _git(folder, "remote", "set-head", "origin", "--auto")
        _git(folder, "checkout", "--quiet", "--detach", "origin/HEAD")
    except GitError as exc:
        raise GitError(f"cannot update {folder}: {exc}") from None


def commit(clone: Path) -> str:
    """The commit `clone` is at."""
    return _git(clone, "rev-parse", "HEAD")


def _git(cwd: Path | None, *args: str) -> str:
    where = ["-C", str(cwd)] if cwd else []
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}  # fail instead of asking for a password
    result = subprocess.run(
        ["git", *where, *args], capture_output=True, text=True, check=False, env=env
    )
    if result.returncode != 0:
        raise GitError(result.stderr.strip() or f"git {' '.join(args)} failed")
    return result.stdout.strip()
