"""The test audit: what each test checks and whether it can fail (openspec capability
test-audit, docs/testing.md "Test audit").

    python scripts/test_audit.py coverage --layer unit|integration|ui [--out DIR] [-- ARGS]

Every command writes JSON to `--out` (default `<temp dir>/lado-test-audit`), outside the
repository; ARGS after `--` go to pytest (node ids, `-n0`, `-k`).

- `coverage`: the lines of `src/lado/` and `scripts/` each test of a layer ran, also in the
  processes it started (scripts/test_audit_plugin.py), as `coverage-<layer>.json`:
  `{node id: {path: [line, ...]}}`, paths relative to the repository.

Standard library, but coverage and pytest-cov (dev dependencies) for `coverage`.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
DEFAULT_OUT = Path(tempfile.gettempdir()) / "lado-test-audit"
LAYERS = {"unit": [], "integration": ["-m", "integration"], "ui": ["-m", "ui"]}
# The audit's own files are not code under audit.
OMIT = "*/scripts/test_audit*.py"

SITECUSTOMIZE = """\
# The test audit's: coverage in every Python process a test starts (COVERAGE_PROCESS_START).
try:
    import coverage
except ImportError:  # a Python without coverage (not LADO's): not measured
    pass
else:
    coverage.process_startup()
