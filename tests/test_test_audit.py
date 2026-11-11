"""scripts/test_audit.py: the test audit's logic (openspec capability test-audit); its runs of
pytest across processes are tests/integration/test_test_audit_*.py."""

import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts" / "test_audit.py"

spec = importlib.util.spec_from_file_location("test_audit", SCRIPT)
test_audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(test_audit)


def test_load_coverage_gives_each_test_s_lines_per_file_as_sets(tmp_path):
    path = tmp_path / "coverage-unit.json"
    path.write_text(json.dumps({"t.py::a": {"src/lado/runs.py": [3, 1, 2]}, "t.py::b": {}}))
    assert test_audit.load_coverage(path) == {
        "t.py::a": {"src/lado/runs.py": {1, 2, 3}},
        "t.py::b": {},
    }


# --- durations and flakiness ------------------------------------------------------------

PYTEST_OUTPUT = """\
........                                                                 [100%]
============================= slowest durations ==============================
20.15s call     tests/test_providers.py::test_slow
1.20s setup    tests/test_doctor.py::test_probe[a b]
0.30s call     tests/test_doctor.py::test_probe[a b]
0.40s call     tests/test_text.py::test_fast
0.00s teardown tests/test_text.py::test_fast
================== 6155 passed, 7 skipped in 62.75s (0:01:02) ==================
"""


def test_durations_lists_tests_of_a_second_or_more():
    result = test_audit.parse_durations(PYTEST_OUTPUT)
    assert result["wall"] == 62.75
    assert result["tests"] == {
        "tests/test_providers.py::test_slow": 20.15,
        "tests/test_doctor.py::test_probe[a b]": 1.5,  # setup, call and teardown
        "tests/test_text.py::test_fast": 0.4,
    }
    assert test_audit.slow(result) == [
        ("tests/test_providers.py::test_slow", 20.15),
        ("tests/test_doctor.py::test_probe[a b]", 1.5),
    ]


def test_durations_reads_the_summary_of_a_quiet_run():
    text = "0.40s call     tests/test_text.py::test_fast\n471 passed, 1 skipped in 21.55s\n"
    assert test_audit.parse_durations(text)["wall"] == 21.55


def test_durations_without_a_summary_line_is_refused():
    with pytest.raises(ValueError, match="no pytest summary"):
        test_audit.parse_durations("collected 0 items\n")


def job(name, conclusion, start="2026-11-10T10:00:00Z", end="2026-11-10T10:02:00Z"):
    return {"name": name, "conclusion": conclusion, "startedAt": start, "completedAt": end}


@pytest.fixture
def fake_gh(tmp_path, monkeypatch):
    """A `gh` on PATH that answers `run list` and `run view <id> --attempt <n> --json jobs`
    from the file it returns: {"runs": [...], "jobs": {"<id>/<attempt>": [...]}}."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    data = tmp_path / "gh.json"
    gh = bin_dir / "gh"
    gh.write_text(
        f"""#!{sys.executable}
import json, sys
answers = json.load(open({str(data)!r}))
args = sys.argv[1:]
if args[:2] == ["run", "list"]:
    print(json.dumps(answers["runs"]))
elif args[:2] == ["run", "view"]:
    key = args[2] + "/" + args[args.index("--attempt") + 1]
    print(json.dumps({{"jobs": answers["jobs"][key]}}))
else:
    sys.exit(1)
