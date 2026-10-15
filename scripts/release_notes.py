"""A release tag's notes for its GitHub release, from CHANGELOG.md.

    python scripts/release_notes.py <tag>          # the notes, on stdout
    python scripts/release_notes.py --flag <tag>   # --prerelease or --latest

Run by the Release workflow in the repository's root (docs/release.md): before it
publishes to PyPI, so a tag without notes publishes nothing anywhere, and for the GitHub
release after PyPI. A final `vX.Y.Z` takes the section `## X.Y.Z (<date>)`; a release
candidate `vX.Y.ZrcN` takes `## X.Y.Z (unreleased)`, as its changes are not dated until
the final. A section runs to the next `## ` heading or the file's end. The notes are the
section's lines, each wrapped list item joined into one line, then a footer: how to
install or update, the release's Docker image, and the release on PyPI. A tag that is no
release, a missing section or an empty one is one line on stderr, exit 1.

Standard library only.
"""

from __future__ import annotations  # the runner's python3 may be older than LADO's

import re
import sys
from pathlib import Path

TAG = re.compile(r"v(\d+\.\d+\.\d+)(rc\d+)?")
HEADING = re.compile(r"## (\d+\.\d+\.\d+) \((.*)\)\s*")
DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
UNRELEASED = "unreleased"
ITEM = re.compile(r"([-*+]|\d+\.) ")  # a list item's start
PYPI = "https://pypi.org/project/lado/{version}/"
IMAGE = "ghcr.io/ladohq/lado"  # update.IMAGE (a test keeps them the same); no lado import


class NotesError(Exception):
    pass


def _parse(tag: str) -> tuple[str, str, bool]:
    """The section's version of `tag`, the release's own version (`X.Y.ZrcN` for a
    release candidate) and whether it is a release candidate."""
    match = TAG.fullmatch(tag)
    if not match:
        raise NotesError(f"{tag} is no release tag (vX.Y.Z or vX.Y.ZrcN)")
    return match[1], tag[1:], match[2] is not None


def flag(tag: str) -> str:
    """`gh release create`'s flag: a release candidate is never the latest release."""
    return "--prerelease" if _parse(tag)[2] else "--latest"


def _footer(version: str, candidate: bool) -> str:
    if candidate:
        update = (
            "This is a pre-release: a LADO on a final release is not offered it. "
            f"Update to it with `lado update {version}`"
        )
    else:
        update = "Update with `lado update`"
    return (
        f"{update}, or install it with `uv tool install lado=={version}`.\n\n"
        f"Docker: `docker pull {IMAGE}:{version}`.\n\n"
        f"PyPI: {PYPI.format(version=version)}\n"
    )


def notes(tag: str, changelog: str) -> str:
    """The notes of `tag` from the text of CHANGELOG.md."""
    _, release, candidate = _parse(tag)
    return f"{section(tag, changelog)}\n\n---\n\n{_footer(release, candidate)}"


def section(tag: str, changelog: str) -> str:
    """The text of `tag`'s section of CHANGELOG.md, each list item on one line (also
    scripts/rc_check.py's checklist)."""
    version, _, candidate = _parse(tag)
    found: str | None = None  # the section's heading
    lines: list[str] = []
    undated = False
    for line in changelog.splitlines():
        if found is not None:
            if line.startswith("## "):
                break
            lines.append(line)
            continue
        heading = HEADING.fullmatch(line)
        if not heading or heading[1] != version:
            continue
        dated = DATE.fullmatch(heading[2]) is not None
        if (heading[2] == UNRELEASED) if candidate else dated:
            found = line.strip()
        elif heading[2] == UNRELEASED:
            undated = True
    if found is None:
        wanted = f"## {version} ({UNRELEASED if candidate else '<date>'})"
        problem = f'CHANGELOG.md has no section "{wanted}" for {tag}'
        if undated:
            problem += ": its heading still says (unreleased); date it in the release commit"
        raise NotesError(problem)
    body = "\n".join(_unwrap(lines)).strip()
    if not body:
        raise NotesError(f'CHANGELOG.md\'s section "{found}" is empty')
    return body


def _unwrap(lines: list[str]) -> list[str]:
    """Each list item on one line: GitHub shows every newline of a release's notes as a
    line break, and CHANGELOG.md wraps its items, indenting the lines that go on."""
    out: list[str] = []
    for line in lines:
        text = line.strip()
        goes_on = line[:1].isspace() and text and not ITEM.match(text)
        if goes_on and out and out[-1].strip():
            out[-1] = f"{out[-1]} {text}"
        else:
            out.append(line.rstrip())
    return out


def main(argv: list[str]) -> int:
    try:
        if len(argv) == 2 and argv[0] == "--flag":
            print(flag(argv[1]))
        elif len(argv) == 1:
            sys.stdout.write(notes(argv[0], Path("CHANGELOG.md").read_text()))
        else:
            print("usage: release_notes.py [--flag] <tag>", file=sys.stderr)
            return 2
    except NotesError as error:
        print(f"release notes: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
