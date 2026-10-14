"""The verdict of ci.yml's job `ci-ok`, the one check the ruleset of `main` requires.

    NEEDS='${{ toJSON(needs) }}' python3 scripts/ci_ok.py

`ci-ok` needs every other job of ci.yml and runs whatever their results (`if: always()`).
It passes only when each of them succeeded. The one job it may see skipped is `smoke`, and
only when the job `changes` said the smoke is not needed (its output `smoke` is `false`).
A cancelled job fails it like a failed one. It prints each job's result, and on stderr
each job that fails it.

Standard library only: ci-ok runs it with the runner's python3, no `uv sync`.
"""

import json
import os
import sys


def problems(needs: dict) -> list[str]:
    """The jobs that fail `ci-ok`, as `<job>: <result>`; none when it passes."""
    if not needs:
        return ["no job to check"]
    smoke_needed = needs.get("changes", {}).get("outputs", {}).get("smoke") != "false"
    found = []
    for job, facts in needs.items():
        result = facts.get("result")
        if result == "success" or (job == "smoke" and result == "skipped" and not smoke_needed):
            continue
        found.append(f"{job}: {result}")
    return found


def main() -> int:
    try:
        needs = json.loads(os.environ.get("NEEDS", ""))
    except ValueError:
        needs = None
    if not isinstance(needs, dict):
        print("ci-ok: NEEDS holds no `toJSON(needs)` object", file=sys.stderr)
        return 1
    for job, facts in needs.items():
        print(f"{job}: {facts.get('result')}")
    found = problems(needs)
    for problem in found:
        print(f"ci-ok: {problem}", file=sys.stderr)
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
