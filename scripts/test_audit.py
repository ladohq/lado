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
import ast
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import NamedTuple

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


# --- subsets ---------------------------------------------------------------------------


def family(test: str) -> str:
    """A test's function: its node id without a parametrized case's `[...]`."""
    return test.split("[", 1)[0]


def subset_candidates(cov: dict[str, dict[str, set[int]]]) -> list[tuple[str, str]]:
    """Each test whose lines are all among one other test's of `cov`, with the closest such
    test (the fewest lines); cases of one function are not compared, equal sets give one pair,
    and a test that ran none of our lines is no candidate (`no_code`)."""
    sets = {
        test: frozenset((file, line) for file, lines in files.items() for line in lines)
        for test, files in cov.items()
    }
    sets = {test: lines for test, lines in sets.items() if lines}
    index: dict[tuple[str, int], set[str]] = defaultdict(set)
    for test, lines in sets.items():
        for line in lines:
            index[line].add(test)
    found = []
    for test, lines in sorted(sets.items()):
        rarest = min(lines, key=lambda line: len(index[line]))
        covering = [
            other
            for other in index[rarest]
            if family(other) != family(test)
            and lines <= sets[other]
            and (len(sets[other]) > len(lines) or other < test)
        ]
        if covering:
            found.append((test, min(covering, key=lambda other: (len(sets[other]), other))))
    return found


def no_code(cov: dict[str, dict[str, set[int]]]) -> list[str]:
    return sorted(test for test, files in cov.items() if not any(files.values()))


def run_subsets(out: Path) -> int:
    result = {}
    for layer in LAYERS:
        path = out / f"coverage-{layer}.json"
        if not path.exists():
            print(f"subsets: no {path.name}; run `coverage --layer {layer}` first")
            continue
        cov = load_coverage(path)
        pairs = subset_candidates(cov)
        result[layer] = {"tests": len(cov), "candidates": pairs, "no_code": no_code(cov)}
        print(f"subsets: {layer}: {len(pairs)} candidates of {len(cov)} tests")
    write_json(out / "subsets.json", result)
    return 0 if result else 1


# --- pseudo-tested functions -----------------------------------------------------------


class Function(NamedTuple):
    qualname: str
    node: ast.FunctionDef | ast.AsyncFunctionDef
    lines: range  # its body's, the docstring's included


def functions(source: str) -> list[Function]:
    """The functions and methods of a module (not those inside a function) whose body does
    something: one that is only `pass`, `...` or `return None` has nothing to empty."""
    found = []

    def walk(body: list[ast.stmt], prefix: str) -> None:
        for node in body:
            if isinstance(node, ast.ClassDef):
                walk(node.body, f"{prefix}{node.name}.")
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not empty(node):
                lines = range(node.body[0].lineno, node.body[-1].end_lineno + 1)
                found.append(Function(prefix + node.name, node, lines))

    walk(ast.parse(source).body, "")
    return found


def empty(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    body = node.body
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
        body = body[1:]  # its docstring
    for statement in body:
        if isinstance(statement, ast.Pass):
            continue
        if isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Constant):
            continue  # `...`
        if isinstance(statement, ast.Return) and (
            statement.value is None
            or (isinstance(statement.value, ast.Constant) and statement.value.value is None)
        ):
            continue
        return False
    return True


def find(source: str, qualname: str) -> ast.FunctionDef | ast.AsyncFunctionDef:
    for function in functions(source):
        if function.qualname == qualname:
            return function.node
    raise KeyError(qualname)


def body_span(source: str, qualname: str) -> tuple[int, int]:
    """The first and the last line of a function's body."""
    node = find(source, qualname)
    return node.body[0].lineno, node.body[-1].end_lineno


