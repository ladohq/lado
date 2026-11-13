"""Mutation testing for the test audit: which tests catch which bug, and which tests of a
file catch nothing the others do not.

    python scripts/mutants.py run <module> <.coverage> <out.json> [--jobs N] [--timeout S]
        [--kinds compare,...] [--also <file of node ids>]
    python scripts/mutants.py removable <test file> <.coverage> <kills.json>... [--json OUT]

`run` makes each mutant of one module of `src/` (one small change of its code: a
comparison turned round, a condition negated, a constant changed, a call or a `raise`
deleted, a return of None), runs the tests that ran the mutated line, and records every
test that fails: the kill matrix, written to `<out.json>`. The tests come from a coverage
database measured per test (docs/research/test-audit.md, stage 0):

- a line in a function's body: the tests that ran that line;
- a default or a decorator of a function: the tests that ran its body;
- a line run at import time (a constant, a class attribute): every test that ran a line of
  the module, and the node ids of `--also`, for the tests that only read such a value
  (the import itself counts for no test).

With `--judge <test file>` a run answers only what `removable` on that file needs: that
file's tests run in full, and the others, up to the first that fails (`pytest -x`), only
for a mutant one of the file's tests killed. A mutant none of the file's tests runs is
"skipped", one none of them kills "untouched": neither keeps a test of the file. A module
that most of the suite runs (`runtime.py`) costs hours instead of days.

Each mutant runs in a copy of `src/` of its own (one per job), so the working copy is never
touched; `PYTHONPATH` puts the copy first. A run that never imported the mutant is an
error: in the audit's first runs a mutant some tests killed "survived" a later run of the
same tests, which never loaded it. Results go to `<out.json>.partial` as they come,
and a later run with the same arguments goes on from there.

`removable` reads one or more kill matrices (a later run of the same mutant adds its
killers) and the coverage database, and removes the tests of one test file one by one,
those that kill the fewest mutants first: a test goes when every mutant it kills has
another killer left and every branch it runs another test left. What it lists is a
candidate under the rules of section 5 of the audit, never a removal on these numbers
alone.
"""

import argparse
import ast
import concurrent.futures as cf
import copy
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path

PHASES = ("|setup", "|run", "|teardown")
SWAP = {
    ast.Eq: ast.NotEq,
    ast.NotEq: ast.Eq,
    ast.Lt: ast.GtE,
    ast.GtE: ast.Lt,
    ast.Gt: ast.LtE,
    ast.LtE: ast.Gt,
    ast.In: ast.NotIn,
    ast.NotIn: ast.In,
    ast.Is: ast.IsNot,
    ast.IsNot: ast.Is,
}


def test_of(context: str) -> str | None:
    """The test (node id) of a pytest-cov context, None for the empty one."""
    for phase in PHASES:
        context = context.removesuffix(phase)
    return context or None


def function(test: str) -> str:
    """A parametrized case's test function: `t.py::test_x[a]` is `t.py::test_x`."""
    return test.split("[", 1)[0] if test.endswith("]") else test


def mark(tree: ast.AST) -> None:
    """Each node learns its parent; docstrings are marked, to be left alone."""
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            child._parent = node
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            first = node.body[0] if node.body else None
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
                first.value._docstring = True


