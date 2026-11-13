"""scripts/mutants.py: the test audit's kill matrix and the tests it shows can go."""

import ast
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts" / "mutants.py"

spec = importlib.util.spec_from_file_location("mutants", SCRIPT)
mutants = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mutants)

SOURCE = '''"""The module's docstring."""
LIMIT = 3


def f(x, y=1):
    """f's docstring."""
    if x > LIMIT and y:
        return f"big {x}"
    print("small")
    return "small"
'''


def mutated(source: str) -> dict[tuple, str]:
    tree = ast.parse(source)
    mutants.mark(tree)
    out = {}
    for kind, line, i, detail, apply in mutants.sites(tree):
        copy = ast.parse(source)
        apply(list(ast.walk(copy))[i])
        out[kind, line, detail] = ast.unparse(copy)
    return out


def test_each_kind_of_mutant_changes_its_node_and_no_docstring_or_f_string_part():
    found = mutated(SOURCE)
    assert set(found) == {
        ("number", 2, "3"),
        ("number", 5, "1"),
        ("negate", 7, "If"),
        ("boolop", 7, "And"),
        ("compare", 7, "Gt->LtE"),
        ("return", 8, "->None"),
        ("delete", 9, "Expr"),
        ("string", 9, "'small'"),
        ("string", 10, "'small'"),
        ("return", 10, "->None"),
    }
    assert "LIMIT = 4" in found["number", 2, "3"]
    assert "if not (x > LIMIT and y)" in found["negate", 7, "If"]
    assert "x > LIMIT or y" in found["boolop", 7, "And"]
    assert "x <= LIMIT" in found["compare", 7, "Gt->LtE"]
    assert "print" not in found["delete", 9, "Expr"]
    assert "return 'XXsmallXX'" in found["string", 10, "'small'"]


def test_a_raise_is_deleted_and_a_bool_inverted():
    found = mutated("def g(ok=True):\n    raise ValueError(ok)\n")
    assert "raise" not in found["delete", 2, "Raise"]
    assert "ok=False" in found["bool", 1, "True"]


def test_a_mutant_runs_the_tests_of_its_line_of_its_function_or_of_the_module():
    tree = ast.parse(SOURCE)
    mutants.mark(tree)
    by_line = {7: {"t::a", "t::b"}, 9: {"t::b"}, 10: {"t::b"}}
    tests = mutants.chooser(by_line, also={"t::reads_limit"})
    nodes = {(kind, line): list(ast.walk(tree))[i] for kind, line, i, _, _ in mutants.sites(tree)}
    assert tests(nodes["delete", 9], 9) == {"t::b"}
    assert tests(nodes["number", 5], 5) == {"t::a", "t::b"}  # a default: f's body
    assert tests(nodes["number", 2], 2) == {"t::a", "t::b", "t::reads_limit"}  # import time


def row(line, status, *killed_by, nth=1):
    return {"line": line, "kind": "k", "detail": "d", "nth": nth, "status": status,
            "killed_by": list(killed_by)}  # fmt: skip


def test_runs_of_the_same_mutant_join_their_killers():
    first = [row(1, "survived"), row(2, "killed", "t::a"), row(3, "error")]
    later = [row(1, "killed", "t::b"), row(2, "killed", "t::c"), row(3, "survived")]
    assert mutants.merged([first, later]) == [
        row(1, "killed", "t::b"),
        row(2, "killed", "t::a", "t::c"),
        row(3, "survived"),
    ]


def test_a_test_goes_only_when_its_mutants_and_its_branches_have_another_test():
    rows = [
        row(1, "killed", "t.py::weak", "t.py::strong"),
        row(2, "killed", "t.py::strong", "t.py::twin[x]"),
        row(3, "killed", "t.py::alone", "u.py::other"),
        row(4, "killed", "t.py::only"),
    ]
    prints = {
        "t.py::weak": {("m", 1, 2)},
        "t.py::strong": {("m", 1, 2), ("m", 2, 3)},
        "t.py::twin": {("m", 2, 3)},
        "t.py::alone": {("m", 9, 10)},  # the one test of this branch
        "t.py::only": {("m", 1, 2)},  # the one killer of mutant 4
        "u.py::other": {("m", 5, 6)},
    }
    gone, kills = mutants.removable(rows, prints, "t.py")
    # weak (1 kill) goes first; twin, the copy of strong, then goes too; strong stays as
    # the last killer of mutant 2.
    assert gone == ["t.py::twin", "t.py::weak"]
    assert kills["t.py::twin"] == {1}


def test_run_and_removable_on_a_small_repository(tmp_path):
    repo = tmp_path.resolve()
    (repo / "src" / "pkg").mkdir(parents=True)
    (repo / "src" / "pkg" / "__init__.py").write_text("")
    (repo / "src" / "pkg" / "m.py").write_text(
        'def size(x):\n    if x > 3:\n        return "big"\n    return "small"\n'
    )
    (repo / "tests").mkdir()
    (repo / "tests" / "test_m.py").write_text(
        "from pkg.m import size\n\n"
        "def test_four():\n    assert size(4) == 'big'\n\n"
        "def test_four_again():\n    assert size(4) == 'big'\n\n"
        "def test_three():\n    assert size(3) == 'small'\n"
    )
    env = {**os.environ, "PYTHONPATH": str(repo / "src"), "COVERAGE_CORE": "ctrace"}
    measure = [sys.executable, "-m", "pytest", "-q", "-n0", "-p", "no:randomly",
               "-o", "addopts=", "--cov=pkg", "--cov-branch", "--cov-context=test",
               "--cov-report=", "tests"]  # fmt: skip
    subprocess.run(measure, cwd=repo, env=env, check=True, capture_output=True)
    kills = repo / "kills.json"
    script = [sys.executable, str(SCRIPT)]
    go = subprocess.run(
        [*script, "run", "src/pkg/m.py", ".coverage", str(kills), "--jobs", "2"],
        cwd=repo, env=env, capture_output=True, text=True,
    )  # fmt: skip
    assert go.returncode == 0, go.stderr
    rows = {(r["kind"], r["detail"]): r for r in json.loads(kills.read_text())}
    assert rows["compare", "Gt->LtE"]["killed_by"] == [
        "tests/test_m.py::test_four",
        "tests/test_m.py::test_four_again",
        "tests/test_m.py::test_three",
    ]
    assert rows["string", "'small'"]["killed_by"] == ["tests/test_m.py::test_three"]
    out = repo / "cand.json"
    found = subprocess.run(
        [*script, "removable", "tests/test_m.py", ".coverage", str(kills), "--json", str(out)],
        cwd=repo, env=env, capture_output=True, text=True,
    )  # fmt: skip
    assert found.returncode == 0, found.stderr
    # test_three has a branch of its own; of the two copies one goes, and the other stays as
    # the last killer of its mutants.
    assert json.loads(out.read_text())["removable"] == ["tests/test_m.py::test_four"]


def test_a_run_that_never_imports_the_mutant_is_an_error_not_a_survivor(tmp_path):
    """Tests that pass on code they never loaded say nothing of the mutant."""
    repo = tmp_path.resolve()
    work = repo / "work"
    (work / "src" / "pkg").mkdir(parents=True)
    (work / "src" / "pkg" / "__init__.py").write_text("")
    (repo / "tests").mkdir()
    (repo / "tests" / "test_other.py").write_text("def test_nothing_of_pkg():\n    pass\n")
    result = mutants.run_one(
        work, repo, Path("pkg/m.py"), "X = 1\n", ["tests/test_other.py"], timeout=60
    )
    assert (result["status"], result["why"]) == ("error", "mutant not imported")