"""


def pytest_command(layer: str, args: list[str]) -> list[str]:
    """pytest on one layer, in parallel unless `args` says otherwise (a later `-n` wins)."""
    return [
        sys.executable,
        "-m",
        "pytest",
        *LAYERS[layer],
        "-p",
        "no:cacheprovider",
        "-n",
        "auto",
    ] + args


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1, sort_keys=True) + "\n")


# --- coverage --------------------------------------------------------------------------


def coverage_config(data_file: Path, *, child: bool) -> str:
    """A coverage config of `src/lado/` and `scripts/`; a child's records the test's id from
    LADO_TEST_ID as its static context, and its data when it is ended by SIGTERM too."""
    lines = [
        "[run]",
        f"data_file = {data_file}",
        "source =",
        f"    {ROOT / 'src' / 'lado'}",
        f"    {SCRIPTS}",
        f"omit = {OMIT}",
    ]
    if child:
        lines += ["parallel = true", "sigterm = true", "context = ${LADO_TEST_ID-}"]
    return "\n".join(lines) + "\n"


def run_coverage(layer: str, out: Path, args: list[str]) -> int:
    data = out / f"data-{layer}"
    shutil.rmtree(data, ignore_errors=True)
    (data / "main").mkdir(parents=True)
    (data / "child").mkdir()
    site = data / "site"
    site.mkdir()
    (site / "sitecustomize.py").write_text(SITECUSTOMIZE)
    main_rc = data / "main.coveragerc"
    child_rc = data / "child.coveragerc"
    main_rc.write_text(coverage_config(data / "main" / ".coverage", child=False))
    child_rc.write_text(coverage_config(data / "child" / ".coverage", child=True))

    path = [str(SCRIPTS), os.environ.get("PYTHONPATH", "")]
    env = {
        **os.environ,
        "PYTHONPATH": os.pathsep.join(p for p in path if p),
        "LADO_AUDIT_RC": str(child_rc),
        "LADO_AUDIT_SITE": str(site),
    }
    env.pop("COVERAGE_PROCESS_START", None)
    plugin = ["-p", "test_audit_plugin", "--cov", f"--cov-config={main_rc}"]
    plugin += ["--cov-context=test", "--cov-report="]
    code = subprocess.run(pytest_command(layer, plugin + args), cwd=ROOT, env=env).returncode

    records = export_coverage(data)
    write_json(out / f"coverage-{layer}.json", records)
    print(
        f"coverage: {len(records)} tests of the {layer} layer -> {out / f'coverage-{layer}.json'}"
    )
    if code != 0:
        print(f"coverage: pytest exited {code}; the records are of the tests that ran")
    return code


def export_coverage(data: Path) -> dict[str, dict[str, list[int]]]:
    """The lines per test of pytest's processes (contexts `<node id>|setup|run|teardown`) and
    of the child processes (context `<node id>`, empty outside a test: dropped)."""
    import coverage

    child = coverage.Coverage(data_file=str(data / "child" / ".coverage"), config_file=False)
    child.combine([str(data / "child")], keep=False)
    child.save()
    main = coverage.CoverageData(basename=str(data / "main" / ".coverage"))
    main.read()

    records: dict[str, dict[str, set[int]]] = defaultdict(lambda: defaultdict(set))
    for source, pytest_own in ((main, True), (child.get_data(), False)):
        for file in source.measured_files():
            rel = relative(file)
            if rel is None:
                continue
            for line, contexts in source.contexts_by_lineno(file).items():
                for context in contexts:
                    test = context.rpartition("|")[0] if pytest_own else context
                    if test:
                        records[test][rel].add(line)
    return {
        test: {path: sorted(lines) for path, lines in sorted(files.items())}
        for test, files in sorted(records.items())
    }


def relative(file: str) -> str | None:
    try:
        return Path(file).resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return None


def load_coverage(path: Path) -> dict[str, dict[str, set[int]]]:
    data = json.loads(Path(path).read_text())
    return {
        test: {file: set(lines) for file, lines in files.items()} for test, files in data.items()
    }


# --- durations and flakiness -----------------------------------------------------------

DURATION = re.compile(r"^(\d+\.\d+)s (?:setup|call|teardown) +(\S.*)$")
SUMMARY = re.compile(r"^(?:=+ )?\d+ (?:passed|failed|error).* in (\d+\.\d+)s")
SLOW = 1.0  # seconds: a test this slow names why (docs/testing.md, Which tests we keep)


def run_durations(layer: str, out: Path, args: list[str]) -> int:
    command = pytest_command(layer, ["--durations=0", "--durations-min=0", "-q"] + args)
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    try:
        durations = parse_durations(result.stdout)
    except ValueError as error:
        print(result.stdout[-4000:] + result.stderr[-4000:])
        print(f"durations: {error}")
        return result.returncode or 1
    write_json(out / f"durations-{layer}.json", durations)
    print(f"durations: {len(durations['tests'])} tests, {durations['wall']} s by the clock")
    for test, seconds_ in slow(durations):
        print(f"  {seconds_:6.2f} s  {test}")
    return result.returncode


def parse_durations(text: str) -> dict:
    """`pytest --durations=0 -q`'s output: the wall time and each test's seconds (its setup,
    call and teardown together)."""
    tests: dict[str, float] = defaultdict(float)
    wall = None
    for line in text.splitlines():
        if match := DURATION.match(line):
            tests[match[2]] = round(tests[match[2]] + float(match[1]), 2)
        elif match := SUMMARY.match(line):
            wall = float(match[1])
    if wall is None:
        raise ValueError("no pytest summary line in the output")
    return {"wall": wall, "tests": dict(tests)}


def slow(durations: dict, limit: float = SLOW) -> list[tuple[str, float]]:
    found = [(test, s) for test, s in durations["tests"].items() if s >= limit]
    return sorted(found, key=lambda item: -item[1])


def run_flaky(out: Path, *, days: int, recent: int) -> int:
    """CI's runs of ci.yml on main of the last `days`: the clock and the runners' minutes of
    the `recent` newest, and each job that was green only on a later attempt."""
    if shutil.which("gh") is None:
        return skip_flaky(out, "gh is not available on PATH")
    since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    fields = "databaseId,attempt,createdAt,updatedAt,conclusion"
    listed = gh("run", "list", "--workflow", "ci.yml", "--branch", "main", "--created",
                f">={since}", "--limit", "1000", "--json", fields)  # fmt: skip
    if listed is None:
        return skip_flaky(out, "gh run list failed (not logged in?)")
    runs, reruns, unread = [], [], []
    for index, run in enumerate(listed):
        newest = index < recent
        attempts = {}
        if newest or run["attempt"] > 1:
            for attempt in range(1, run["attempt"] + 1):
                view = gh("run", "view", str(run["databaseId"]), "--attempt", str(attempt),
                          "--json", "jobs")  # fmt: skip
                if view is None:
                    unread.append(f"{run['databaseId']}/{attempt}")
                    print(f"flaky: gh run view {run['databaseId']} --attempt {attempt} failed")
                    continue
                attempts[attempt] = view["jobs"]
        if newest and run["attempt"] in attempts:
            last = attempts[run["attempt"]]
            jobs = {job["name"]: seconds(job["startedAt"], job["completedAt"]) for job in last}
            runs.append({
                "id": run["databaseId"],
                "clock_s": seconds(run["createdAt"], run["updatedAt"]),
                "runner_min": round(sum(jobs.values()) / 60, 2),
                "jobs": jobs,
            })  # fmt: skip
        reruns += rerun_greens(run["databaseId"], attempts)
    result = {"days": days, "runs": runs, "reruns": reruns, "unread": unread}
    write_json(out / "flaky.json", result)
    print(f"flaky: {len(listed)} runs on main in {days} days, {len(reruns)} jobs green on a rerun")
    return 1 if unread else 0


def rerun_greens(run: int, attempts: dict[int, list[dict]]) -> list[dict]:
    """The jobs that failed in an attempt and passed in a later one, with that attempt."""
    found = []
    failed: set[str] = set()
    for attempt in sorted(attempts):
        for job in attempts[attempt]:
            if job["conclusion"] == "failure":
                failed.add(job["name"])
            elif job["conclusion"] == "success" and job["name"] in failed:
                found.append({"run": run, "job": job["name"], "attempt": attempt})
                failed.discard(job["name"])
    return found


def skip_flaky(out: Path, reason: str) -> int:
    print(f"flaky: {reason}; skipped")
    write_json(out / "flaky.json", {"skipped": reason})
    return 0


def gh(*args: str, tries: int = 3):
    """`gh`'s JSON answer, or None when it fails `tries` times (GitHub's API fails at times)."""
    for _ in range(tries):
        result = subprocess.run(["gh", *args], capture_output=True, text=True)
        if result.returncode == 0:
            return json.loads(result.stdout)
    return None


def seconds(start: str, end: str) -> int:
    def parse(stamp: str) -> datetime:
        return datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ")

    return int((parse(end) - parse(start)).total_seconds())


# --- the command line ------------------------------------------------------------------


def main(argv: list[str]) -> int:
    args, rest = split_args(argv)
    parser = argparse.ArgumentParser(prog="test_audit.py", description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    commands = parser.add_subparsers(dest="command", required=True)

    def command(name: str, help: str) -> argparse.ArgumentParser:
        sub = commands.add_parser(name, help=help)
        sub.add_argument("--out", type=Path, default=argparse.SUPPRESS)
        return sub

    command("coverage", "the lines each test runs").add_argument(
        "--layer", choices=LAYERS, required=True
    )
    command("durations", "each test's time").add_argument("--layer", choices=LAYERS, required=True)
    flaky = command("flaky", "CI's runs on main and the jobs green on a rerun")
    flaky.add_argument("--days", type=int, default=30)
    flaky.add_argument("--recent", type=int, default=10, help="runs whose jobs are timed")
    opts = parser.parse_args(args)
    out = opts.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    if opts.command == "coverage":
        return run_coverage(opts.layer, out, rest)
    if opts.command == "durations":
        return run_durations(opts.layer, out, rest)
    if opts.command == "flaky":
        return run_flaky(out, days=opts.days, recent=opts.recent)
    return 2


def split_args(argv: list[str]) -> tuple[list[str], list[str]]:
    """The audit's arguments, and pytest's after `--`."""
    if "--" in argv:
        at = argv.index("--")
        return argv[:at], argv[at + 1 :]
    return argv, []


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
