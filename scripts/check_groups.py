"""Run make check's test groups one after another, every group, and fail at the end.

    python scripts/check_groups.py --group <name> <command...> [--group <name> <command...>]

Each group is its name and its command's argv, up to the next `--group`: the shell parses
the command (the Makefile's PYTEST_ARGS with its quotes), never this script. The groups
run in turn, also after one that failed. Exit 5 (pytest: no tests collected, e.g. a -k
that matches nothing in a group) is no failure; any other non-zero exit is, and so is a
command that cannot start. The last line names the groups that failed (exit 1), or says
all passed (exit 0). Ctrl-C stops at once (exit 130).

The Makefile runs the unit, integration and UI tests through it as three pytest runs:
in one run, xdist hands the integration tests, collected first, to two workers, which
run them serially while the others are idle.

Standard library only.
"""

import subprocess
import sys
import time

GROUP = "--group"
NO_TESTS = 5
USAGE = "usage: check_groups.py --group <name> <command...> [--group <name> <command...>]"


def parse(argv: list[str]) -> list[tuple[str, list[str]]] | None:
    """The groups, or None when argv is not --group, a name and a command, repeated."""
    if not argv or argv[0] != GROUP:
        return None
    groups: list[list[str]] = []
    for arg in argv:
        if arg == GROUP:
            groups.append([])
        else:
            groups[-1].append(arg)
    if any(len(group) < 2 for group in groups):
        return None
    return [(group[0], group[1:]) for group in groups]


def run(name: str, command: list[str]) -> bool:
    """Run one group; True unless it failed."""
    started = time.monotonic()
    try:
        code = subprocess.call(command)
    except OSError as error:
        print(f"check: {name} failed (cannot run {command[0]}: {error.strerror})", flush=True)
        return False
    took = f"in {time.monotonic() - started:.0f} s"
    if code == 0:
        print(f"check: {name} passed {took}", flush=True)
    elif code == NO_TESTS:
        print(f"check: {name} collected no tests {took}", flush=True)
    else:
        print(f"check: {name} failed (exit {code}) {took}", flush=True)
    return code in (0, NO_TESTS)


def main(argv: list[str]) -> int:
    groups = parse(argv)
    if groups is None:
        print(USAGE, file=sys.stderr)
        return 2
    try:
        failed = [name for name, command in groups if not run(name, command)]
    except KeyboardInterrupt:
        return 130
    if failed:
        print(f"check: failed: {', '.join(failed)}")
        return 1
    print(f"check: passed: {', '.join(name for name, _ in groups)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
