"""The human's checks of a release candidate (docs/release.md, section 4).

    python3 scripts/rc_check.py sandbox [X.Y.ZrcN] [--provider NAME] [--no-ui]
    python3 scripts/rc_check.py upgrade X.Y.ZrcN
    python3 scripts/rc_check.py rollback

Run with `python3` from the repository's root on the RC's commit, never with `uv run`:
that puts the working copy's `.venv/bin/lado` first on PATH, and `upgrade` and
`rollback` run the human's own installed `lado` (they refuse one inside this repository).

`sandbox` installs the RC (by default the newest release on PyPI, refused when that is a
final) with `uv tool install` into a temporary folder, with a LADO home, a tmux socket and
uv tool folders of its own and statistics off, checks it one line each, shows its UI until
Enter, then removes everything with the RC's own `lado uninstall`. A failed check keeps
the folder and prints the command that removes it; Ctrl-C removes it. `upgrade` runs the
human's `lado update X.Y.ZrcN` and, coming from a final, keeps a copy of that final's
database backup in `~/.lado-rc/`, as `lado update` keeps only one backup. `rollback` goes
back to the final of that copy: it asks first, stops the sessions and the UI server, runs
`lado update <final>`, puts the copy back when the RC moved the schema, and starts the
sessions and the UI again. `sandbox` and `upgrade` end with what is left by hand, the items
of CHANGELOG.md's `## X.Y.Z (unreleased)` among them (`release_notes.section`).

Exit 0 when every check passed, 1 for a failed check or a refusal, 2 for a usage error, 130
on Ctrl-C. Standard library only; nothing of LADO is imported.
"""

from __future__ import annotations  # the human's python3 may be older than LADO's

import argparse
import importlib.util
import json
import math
import os
import re
import subprocess
import sys
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # the repository this script is part of
PYPI_JSON = "https://pypi.org/pypi/lado/json"
PYPI_TIMEOUT = 10  # seconds
VERSION = re.compile(r"(\d+)\.(\d+)\.(\d+)(?:rc(\d+))?")  # the only forms LADO publishes
PYPROJECT_VERSION = re.compile(r'^version = "([^"]*)"', re.MULTILINE)
OUTPUT_LINES = 10  # of a failed command's output, under its [FAIL] line
BY_HAND = [
    "[ ] A session with the sdlc kit through one run to its first gate, answered in the UI",
    "[ ] The UI: the chat, a gate's card, the System panel with its pre-release pill",
]


class RcError(Exception):
    """A refusal: one line, exit 1."""


@dataclass(frozen=True, order=True)
class Version:
    """X.Y.Z or X.Y.ZrcN; a final sorts after its release candidates."""

    release: tuple[int, int, int]
    candidate: float  # N of rcN, math.inf for a final
    text: str = field(compare=False)

    @property
    def final(self) -> bool:
        return self.candidate == math.inf

    def __str__(self) -> str:
        return self.text


def parse(text: str) -> Version | None:
    match = VERSION.fullmatch(text.strip())
    if not match:
        return None
    candidate = math.inf if match[4] is None else int(match[4])
    return Version((int(match[1]), int(match[2]), int(match[3])), candidate, match[0])


def fetch_index() -> dict:
    """PyPI's JSON of the package."""
    with urllib.request.urlopen(PYPI_JSON, timeout=PYPI_TIMEOUT) as answer:
        return json.load(answer)


def releases(index: dict) -> list[Version]:
    """The releases of PyPI's JSON in order, but those of another form and yanked ones."""
    found = []
    for text, files in index.get("releases", {}).items():
        version = parse(text)
        if version and not (files and all(f.get("yanked") for f in files)):
            found.append(version)
    return sorted(found)


@dataclass(frozen=True)
class Result:
    code: int
    output: str  # stdout and stderr; empty for a command run on the terminal


def run(
    argv: list[str],
    env: dict[str, str] | None = None,
    terminal: bool = False,
    cwd: Path | None = None,
) -> Result:
    """Every command of the script: its output kept, or with `terminal` the human's
    terminal for its output and its questions."""
    try:
        if terminal:
            return Result(subprocess.run(argv, env=env, cwd=cwd, check=False).returncode, "")
        done = subprocess.run(
            argv,
            env=env,
            cwd=cwd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )
    except OSError as error:  # not on PATH, not executable
        return Result(127, f"{argv[0]}: {error.strerror or error}\n")
    return Result(done.returncode, done.stdout)


