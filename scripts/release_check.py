"""Check that a final release is the code of its last release candidate.

    python scripts/release_check.py <tag>

Run by the Release workflow before it builds, in a checkout with every tag and the history
(docs/release.md). A tag `vX.Y.Z` is a final release; any other tag (a release candidate
`vX.Y.ZrcN`, a tag that is no version) passes untouched. A final's last release candidate
is its tag `vX.Y.ZrcN` with the highest N. Without one, a minor release (Z = 0) fails and
a patch passes. With one, the final may differ from it only in CHANGELOG.md, the
`version = "..."` line of pyproject.toml and that of the `lado` package in uv.lock (a
dependency's version there is no release's change): each other file, and each other
changed line of those two, is one line on stderr, and the exit is 1.

Standard library only.
"""

from __future__ import annotations  # the runner's python3 may be older than LADO's

import re
import subprocess
import sys

FINAL = re.compile(r"v(\d+)\.(\d+)\.(\d+)")
FREE = {"CHANGELOG.md"}  # free text: the final's commit dates it
LOCK = "uv.lock"
VERSIONED = ("pyproject.toml", LOCK)  # only their version lines may change
VERSION_LINE = re.compile(r'[+-]version = "[^"]*"')
PACKAGE = "lado"  # in uv.lock only its own block's version line, never a dependency's
LOCK_NAME = re.compile(r'name = "([^"]*)"')
HUNK = re.compile(r"@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@")


def git(*args: str) -> str:
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True).stdout


def last_candidate(final: str) -> str | None:
    """The tag of `final`'s release candidate with the highest number, or None."""
    numbered = re.compile(re.escape(final) + r"rc(\d+)")
    found = [numbered.fullmatch(tag) for tag in git("tag", "--list", f"{final}rc*").split()]
    found = [match for match in found if match]
    if not found:
        return None
    return max(found, key=lambda match: int(match[1]))[0]


def packages(tag: str, path: str) -> list[str | None]:
    """For each line of uv.lock at `tag`, the name of the `[[package]]` block it is in, or
    None before the first block."""
    names, name = [], None
    for line in git("show", f"{tag}:{path}").splitlines():
        if line == "[[package]]":
            name = ""  # its `name = ` line comes first in the block
        elif name == "" and (found := LOCK_NAME.fullmatch(line)):
            name = found[1]
        names.append(name)
    return names


def changed_lines(candidate: str, final: str) -> list[tuple[str, str, str | None]]:
    """Each changed line of VERSIONED between the two tags, with its file and, in uv.lock,
    the package whose block it is in (on the side the line is on)."""
    lines, path, numbers = [], "", {}
    blocks: dict[str, list[str | None]] = {}
    diff = git("diff", "-U0", candidate, final, "--", *VERSIONED)
    for line in diff.splitlines():
        if line.startswith(("+++ ", "--- ")):
            name = line[4:]
            if name != "/dev/null":
                path = name[2:]  # a/… or b/…
        elif hunk := HUNK.match(line):
            numbers = {"-": int(hunk[1]), "+": int(hunk[2])}  # the next line's number
        elif line.startswith(("+", "-")):
            side = line[0]
            package = None
            if path == LOCK:
                tag = candidate if side == "-" else final
                if tag not in blocks:  # one `git show` per side
                    blocks[tag] = packages(tag, path)
                package = blocks[tag][numbers[side] - 1]
            numbers[side] += 1
            lines.append((path, line, package))
    return lines


def problems(tag: str) -> tuple[list[str], str]:
    """What keeps `tag` from being released, and what was checked."""
    found = FINAL.fullmatch(tag)
    if found is None:
        return [], f"{tag} is no final release: nothing to check"
    candidate = last_candidate(tag)
    if candidate is None:
        if found[3] == "0":
            return [f"{tag} needs a release candidate: tag {tag}rc1 first"], ""
        return [], f"{tag} is a patch without a release candidate"
    wrong = [
        f"{tag} differs from {candidate} in {path}"
        for path in git("diff", "--name-only", candidate, tag).splitlines()
        if path not in FREE and path not in VERSIONED
    ]
    wrong += [
        f"{tag} changes a line of {path} that is not its version: {line}"
        for path, line, package in changed_lines(candidate, tag)
        if not (VERSION_LINE.fullmatch(line) and (path != LOCK or package == PACKAGE))
    ]
    return wrong, f"{tag} is the code of {candidate}"


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("usage: release_check.py <tag>", file=sys.stderr)
        return 2
    wrong, checked = problems(argv[0])
    for line in wrong:
        print(line, file=sys.stderr)
    if wrong:
        return 1
    print(checked)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