def is_generator(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    stack = list(node.body)
    while stack:
        child = stack.pop()
        if isinstance(child, (ast.Yield, ast.YieldFrom)):
            return True
        if not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
            stack.extend(ast.iter_child_nodes(child))
    return False


def empty_body(source: str, qualname: str) -> str:
    """`source` with the body of function `qualname` replaced by `return None` (a generator's
    by `return` and an unreachable `yield`); every other character stays."""
    node = find(source, qualname)
    first, last = node.body[0], node.body[-1]
    lines = source.encode().splitlines(keepends=True)
    prefix = lines[first.lineno - 1][: first.col_offset]
    suffix = lines[last.end_lineno - 1][last.end_col_offset :]
    if not is_generator(node):
        replacement = b"return None"
    elif prefix.strip():
        replacement = b"return; yield"  # a body on the line of its `def`
    else:
        replacement = b"return\n" + prefix + b"yield"
    mutated = lines[: first.lineno - 1] + [prefix + replacement + suffix] + lines[last.end_lineno :]
    return b"".join(mutated).decode()


CORE = ("runtime", "hooks", "state", "runs", "flows")
# pytest's exit codes that say a test failed: 1, and 2 when `-x` stopped an xdist run (or a
# test module no longer imports).
KILLED = (1, 2)


def run_pseudo(
    out: Path, *, repo: Path, modules: list[str], coverage: list[Path], timeout: float
) -> int:
    """Empty each function of `modules` in a copy of `repo` (its HEAD) and run the tests that
    executed it; one no test fails for is pseudo-tested. `pseudo.json` under `out`."""
    records: dict[str, dict[str, set[int]]] = {}
    for path in coverage:
        records.update(load_coverage(path))
    copy = out / "pseudo-copy"
    remove_copy(repo, copy)
    git(repo, "worktree", "add", "--detach", "--quiet", str(copy), "HEAD")
    env = {**os.environ, "PYTHONPATH": str(copy / "src"), "PYTHONDONTWRITEBYTECODE": "1"}
    try:
        # From `out`, not the copy: `-c` would put its cwd first on sys.path.
        where = subprocess.run(
            [sys.executable, "-c", "import lado; print(lado.__file__)"],
            cwd=out, env=env, capture_output=True, text=True,
        ).stdout.strip()  # fmt: skip
        package = (copy / "src" / "lado").resolve()
        if not where or not Path(where).resolve().is_relative_to(package):
            print(f"pseudo: the copy imports lado from {where or 'nowhere'}, not from {package}")
            return 2
        result = {"head": git(repo, "rev-parse", "HEAD").strip(), "modules": modules}
        result |= {"pseudo": {}, "killed": [], "timeout": [], "errors": {}, "not_covered": []}
        result["seconds"] = {}
        for module in modules:
            started = time.monotonic()
            pseudo_module(copy, env, module, records, timeout, result)
            result["seconds"][module] = round(time.monotonic() - started)
        write_json(out / "pseudo.json", result)
        counts = {key: len(result[key]) for key in ("pseudo", "killed", "timeout", "not_covered")}
        print(f"pseudo: {counts}")
        return 1 if result["errors"] else 0
    except KeyboardInterrupt:
        print("pseudo: interrupted; the copy is removed")
        return 130
    finally:
        remove_copy(repo, copy)


def pseudo_module(copy: Path, env: dict, module: str, records: dict, timeout: float, result: dict):
    rel = f"src/lado/{module}.py"
    path = copy / rel
    source = path.read_text()
    try:
        for function in functions(source):
            name = f"{module}.{function.qualname}"
            tests = sorted(
                test
                for test, files in records.items()
                if any(line in function.lines for line in files.get(rel, ()))
            )
            if not tests:
                result["not_covered"].append(name)
                continue
            print(f"pseudo: {name} ({len(tests)} tests)", flush=True)
            path.write_text(empty_body(source, function.qualname))
            try:
                code = run_tests(copy, env, tests, timeout)
            finally:
                path.write_text(source)
            if code is None:
                result["timeout"].append(name)
            elif code == 0:
                result["pseudo"][name] = tests
            elif code in KILLED:
                result["killed"].append(name)
            else:
                log = (copy.parent / "pseudo-tests.log").read_text()[-2000:]
                result["errors"][name] = {"code": code, "log": log}
                print(f"pseudo: {name}: pytest exited {code}")
    finally:
        path.write_text(source)


def run_tests(copy: Path, env: dict, tests: list[str], timeout: float) -> int | None:
    """pytest on `tests` in the copy, stopping at the first failure: its exit code, or None
    when it ran over `timeout` seconds (then it and its workers are killed)."""
    args = copy.parent / "pseudo-tests.txt"
    args.write_text("\n".join(tests) + "\n")
    workers = "0" if len(tests) <= 8 else "auto"
    command = [sys.executable, "-m", "pytest", "-o", "addopts=", "-x", "-q"]
    command += ["-p", "no:cacheprovider", "-n", workers, f"@{args}"]
    with open(copy.parent / "pseudo-tests.log", "w") as log:
        process = subprocess.Popen(
            command,
            cwd=copy,
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    try:
        return process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        return None
    finally:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()


def remove_copy(repo: Path, copy: Path) -> None:
    if copy.exists():
        subprocess.run(["git", "-C", str(repo), "worktree", "remove", "--force", str(copy)],
                       capture_output=True)  # fmt: skip
        shutil.rmtree(copy, ignore_errors=True)
    subprocess.run(["git", "-C", str(repo), "worktree", "prune"], capture_output=True)


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    ).stdout


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
    command("subsets", "tests whose lines are all another test's")
    pseudo = command("pseudo", "functions no test fails for when emptied")
    pseudo.add_argument("--repo", type=Path, default=ROOT)
    pseudo.add_argument("--modules", default=",".join(CORE), help="of src/lado/, by commas")
    pseudo.add_argument("--coverage", type=Path, action="append", help="default: the unit layer's")
    pseudo.add_argument("--timeout", type=float, default=60, help="seconds per function")
    opts = parser.parse_args(args)
    out = opts.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    if opts.command == "coverage":
        return run_coverage(opts.layer, out, rest)
    if opts.command == "durations":
        return run_durations(opts.layer, out, rest)
    if opts.command == "flaky":
        return run_flaky(out, days=opts.days, recent=opts.recent)
    if opts.command == "subsets":
        return run_subsets(out)
    if opts.command == "pseudo":
        coverage = opts.coverage or [out / "coverage-unit.json"]
        modules = opts.modules.split(",")
        return run_pseudo(
            out, repo=opts.repo.resolve(), modules=modules, coverage=coverage, timeout=opts.timeout
        )
    return 2


def split_args(argv: list[str]) -> tuple[list[str], list[str]]:
    """The audit's arguments, and pytest's after `--`."""
    if "--" in argv:
        at = argv.index("--")
        return argv[:at], argv[at + 1 :]
    return argv, []


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