"""
    )
    gh.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    return data


def test_flaky_reads_reruns_from_gh(fake_gh, tmp_path):
    runs = [
        {"databaseId": 2, "attempt": 2, "createdAt": "2026-11-10T10:00:00Z",
         "updatedAt": "2026-11-10T10:20:00Z", "conclusion": "success"},
        {"databaseId": 1, "attempt": 1, "createdAt": "2026-11-09T10:00:00Z",
         "updatedAt": "2026-11-09T10:08:00Z", "conclusion": "success"},
    ]  # fmt: skip
    jobs = {
        "2/1": [job("unit (3.10)", "success"), job("ui (1)", "failure")],
        "2/2": [job("unit (3.10)", "success"), job("ui (1)", "success")],
        "1/1": [job("unit (3.10)", "success", "2026-11-09T10:00:00Z", "2026-11-09T10:03:30Z")],
    }
    fake_gh.write_text(json.dumps({"runs": runs, "jobs": jobs}))

    assert test_audit.run_flaky(tmp_path / "out", days=30, recent=10) == 0

    result = json.loads((tmp_path / "out" / "flaky.json").read_text())
    assert result["reruns"] == [{"run": 2, "job": "ui (1)", "attempt": 2}]
    assert result["runs"][1] == {
        "id": 1,
        "clock_s": 480,
        "runner_min": 3.5,
        "jobs": {"unit (3.10)": 210},
    }
    assert result["runs"][0]["runner_min"] == 4.0  # the last attempt's jobs


def test_a_run_gh_cannot_show_is_named_and_fails_the_command(fake_gh, tmp_path, capsys):
    runs = [{"databaseId": 3, "attempt": 1, "createdAt": "2026-11-10T10:00:00Z",
             "updatedAt": "2026-11-10T10:20:00Z", "conclusion": "success"}]  # fmt: skip
    fake_gh.write_text(json.dumps({"runs": runs, "jobs": {}}))  # `run view 3` fails

    assert test_audit.run_flaky(tmp_path / "out", days=30, recent=10) == 1

    assert "gh run view 3 --attempt 1 failed" in capsys.readouterr().out
    result = json.loads((tmp_path / "out" / "flaky.json").read_text())
    assert result["unread"] == ["3/1"]
    assert result["runs"] == []


def test_flaky_without_gh_says_so_and_skips(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("PATH", str(tmp_path))  # no gh

    assert test_audit.run_flaky(tmp_path / "out", days=30, recent=10) == 0

    assert "flaky: gh is not available" in capsys.readouterr().out
    result = json.loads((tmp_path / "out" / "flaky.json").read_text())
    assert result["skipped"].startswith("gh is not available")


# --- subsets ----------------------------------------------------------------------------


def test_a_test_inside_another_is_a_candidate():
    cov = {
        "t.py::a": {"src/lado/runs.py": set(range(10, 21))},
        "t.py::b": {"src/lado/runs.py": set(range(1, 41))},
    }
    assert test_audit.subset_candidates(cov) == [("t.py::a", "t.py::b")]


def test_lines_of_another_file_keep_a_test_out_of_the_candidates():
    cov = {
        "t.py::a": {"src/lado/runs.py": {10}, "src/lado/flows.py": {3}},
        "t.py::b": {"src/lado/runs.py": set(range(1, 41))},
    }
    assert test_audit.subset_candidates(cov) == []


def test_cases_of_one_function_are_not_compared():
    lines = {"src/lado/runs.py": {1, 2}}
    cov = {"t.py::f[x]": lines, "t.py::f[y]": dict(lines), "u.py::C::f[x]": {}}
    assert test_audit.subset_candidates(cov) == []


def test_equal_sets_are_listed_once():
    lines = {"src/lado/runs.py": {1, 2}}
    assert test_audit.subset_candidates({"t.py::a": lines, "t.py::b": dict(lines)}) == [
        ("t.py::b", "t.py::a")
    ]


def test_the_closest_covering_test_is_named():
    cov = {
        "t.py::a": {"src/lado/runs.py": {1}},
        "t.py::big": {"src/lado/runs.py": set(range(1, 100))},
        "t.py::small": {"src/lado/runs.py": {1, 2}},
    }
    assert ("t.py::a", "t.py::small") in test_audit.subset_candidates(cov)


def test_a_test_that_runs_none_of_our_code_is_listed_apart():
    cov = {"t.py::a": {}, "t.py::b": {"src/lado/runs.py": {1}}}
    assert test_audit.subset_candidates(cov) == []
    assert test_audit.no_code(cov) == ["t.py::a"]


# --- pseudo-tested functions ------------------------------------------------------------

SOURCE = '''\
"""A module."""

import os


def plain(x):
    """Doc."""
    y = x + 1
    return y  # the end


class Box:
    @property
    def size(self):
        return 3

    def items(self):
        yield from range(3)

    async def wait(self):
        await os.sleep(1)


def one_line(x): return x * 2
'''


@pytest.mark.parametrize(
    "qualname, replaced, kept",
    [
        ("plain", "def plain(x):\n    return None  # the end\n", "class Box:"),
        ("Box.size", "    def size(self):\n        return None\n", 'def plain(x):\n    """Doc'),
        ("Box.items", "    def items(self):\n        return\n        yield\n", "        await os"),
        ("Box.wait", "    async def wait(self):\n        return None\n", "def one_line"),
        ("one_line", "def one_line(x): return None\n", "class Box:"),
    ],
)
def test_body_replacement_empties_one_function_and_keeps_the_rest(qualname, replaced, kept):
    result = test_audit.empty_body(SOURCE, qualname)
    assert replaced in result
    assert kept in result
    compile(result, "m.py", "exec")
    # Every line outside the function's body is byte for byte the source's.
    start, end = test_audit.body_span(SOURCE, qualname)
    old, new = SOURCE.splitlines(), result.splitlines()
    assert old[: start - 1] == new[: start - 1]
    assert old[end:] == new[len(new) - (len(old) - end) :]


def test_body_replacement_of_a_generator_stays_a_generator():
    namespace = {}
    exec(test_audit.empty_body(SOURCE.replace("import os\n", ""), "Box.items"), namespace)
    assert list(namespace["Box"]().items()) == []


def test_the_functions_of_a_module_with_their_body_lines():
    functions = test_audit.functions(SOURCE)
    assert [f.qualname for f in functions] == [
        "plain",
        "Box.size",
        "Box.items",
        "Box.wait",
        "one_line",
    ]
    assert functions[0].lines == range(7, 10)  # the docstring's line to `return y`
    assert functions[-1].lines == range(24, 25)


def test_a_function_whose_body_is_already_empty_is_not_mutated():
    source = (
        "def a():\n    pass\n\n\ndef b():\n    return None\n\n\ndef c():\n    '''Doc.'''\n    ...\n"
    )
    assert test_audit.functions(source) == []
