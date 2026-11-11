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
import shutil
import subprocess
import sys
import tempfile
from collections import defaultdict
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


# --- the command line ------------------------------------------------------------------


def main(argv: list[str]) -> int:
    args, rest = split_args(argv)
    parser = argparse.ArgumentParser(prog="test_audit.py", description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    commands = parser.add_subparsers(dest="command", required=True)
    cov = commands.add_parser("coverage", help="the lines each test runs")
    cov.add_argument("--layer", choices=LAYERS, required=True)
    cov.add_argument("--out", type=Path, default=argparse.SUPPRESS)
    opts = parser.parse_args(args)
    out = opts.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    if opts.command == "coverage":
        return run_coverage(opts.layer, out, rest)
    return 2


def split_args(argv: list[str]) -> tuple[list[str], list[str]]:
    """The audit's arguments, and pytest's after `--`."""
    if "--" in argv:
        at = argv.index("--")
        return argv[:at], argv[at + 1 :]
    return argv, []


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
