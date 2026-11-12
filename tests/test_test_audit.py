"""scripts/test_audit.py: the test audit's numbers from a coverage database per test."""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import coverage
import pytest

ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts" / "test_audit.py"

spec = importlib.util.spec_from_file_location("test_audit", SCRIPT)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def test_a_context_is_its_test_whatever_the_phase():
    assert audit.test_of("tests/test_a.py::test_x|setup") == "tests/test_a.py::test_x"
    assert audit.test_of("tests/test_a.py::test_x|run") == "tests/test_a.py::test_x"
    assert audit.test_of("tests/test_a.py::test_x|teardown") == "tests/test_a.py::test_x"
    assert audit.test_of("tests/test_a.py::test_x") == "tests/test_a.py::test_x"
    assert audit.test_of("") is None


def test_with_functions_a_parametrized_case_is_its_function():
    assert audit.test_of("t.py::test_x[a-1]|run", functions=True) == "t.py::test_x"
    assert audit.test_of("t.py::test_x[a-1]|run") == "t.py::test_x[a-1]"
    assert audit.test_of("t.py::test_x|run", functions=True) == "t.py::test_x"


PRINTS = {
    "t.py::a": {("m.py", 1), ("m.py", 2)},
    "t.py::b": {("m.py", 1), ("m.py", 2)},
    "t.py::c": {("m.py", 1), ("m.py", 3)},
    "u.py::d": {("m.py", 4)},
    "u.py::e": set(),
}


def test_unique_lines_are_those_no_other_test_runs():
    assert audit.unique_counts(PRINTS) == {
        "t.py::a": 0,
        "t.py::b": 0,
        "t.py::c": 1,
        "u.py::d": 1,
        "u.py::e": 0,
    }


def test_identical_footprints_are_grouped_and_empty_ones_are_not():
    assert audit.identical_groups(PRINTS) == [["t.py::a", "t.py::b"]]


def test_the_greedy_cover_runs_every_line_with_fewer_tests():
    cover = audit.greedy_cover(PRINTS)
    assert set().union(*(PRINTS[t] for t in cover)) == set().union(*PRINTS.values())
    assert len(cover) == 3


def test_the_report_counts_by_file():
    result = audit.report(PRINTS, top=5)
    assert (result["tests"], result["items"], result["cover"]) == (5, 4, 3)
    assert result["no_unique"] == ["t.py::a", "t.py::b", "u.py::e"]
    assert result["no_unique_by_file"] == [["t.py", 2, 3], ["u.py", 1, 2]]


def measured(tmp_path: Path, monkeypatch, branch: bool) -> Path:
    """A .coverage file of three tests' contexts, as pytest-cov names them. The ctrace
    core: sysmon, the default from Python 3.14 on, records no dynamic contexts."""
    monkeypatch.setenv("COVERAGE_CORE", "ctrace")
    module = tmp_path / "m.py"
    module.write_text("def f(x):\n    if x:\n        return 1\n    return 2\n")
    sys.path.insert(0, str(tmp_path))
    try:
        cov = coverage.Coverage(
            data_file=str(tmp_path / ".coverage"), include=[str(module)], branch=branch
        )
        cov.start()
        import m

        cov.switch_context("t.py::yes|run")
        m.f(True)
        cov.switch_context("t.py::no|run")
        m.f(False)
        cov.switch_context("t.py::no_again|run")
        m.f(False)
        cov.stop()
        cov.save()
    finally:
        sys.path.remove(str(tmp_path))
        sys.modules.pop("m", None)
    return tmp_path / ".coverage"


@pytest.mark.parametrize(("branch", "kind"), [(True, "branches"), (False, "lines")])
def test_the_script_reads_a_coverage_file_and_writes_its_json(tmp_path, monkeypatch, branch, kind):
    """`no` and `no_again` take the same branch: identical, and neither unique."""
    data = measured(tmp_path, monkeypatch, branch)
    out = tmp_path / "audit.json"
    run = subprocess.run(
        [sys.executable, str(SCRIPT), str(data), "--json", str(out)],
        capture_output=True,
        text=True,
    )
    assert run.returncode == 0, run.stderr
    assert f"tests: 3, {kind} run:" in run.stdout
    result = json.loads(out.read_text())
    assert result["kind"] == kind
    assert result["identical_groups"] == [["t.py::no", "t.py::no_again"]]
    assert result["no_unique"] == ["t.py::no", "t.py::no_again"]


def test_a_file_without_contexts_is_refused(tmp_path):
    cov = coverage.Coverage(data_file=str(tmp_path / ".coverage"))
    cov.start()
    cov.stop()
    cov.save()
    run = subprocess.run(
        [sys.executable, str(SCRIPT), str(tmp_path / ".coverage")],
        capture_output=True,
        text=True,
    )
    assert run.returncode == 2
    assert "no per-test contexts" in run.stderr