def sites(tree: ast.AST) -> list[tuple]:
    """Every mutation of a marked tree: (kind, line, node index in ast.walk, detail, apply),
    `apply` changing the node of that index in a copy."""
    found = []
    nodes = list(ast.walk(tree))

    def add(kind, i, node, detail, apply):
        found.append((kind, node.lineno, i, detail, apply))

    for i, node in enumerate(nodes):
        if isinstance(node, ast.Compare):
            for k, op in enumerate(node.ops):
                if type(op) in SWAP:

                    def swap(n, k=k):
                        n.ops[k] = SWAP[type(n.ops[k])]()

                    add("compare", i, node, f"{type(op).__name__}->{SWAP[type(op)].__name__}", swap)
        elif isinstance(node, ast.BoolOp):

            def flip(n):
                n.op = ast.Or() if isinstance(n.op, ast.And) else ast.And()

            add("boolop", i, node, type(node.op).__name__, flip)
        elif isinstance(node, (ast.If, ast.While, ast.IfExp)):

            def negate(n):
                n.test = ast.UnaryOp(op=ast.Not(), operand=n.test)

            add("negate", i, node, type(node).__name__, negate)
        elif isinstance(node, ast.Constant) and not isinstance(
            getattr(node, "_parent", None), ast.JoinedStr
        ):
            value = node.value
            if isinstance(value, bool):

                def invert(n):
                    n.value = not n.value

                add("bool", i, node, str(value), invert)
            elif isinstance(value, int):

                def bump(n):
                    n.value += 1

                add("number", i, node, str(value), bump)
            elif isinstance(value, str) and value and not getattr(node, "_docstring", False):

                def wrap(n):
                    n.value = "XX" + n.value + "XX"

                add("string", i, node, repr(value)[:30], wrap)
        if isinstance(node, ast.Raise) or (
            isinstance(node, ast.Expr) and isinstance(node.value, (ast.Call, ast.Await))
        ):

            def delete(n):
                n.__class__ = ast.Pass
                for field in ("value", "exc", "cause"):
                    if hasattr(n, field):
                        delattr(n, field)

            add("delete", i, node, type(node).__name__, delete)
        if isinstance(node, ast.Return) and node.value is not None:
            if not (isinstance(node.value, ast.Constant) and node.value.value is None):

                def none(n):
                    n.value = ast.Constant(value=None)

                add("return", i, node, "->None", none)
    return found


def tests_by_line(database: str, path: str) -> dict[int, set[str]]:
    """Each line of one file: the tests that ran it."""
    db = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
    row = db.execute("select id from file where path = ?", (path,)).fetchone()
    if row is None:
        sys.exit(f"{database} has no data of {path}")
    contexts = dict(db.execute("select id, context from context"))
    lines = defaultdict(set)
    for ctx, a, b in db.execute(
        "select context_id, fromno, tono from arc where file_id = ?", (row[0],)
    ):
        test = test_of(contexts[ctx])
        if test:
            for n in (a, b):
                if n > 0:
                    lines[n].add(test)
    return lines


def chooser(by_line: dict[int, set[str]], also: set[str]):
    """The tests to run for a mutant of a node: see the module's docstring."""
    everyone = set().union(*by_line.values(), also)

    def tests(node: ast.AST, line: int) -> set[str]:
        child, parent = node, getattr(node, "_parent", None)
        while parent is not None:
            if isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if any(child is statement for statement in parent.body):
                    return by_line.get(line, set())
                body = range(parent.body[0].lineno, parent.end_lineno + 1)
                return set().union(*(by_line.get(n, set()) for n in body))
            if isinstance(parent, (ast.Module, ast.ClassDef)):
                break
            child, parent = parent, getattr(parent, "_parent", None)
        return everyone

    return tests


def run_one(
    work: Path, repo: Path, rel: Path, source: str, tests: list[str], timeout: int, first=False
):
    """One mutant in the copy `work`: its status and the tests that failed (with `first`,
    the first test that failed, `pytest -x`). The module's
    compiled files go first, and a run that compiled none never imported the mutant (a
    stale .pyc, the copy gone, another `lado` first on the path): an error, never
    "survived"."""
    target = work / "src" / rel
    target.write_text(source)
    compiled = target.parent / "__pycache__"
    for old in compiled.glob(f"{target.stem}.*.pyc"):
        old.unlink()
    junit = work / "junit.xml"
    junit.unlink(missing_ok=True)
    environ = {k: v for k, v in os.environ.items() if k != "PYTHONDONTWRITEBYTECODE"}
    started = time.monotonic()
    try:
        run = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "-n0", "-p", "no:cacheprovider",
             "-p", "no:randomly", f"--junitxml={junit}", "-o", "addopts=",
             *(["-x"] if first else []), *tests],
            cwd=repo,
            env={**environ, "PYTHONPATH": str(work / "src")},
            capture_output=True,
            text=True,
            timeout=timeout,
        )  # fmt: skip
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "killed_by": [], "seconds": timeout}
    if not any(compiled.glob(f"{target.stem}.*.pyc")):
        return {"status": "error", "killed_by": [], "seconds": 0, "why": "mutant not imported"}
    failed = []
    if junit.exists():
        for case in ET.parse(junit).getroot().iter("testcase"):
            if case.find("failure") is not None or case.find("error") is not None:
                where = case.get("classname").replace(".", "/") + ".py"
                failed.append(f"{where}::{case.get('name')}")
    status = "killed" if failed else ("survived" if run.returncode == 0 else "error")
    return {"status": status, "killed_by": failed, "seconds": round(time.monotonic() - started, 2)}


