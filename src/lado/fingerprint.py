"""A git fingerprint of a read-only agent's repository, taken at a turn's start and end
(lado.hooks): what the turn changed. Only git, no LADO state.

A fingerprint holds the agent's HEAD and checked-out branch, the repository's main branch,
tags and stash, and each changed or new file (not ignored, not under .lado/) with the hash of
its content: no copy of a file. Other branches (other agents' work) are left out.
"""

import os
import subprocess
import time

BUDGET = 2.0  # seconds for all of a fingerprint's git commands, at most
MIN_BUDGET = 0.2  # with less time left than this, no git command is started (lado.hooks)

# {"head", "branch", "main": [branch, sha] | None, "refs": {ref: sha} (tags, stash),
#  "files": {path: "<kind> <hash>"}}
Fingerprint = dict


class FingerprintError(RuntimeError):
    """A git command failed or the fingerprint took longer than its budget."""


def take(cwd: str, repo: str, budget: float) -> Fingerprint:
    """The fingerprint of the repository the agent works in at `cwd` (its worktree), with the
    current branch of the session's repository `repo` (none on a detached HEAD), within
    `budget` seconds for all its git commands; FingerprintError else."""
    deadline = time.monotonic() + budget

    def git(*args: str, stdin: str | None = None, ok: tuple[int, ...] = (0,)) -> str:
        left = deadline - time.monotonic()
        if left <= 0:
            raise FingerprintError(f"git took longer than {budget:g} s")
        try:
            # No optional locks: `status` would refresh the index of a worktree other agents
            # may share, and hold its lock.
            result = subprocess.run(
                ["git", "--no-optional-locks", "-C", cwd, *args],
                input=stdin,
                capture_output=True,
                text=True,
                timeout=left,
                check=False,
            )
        except subprocess.TimeoutExpired:
            raise FingerprintError(f"git took longer than {budget:g} s") from None
        except OSError as error:
            raise FingerprintError(f"cannot run git: {error}") from None
        if result.returncode not in ok:
            raise FingerprintError(result.stderr.strip() or f"git {args[0]} failed")
        return result.stdout

    top = git("rev-parse", "--show-toplevel").strip()
    head = git("rev-parse", "-q", "--verify", "HEAD", ok=(0, 1)).strip() or None
    branch = git("symbolic-ref", "-q", "--short", "HEAD", ok=(0, 1)).strip() or None
    main_branch = git("-C", repo, "symbolic-ref", "-q", "--short", "HEAD", ok=(0, 1)).strip()
    patterns = ["refs/tags", "refs/stash"]
    if main_branch:
        patterns.insert(0, f"refs/heads/{main_branch}")
    listed = git("for-each-ref", "--format=%(refname) %(objectname)", *patterns)
    refs = dict(line.split(" ", 1) for line in listed.splitlines() if line)
    main_sha = refs.pop(f"refs/heads/{main_branch}", None) if main_branch else None
    main = [main_branch, main_sha] if main_branch else None
    status = git(
        "status", "--porcelain=v2", "-z", "--untracked-files=all", "--", ":(top,exclude).lado"
    )
    kinds = _kinds(status)
    present = [p for p in kinds if kinds[p] != "deleted" and os.path.isfile(os.path.join(top, p))]
    hashes: dict[str, str] = {}
    if present:
        # hash-object reads paths relative to the folder it runs in: the top here.
        out = git("-C", top, "hash-object", "--stdin-paths", stdin="\n".join(present) + "\n")
        try:
            hashes = dict(zip(present, out.split(), strict=True))
        except ValueError:
            raise FingerprintError("git hash-object gave another number of hashes") from None
    files = {}
    for path, kind in kinds.items():
        if kind != "deleted" and not os.path.lexists(os.path.join(top, path)):
            kind = "deleted"
        files[path] = f"{kind} {hashes.get(path, '-')}"
    return {"head": head, "branch": branch, "main": main, "refs": refs, "files": files}


def _kinds(status: str) -> dict[str, str]:
    """Each path of `git status --porcelain=v2 -z` with what it is: new (untracked),
    deleted or changed."""
    kinds: dict[str, str] = {}
    entries = iter(status.split("\0"))
    for entry in entries:
        if not entry:
            continue
        kind = entry[0]
        if kind == "?":
            kinds[entry[2:]] = "new"
            continue
        fields = entry.split(" ", {"1": 8, "2": 9, "u": 10}.get(kind, 0))
        if kind not in "12u" or len(fields) < 2:
            continue
        if kind == "2":
            next(entries, None)  # a rename's original path
        kinds[fields[-1]] = "deleted" if "D" in fields[1] else "changed"
    return kinds


def diff(before: Fingerprint, after: Fingerprint) -> list[str]:
    """What changed from `before` to `after`, one short line each."""
    lines = []
    if before["head"] != after["head"]:
        lines.append(f"HEAD {_short(before['head'])} -> {_short(after['head'])}")
    if before["branch"] != after["branch"]:
        lines.append(f"on branch {before['branch'] or '(none)'} -> {after['branch'] or '(none)'}")
    was, now = before["main"] or [None, None], after["main"] or [None, None]
    if was[0] == now[0] and was[1] != now[1]:
        lines.append(f"branch {now[0]} moved")
    elif was[0] != now[0] and [before["branch"], after["branch"]] != [was[0], now[0]]:
        # The repository's checkout moved; said once when it is the agent's own checkout.
        lines.append(f"main branch {was[0] or '(none)'} -> {now[0] or '(none)'}")
    old, new = before["refs"], after["refs"]
    for ref in sorted(set(old) | set(new)):
        if old.get(ref) == new.get(ref):
            continue
        if ref == "refs/stash":
            lines.append("stash changed")
            continue
        what = "added" if ref not in old else "deleted" if ref not in new else "moved"
        if ref.startswith("refs/tags/"):
            lines.append(f"tag {ref.removeprefix('refs/tags/')} {what}")
        else:
            lines.append(f"branch {ref.removeprefix('refs/heads/')} {what}")
    old, new = before["files"], after["files"]
    for path in sorted(set(old) | set(new)):
        was, now = old.get(path), new.get(path)
        if was == now:
            continue
        if was is None:
            what = now.split(" ")[0]
        elif now is None:
            # Clean again: an untracked file removed, a changed file put back or committed.
            what = "deleted" if was.startswith("new ") else "changed"
        else:
            what = now.split(" ")[0] if now.split(" ")[0] == "deleted" else "changed"
        lines.append(f"{what}: {path}")
    return lines


def _short(sha: str | None) -> str:
    return sha[:7] if sha else "(none)"
