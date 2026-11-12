"""The test audit's numbers from a coverage database measured per test.

    python scripts/test_audit.py <.coverage file> [--functions] [--top N] [--json OUT]

The database comes from a run with dynamic contexts, one per test (pytest-cov's
`--cov-context=test`, coverage.py's `[run] dynamic_context` or the like); the way to
measure LADO's layers is in docs/research/test-audit.md, stage 0. Each test's footprint is
what it ran, setup, call and teardown together (pytest-cov's `<nodeid>|setup`, `|run`,
`|teardown`): its branches, (file, from line, to line), when the run measured branches,
else its (file, line). What ran outside any test (a subprocess with no context, import
time) counts for no test. With `--functions` the cases of one
parametrized test are one test, their footprints joined: cases that differ only in data
run the same lines, and that alone says nothing about them.

It prints, and with `--json` writes:

- the tests, the branches (or lines) run, and how many of the tests a greedy set cover
  needs to run every one of them;
- the tests that run no branch (or line) any other test does not, by file;
- the groups of two or more tests whose footprints are identical.

A test on either list is a candidate to look at, never one to remove on these numbers
alone (the rules of section 5 of the audit). The database is read with SQL (coverage.py's
documented schema); a database of lines needs coverage.py itself for their bit sets.
"""

import argparse
import json
import sqlite3
import sys
from collections import defaultdict

Line = tuple  # (file, line) or (file, from line, to line)
PHASES = ("|setup", "|run", "|teardown")


def test_of(context: str, functions: bool = False) -> str | None:
    """The test a dynamic context belongs to, or None for the empty context; with
    `functions`, without its parameters (`test_x[a-1]` is `test_x`)."""
    if not context:
        return None
    for phase in PHASES:
        if context.endswith(phase):
            context = context[: -len(phase)]
            break
    if functions and context.endswith("]") and "[" in context:
        context = context[: context.index("[")]
    return context


def footprints(database: str, functions: bool = False) -> tuple[str, dict[str, set[Line]]]:
    """What each test ran, from a coverage.py database with contexts: "branches" and
    each test's (file, from, to) set when the run measured branches, else "lines" and its
    (file, line) set."""
    db = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
    try:
        files = dict(db.execute("select id, path from file"))
        tests = {
            id_: test_of(context, functions)
            for id_, context in db.execute("select id, context from context")
        }
        result: dict[str, set[Line]] = defaultdict(set)
        if db.execute("select 1 from arc limit 1").fetchone():
            kind = "branches"
            for file_id, context_id, start, end in db.execute(
                "select file_id, context_id, fromno, tono from arc"
            ):
                if tests.get(context_id) is not None:
                    result[tests[context_id]].add((files[file_id], start, end))
        else:
            from coverage.numbits import numbits_to_nums

            kind = "lines"
            for file_id, context_id, bits in db.execute(
                "select file_id, context_id, numbits from line_bits"
            ):
                if tests.get(context_id) is not None:
                    path = files[file_id]
                    result[tests[context_id]].update((path, n) for n in numbits_to_nums(bits))
    finally:
        db.close()
    return kind, dict(result)


def unique_counts(prints: dict[str, set[Line]]) -> dict[str, int]:
    """How many of each test's lines no other test runs."""
    runs: dict[Line, int] = defaultdict(int)
    for lines in prints.values():
        for line in lines:
            runs[line] += 1
    return {test: sum(runs[line] == 1 for line in lines) for test, lines in prints.items()}


def identical_groups(prints: dict[str, set[Line]]) -> list[list[str]]:
    """Groups of two or more tests with the same non-empty footprint, biggest first."""
    by_print: dict[frozenset, list[str]] = defaultdict(list)
    for test, lines in prints.items():
        if lines:
            by_print[frozenset(lines)].append(test)
    groups = [sorted(tests) for tests in by_print.values() if len(tests) > 1]
    return sorted(groups, key=lambda group: (-len(group), group[0]))


def greedy_cover(prints: dict[str, set[Line]]) -> list[str]:
    """A small set of tests that runs every line some test runs (greedy set cover)."""
    left = set().union(*prints.values()) if prints else set()
    chosen: list[str] = []
    remaining = {test: set(lines) for test, lines in prints.items()}
    while left:
        test = max(sorted(remaining), key=lambda name: len(remaining[name] & left))
        gain = remaining.pop(test) & left
        if not gain:
            break
        chosen.append(test)
        left -= gain
    return chosen


def file_of(test: str) -> str:
    return test.split("::", 1)[0]


def report(prints: dict[str, set[Line]], top: int, kind: str = "lines") -> dict:
    unique = unique_counts(prints)
    no_unique = sorted(test for test, count in unique.items() if count == 0)
    by_file: dict[str, int] = defaultdict(int)
    tests_by_file: dict[str, int] = defaultdict(int)
    for test in prints:
        tests_by_file[file_of(test)] += 1
    for test in no_unique:
        by_file[file_of(test)] += 1
    groups = identical_groups(prints)
    cover = greedy_cover(prints)
    lines = set().union(*prints.values()) if prints else set()
    return {
        "kind": kind,
        "tests": len(prints),
        "items": len(lines),
        "cover": len(cover),
        "no_unique": no_unique,
        "no_unique_by_file": sorted(
            ([f, n, tests_by_file[f]] for f, n in by_file.items()), key=lambda r: -r[1]
        ),
        "identical_groups": groups,
        "top": top,
    }


def show(result: dict) -> str:
    tests, top, kind = result["tests"], result["top"], result["kind"]
    one = kind[:-2] if kind == "branches" else kind[:-1]

    def share(n: int) -> str:
        return f"{n} ({100 * n / tests:.0f}%)" if tests else str(n)

    out = [
        f"tests: {tests}, {kind} run: {result['items']}",
        f"greedy cover of every {one}: {share(result['cover'])} tests",
        f"tests with no unique {one}: {share(len(result['no_unique']))}",
        f"groups of identical footprints: {len(result['identical_groups'])}, "
        f"{sum(len(g) for g in result['identical_groups'])} tests",
        "",
        f"no unique {one}, by file (top {top}): no-unique / tests",
    ]
    out += [f"  {n:5} / {total:5}  {f}" for f, n, total in result["no_unique_by_file"][:top]]
    out += ["", f"biggest identical groups (top {top}):"]
    for group in result["identical_groups"][:top]:
        out.append(f"  {len(group)}: {group[0]} ...")
    return "\n".join(out)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("data", help="the .coverage file, measured with a context per test")
    parser.add_argument(
        "--functions", action="store_true", help="a parametrized test's cases as one test"
    )
    parser.add_argument("--top", type=int, default=20)
    parser.add_argument("--json", help="also write the whole result to this file")
    args = parser.parse_args(argv)
    try:
        kind, prints = footprints(args.data, args.functions)
    except (sqlite3.Error, ImportError) as error:
        print(f"test_audit.py: {args.data}: {error}", file=sys.stderr)
        return 2
    if not prints:
        print(f"test_audit.py: {args.data}: no per-test contexts", file=sys.stderr)
        return 2
    result = report(prints, args.top, kind)
    print(show(result))
    if args.json:
        with open(args.json, "w") as out:
            json.dump(result, out, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
