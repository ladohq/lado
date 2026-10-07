"""Run make check's test groups one after another, every group, and fail at the end.

    python scripts/check_groups.py <name> <command> [<name> <command> ...]

Each command is one string, split as a shell would (shlex), and runs in turn, also after
one that failed. Exit 5 (pytest: no tests collected, e.g. a -k that matches nothing in a
group) is no failure; any other non-zero exit is. The last line names the groups that
failed (exit 1), or says all passed (exit 0). Ctrl-C stops at once (exit 130).

The Makefile runs the unit, integration and UI tests through it as three pytest runs:
in one run, xdist hands the integration tests, collected first, to two workers, which
run them serially while the others are idle.

Standard library only.
"""

import shlex
import subprocess
import sys
import time

NO_TESTS = 5


def run(name: str, command: str) -> bool:
    """Run one group; True unless it failed."""
    started = time.monotonic()
    code = subprocess.call(shlex.split(command))
    took = f"in {time.monotonic() - started:.0f} s"
    if code == 0:
        print(f"check: {name} passed {took}", flush=True)
    elif code == NO_TESTS:
        print(f"check: {name} collected no tests {took}", flush=True)
    else:
        print(f"check: {name} failed (exit {code}) {took}", flush=True)
    return code in (0, NO_TESTS)


def main(argv: list[str]) -> int:
    if not argv or len(argv) % 2:
        print("usage: check_groups.py <name> <command> [<name> <command> ...]", file=sys.stderr)
        return 2
    groups = list(zip(argv[::2], argv[1::2], strict=True))
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