class Report:
    """The check lines, `[ok  ]` or `[FAIL]` as `lado doctor` prints them."""

    def __init__(self) -> None:
        self.failed = False

    def ok(self, what: str) -> None:
        print(f"[ok  ] {what}", flush=True)

    def fail(self, what: str, reason: str, output: str = "") -> None:
        self.failed = True
        print(f"[FAIL] {what}: {reason}", flush=True)
        for line in output.rstrip().splitlines()[-OUTPUT_LINES:]:
            print(f"         {line}")


def _release_notes():
    """scripts/release_notes.py, beside this script: the CHANGELOG's rules are its own."""
    path = Path(__file__).resolve().with_name("release_notes.py")
    spec = importlib.util.spec_from_file_location("release_notes", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def checklist(version: Version, changelog: str | None, pyproject: str | None) -> list[str]:
    """What is left to the human: the checks by hand, then each item of the RC's section
    of CHANGELOG.md, then what makes that list doubtful."""
    lines = list(BY_HAND)
    if changelog is None:
        lines.append("warning: no CHANGELOG.md here: run the script from the repository's root")
    else:
        notes = _release_notes()
        try:
            text = notes.section(f"v{version}", changelog)
        except notes.NotesError as error:
            lines.append(f"warning: {error}")
        else:
            lines += [f"[ ] {line[2:]}" for line in text.splitlines() if line.startswith("- ")]
    found = PYPROJECT_VERSION.search(pyproject or "")
    if found and found[1] != str(version):
        lines.append(
            f"warning: pyproject.toml says {found[1]}, not {version}: this checkout is not the "
            "RC's commit, and its CHANGELOG.md may not be the RC's"
        )
    return lines


def _read(path: Path) -> str | None:
    try:
        return path.read_text()
    except OSError:
        return None


def print_checklist(version: Version) -> None:
    print(f"\nLeft to check by hand on LADO {version}:")
    for line in checklist(version, _read(Path("CHANGELOG.md")), _read(Path("pyproject.toml"))):
        print(f"  {line}")


def sandbox(version: Version, provider: str, ui: bool) -> int:
    raise NotImplementedError


def upgrade(version: Version) -> int:
    raise NotImplementedError


def rollback() -> int:
    raise NotImplementedError


def _version(text: str) -> Version:
    version = parse(text)
    if version is None:
        raise argparse.ArgumentTypeError(f"{text!r} is no LADO version (X.Y.Z or X.Y.ZrcN)")
    return version


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rc_check.py", description="The checks of a release candidate (docs/release.md)."
    )
    commands = parser.add_subparsers(dest="command", required=True)
    box = commands.add_parser("sandbox", help="check a clean install of the RC, then remove it")
    box.add_argument("version", nargs="?", type=_version, help="X.Y.ZrcN; the newest on PyPI")
    box.add_argument("--provider", default="claude", help="the session's (default claude)")
    box.add_argument("--no-ui", action="store_true", help="do not open the sandbox's UI")
    up = commands.add_parser("upgrade", help="move your own LADO onto the RC")
    up.add_argument("version", type=_version, help="X.Y.ZrcN")
    commands.add_parser("rollback", help="go back to the final you upgraded from")
    return parser


def _final_refused(version: Version) -> int:
    print(
        f"rc_check: {version} is a final release: name the RC to check (X.Y.ZrcN)",
        file=sys.stderr,
    )
    return 2


def main(argv: list[str]) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "sandbox":
            version = args.version
            if version is None:
                try:
                    found = releases(fetch_index())
                except (OSError, ValueError) as error:
                    Report().fail("PyPI", str(getattr(error, "reason", error)))
                    return 1
                if not found:
                    Report().fail("PyPI", "it lists no release of LADO")
                    return 1
                version = found[-1]
            if version.final:
                return _final_refused(version)
            return sandbox(version, args.provider, not args.no_ui)
        if os.environ.get("LADO_AGENT"):
            raise RcError(
                f"{args.command} is the human's: run it on your terminal, not in an agent"
            )
        if args.command == "upgrade":
            if args.version.final:
                return _final_refused(args.version)
            return upgrade(args.version)
        return rollback()
    except RcError as error:
        print(f"rc_check: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nrc_check: interrupted", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