def judged(work, repo, rel, source, tests: list[str], timeout: int, judge: str | None):
    """With `judge` (a test file), only what decides whether a test of that file can go:
    its tests run in full, and only when one of them kills the mutant do the others run, up
    to the first that fails (is there another killer). A mutant no test of the file runs
    is skipped, one none of them kills is "untouched": neither keeps a test of the file."""
    if not judge:
        return run_one(work, repo, rel, source, tests, timeout)
    own = [t for t in tests if t.startswith(judge)]
    rest = [t for t in tests if not t.startswith(judge)]
    if not own:
        return {"status": "skipped", "killed_by": [], "seconds": 0}
    mine = run_one(work, repo, rel, source, own, timeout)
    if mine["status"] == "survived":
        return mine | {"status": "untouched"}
    if mine["status"] != "killed" or not rest:
        return mine
    others = run_one(work, repo, rel, source, rest, timeout, first=True)
    return mine | {
        "killed_by": mine["killed_by"] + others["killed_by"],
        "seconds": mine["seconds"] + others["seconds"],
    }


def plan(module: Path, coverage: str, also: set[str], kinds: set[str] | None) -> list[dict]:
    """Every mutant of the module: its key, its source and its tests."""
    tree = ast.parse(module.read_text())
    mark(tree)
    tests = chooser(tests_by_line(coverage, str(module)), also)
    nodes = list(ast.walk(tree))
    out, seen = [], Counter()
    for kind, line, i, detail, apply in sites(tree):
        if kinds and kind not in kinds:
            continue
        mutated = copy.deepcopy(tree)
        apply(list(ast.walk(mutated))[i])
        seen[line, kind, detail] += 1
        out.append({
            "line": line, "kind": kind, "detail": detail, "nth": seen[line, kind, detail],
            "tests": sorted(tests(nodes[i], line)), "source": ast.unparse(mutated),
        })  # fmt: skip
    return out


def key(row: dict) -> tuple:
    return row["line"], row["kind"], row["detail"], row["nth"]


def run(args) -> None:
    repo = Path.cwd()
    module = Path(args.module).resolve()
    rel = module.relative_to(repo / "src")
    also = set(Path(args.also).read_text().splitlines()) if args.also else set()
    mutants = plan(module, args.coverage, also, set(args.kinds.split(",")) if args.kinds else None)
    partial = Path(args.out + ".partial")
    results = {}
    if partial.exists():
        for line in partial.read_text().splitlines():
            row = json.loads(line)
            results[tuple(row["key"])] = row["result"]
    for m in mutants:
        if not m["tests"]:
            results[key(m)] = {"status": "uncovered", "killed_by": [], "seconds": 0}
    todo = [m for m in mutants if key(m) not in results]
    print(
        f"{len(mutants)} mutants, {len(mutants) - len(todo)} known, {len(todo)} to run", flush=True
    )
    works = []
    for i in range(args.jobs):
        work = Path(tempfile.mkdtemp(prefix=f"mutants{i}-"))
        shutil.copytree(repo / "src", work / "src")
        works.append(work)
    started = time.monotonic()
    try:
        with cf.ThreadPoolExecutor(args.jobs) as pool, partial.open("a") as log:
            free, running = list(works), {}
            while todo or running:
                while todo and free:
                    m, work = todo.pop(0), free.pop()
                    job = (work, repo, rel, m["source"], m["tests"], args.timeout, args.judge)
                    running[pool.submit(judged, *job)] = (m, work)
                done, _ = cf.wait(running, return_when=cf.FIRST_COMPLETED)
                for future in done:
                    m, work = running.pop(future)
                    free.append(work)
                    results[key(m)] = future.result()
                    log.write(json.dumps({"key": key(m), "result": results[key(m)]}) + "\n")
                    log.flush()
                    if len(results) % 25 == 0:
                        print(f"{len(results)} done, {time.monotonic() - started:.0f}s", flush=True)
    finally:
        for work in works:
            shutil.rmtree(work, ignore_errors=True)
    rows = [{k: v for k, v in m.items() if k != "source"} | results[key(m)] for m in mutants]
    Path(args.out).write_text(json.dumps(rows, indent=1))
    print(dict(Counter(r["status"] for r in rows)))


