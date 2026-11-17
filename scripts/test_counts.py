"""The count of LADO's Python tests per layer, as a Markdown table for CI's summary.

    python scripts/test_counts.py [pytest arguments]

It collects every test under the repository's tests (no `-m`: all layers), runs none, and
puts each in the layer of its marker (`container`, `ui`, `integration`, `live`, `smoke`;
none is `unit`): its test functions, and its cases (a parametrized function's each one).
CI's job `unit` writes it to the run's summary, so that a pull request's growth of the
suite shows next to main's (docs/testing.md, When to add, merge or remove a test). A
collection error fails it, as it fails the tests.
"""

import io
import sys
from collections import defaultdict
from contextlib import redirect_stdout

import pytest

# A test's layer is its first marker of these; a test of none is a unit test.
LAYERS = ("unit", "integration", "ui", "smoke", "live", "container")


class Collector:
    def __init__(self):
        self.cases = defaultdict(set)

    def pytest_collection_finish(self, session):
        for item in session.items:
            marks = {mark.name for mark in item.iter_markers()}
            layer = next((name for name in LAYERS[1:] if name in marks), "unit")
            self.cases[layer].add(item.nodeid)


def function(nodeid: str) -> str:
    """A case's test function: `test_x[a-1]` is `test_x`."""
    return nodeid.split("[", 1)[0]


def table(cases: dict[str, set[str]]) -> str:
    rows = ["| layer | test functions | cases |", "|---|---:|---:|"]
    total_functions = total_cases = 0
    for layer in LAYERS:
        ids = cases.get(layer, set())
        functions = len({function(i) for i in ids})
        rows.append(f"| {layer} | {functions} | {len(ids)} |")
        total_functions += functions
        total_cases += len(ids)
    rows.append(f"| **all** | **{total_functions}** | **{total_cases}** |")
    return "\n".join(rows) + "\n"


def main(argv: list[str]) -> int:
    collector = Collector()
    # addopts holds the default run's `-m`, which would leave the other layers out.
    # pytest's own output (a line per test) only on a failure.
    output = io.StringIO()
    with redirect_stdout(output):
        code = pytest.main(
            ["--collect-only", "-q", "-o", "addopts=", "-p", "no:cacheprovider", *argv],
            plugins=[collector],
        )
    if code != 0:
        print(output.getvalue(), file=sys.stderr)
        print(f"collection failed ({code})", file=sys.stderr)
        return int(code)
    print("### Python tests per layer\n")
    print(table(collector.cases))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