def merged(matrices: list[list[dict]]) -> list[dict]:
    """Runs of the same mutants joined: the killers of every run; killed if any run killed
    it, else the status of the last run."""
    rows = {}
    for matrix in matrices:
        for r in matrix:
            old = rows.get(key(r))
            if old:
                by = sorted(set(old["killed_by"]) | set(r["killed_by"]))
                status = "killed" if by else r["status"]
                r = {**r, "killed_by": by, "status": status}
            rows[key(r)] = r
    return list(rows.values())


def footprints(database: str) -> dict[str, set]:
    """Each test function's branches."""
    db = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
    files = dict(db.execute("select id, path from file"))
    names = {}
    for i, context in db.execute("select id, context from context"):
        test = test_of(context)
        names[i] = function(test) if test else None
    prints = defaultdict(set)
    for f, c, a, b in db.execute("select file_id, context_id, fromno, tono from arc"):
        if names.get(c):
            prints[names[c]].add((files[f], a, b))
    return prints


def removable(rows: list[dict], prints: dict[str, set], prefix: str) -> tuple[list, dict]:
    """The tests of one file that can go one by one, the weakest first, and each test
    function's killed mutants."""
    kills = defaultdict(set)
    for i, r in enumerate(rows):
        if r["status"] == "killed":
            for test in r["killed_by"]:
                kills[function(test)].add(i)
    runs = Counter(item for items in prints.values() for item in items)
    killers = Counter(i for test in set(prints) | set(kills) for i in kills[test])
    candidates = sorted({t for t in set(prints) | set(kills) if t.startswith(prefix)})
    gone = []
    for test in sorted(candidates, key=lambda t: (len(kills[t]), t)):
        if any(runs[item] == 1 for item in prints.get(test, ())):
            continue
        if any(killers[i] == 1 for i in kills[test]):
            continue
        gone.append(test)
        killers.subtract(kills[test])
        runs.subtract(prints.get(test, ()))
    return gone, kills


def report(args) -> None:
    rows = merged([json.loads(Path(p).read_text()) for p in args.kills])
    prints = footprints(args.coverage)
    gone, kills = removable(rows, prints, args.prefix)
    status = Counter(r["status"] for r in rows)
    score = status["killed"] / max(1, status["killed"] + status["survived"])
    tests = sorted({t for t in set(prints) | set(kills) if t.startswith(args.prefix)})
    print(f"mutants {len(rows)}: {dict(status)}; killed of killed and survived: {score:.0%}")
    print(f"test functions of {args.prefix}: {len(tests)}; killing nothing: "
          f"{sum(1 for t in tests if not kills[t])}")  # fmt: skip
    print(f"removable one by one, no killed mutant and no branch lost: {len(gone)}")
    for test in gone:
        print(f"  {len(kills[test]):4} kills  {test}")
    if args.json:
        survived = [r for r in rows if r["status"] == "survived"]
        Path(args.json).write_text(json.dumps({"removable": gone, "survived": survived}, indent=1))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)
    one = commands.add_parser("run", help="the kill matrix of one module")
    one.add_argument("module", help="a module under src/, run from the repository's root")
    one.add_argument("coverage", help="a .coverage file measured per test")
    one.add_argument("out")
    one.add_argument("--jobs", type=int, default=os.cpu_count())
    one.add_argument("--timeout", type=int, default=300)
    one.add_argument("--kinds", help="only these kinds of mutant, comma-separated")
    one.add_argument("--also", help="node ids, one a line, run on import-time mutants too")
    one.add_argument(
        "--judge", help="a test file: its tests in full, the others up to the first that fails"
    )
    one.set_defaults(go=run)
    two = commands.add_parser("removable", help="the tests of one file that can go")
    two.add_argument("prefix", help="a test file, e.g. tests/test_codex.py")
    two.add_argument("coverage")
    two.add_argument("kills", nargs="+")
    two.add_argument("--json")
    two.set_defaults(go=report)
    args = parser.parse_args()
    args.go(args)


if __name__ == "__main__":
    main()
