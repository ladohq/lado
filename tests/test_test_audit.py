"""scripts/test_audit.py: the test audit's logic (openspec capability test-audit); its runs of
pytest across processes are tests/integration/test_test_audit_*.py."""

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts" / "test_audit.py"

spec = importlib.util.spec_from_file_location("test_audit", SCRIPT)
test_audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(test_audit)


def test_a_test_s_record_is_its_body_s_lines_and_its_processes(tmp_path):
    """pytest's process: the lines of the test's call only, not of its fixtures' setup and
    teardown (tests/conftest.py's autouse fixtures run LADO's code for every test); a child
    process: all its lines, under the test that started it, none outside a test."""
    import coverage

    runs = str(ROOT / "src" / "lado" / "runs.py")
    (tmp_path / "main").mkdir()
    (tmp_path / "child").mkdir()
    main = coverage.CoverageData(basename=str(tmp_path / "main" / ".coverage"))
    contexts = [("t.py::a|setup", [1]), ("t.py::a|run", [2]), ("t.py::a|teardown", [3])]
    for context, lines in [*contexts, ("t.py::doc|setup", [1])]:
        main.set_context(context)
        main.add_lines({runs: lines})
    main.write()
    child = coverage.CoverageData(basename=str(tmp_path / "child" / ".coverage"), suffix="x.1")
    for context, lines in [("t.py::a", [4]), ("", [5])]:
        child.set_context(context)
        child.add_lines({runs: lines})
    child.write()

    assert test_audit.export_coverage(tmp_path) == {
        "t.py::a": {"src/lado/runs.py": [2, 4]},
        "t.py::doc": {},  # its call ran none of our lines (a test of a document)
    }


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


def ci_run(id_, attempt, created, updated):
    """A run as `gh run list --json` gives it, green."""
    times = {"createdAt": created, "updatedAt": updated}
    return {"databaseId": id_, "attempt": attempt, **times, "conclusion": "success"}


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
        ci_run(2, 2, "2026-11-10T10:00:00Z", "2026-11-10T10:20:00Z"),
        ci_run(1, 1, "2026-11-09T10:00:00Z", "2026-11-09T10:08:00Z"),
    ]
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
    runs = [ci_run(3, 1, "2026-11-10T10:00:00Z", "2026-11-10T10:20:00Z")]
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


@pytest.mark.parametrize(
    "output, failed",
    [
        ("bringing up nodes...\n\n....s...", False),
        ("bringing up nodes...\n\n..F.", True),
        ("....E", True),  # an error in a fixture, or a module that no longer imports
        ("....\nERROR collecting tests/test_x.py\n", False),  # exit 2 says it at the end
        ("........ [ 52%]\n...", False),
    ],
)
def test_a_failure_is_seen_in_pytest_s_progress(output, failed):
    """xdist's -x stops only after the tests its workers run end, which may wait for long on
    an emptied function: pseudo ends the run at the progress line's first F or E."""
    assert test_audit.failed_already(output) is failed


# --- the mutation baseline and the proof ------------------------------------------------


def test_mutmut_s_results_are_read_by_mutant():
    text = (
        "    lado.text.x_hidden__mutmut_1: killed\n"
        "    lado.text.x_named__mutmut_5: survived\n"
        "    lado.text.x_refusal__mutmut_1: no tests\n"
    )
    assert test_audit.parse_results(text) == {
        "lado.text.x_hidden__mutmut_1": "killed",
        "lado.text.x_named__mutmut_5": "survived",
        "lado.text.x_refusal__mutmut_1": "no tests",
    }


def test_the_score_counts_a_timeout_killed_and_a_mutant_without_tests_survived():
    mutants = {"a": "killed", "b": "timeout", "c": "no tests", "d": "survived"}
    result = {"module": "runs", "mutants": mutants}
    assert test_audit.score(result) == 0.5


def test_prove_passes_when_every_killed_mutant_stays_killed():
    before = {"module": "runs", "mutants": {"m1": "killed", "m2": "survived"}}
    after = {"module": "runs", "mutants": {"m1": "timeout", "m2": "survived"}}
    assert test_audit.prove(before, after) == []


def test_prove_names_a_lost_mutant():
    before = {"module": "runs", "mutants": {"m1": "killed"}}
    after = {"module": "runs", "mutants": {"m1": "survived"}}
    assert test_audit.prove(before, after) == ["runs: m1 killed before, survived after"]


def test_prove_names_a_mutant_missing_after():
    before = {"module": "runs", "mutants": {"m1": "killed", "m2": "killed"}}
    after = {"module": "runs", "mutants": {"m1": "killed"}}
    assert test_audit.prove(before, after) == ["runs: m2 killed before, missing after"]


def test_prove_refuses_other_modules():
    with pytest.raises(ValueError, match="runs.*flows"):
        test_audit.prove({"module": "runs", "mutants": {}}, {"module": "flows", "mutants": {}})


def write_mutation(folder: Path, module: str, mutants: dict, tests: dict | None = None) -> None:
    folder.mkdir(exist_ok=True)
    data = {"module": module, "seconds": 1, "mutants": mutants, "tests": tests or {}}
    (folder / f"mutation-{module}.json").write_text(json.dumps(data))


def test_the_prove_command_fails_on_a_module_measured_on_one_side_only(tmp_path, capsys):
    write_mutation(tmp_path / "before", "runs", {"m1": "killed"})
    write_mutation(tmp_path / "before", "flows", {"f1": "killed"})
    write_mutation(tmp_path / "after", "runs", {"m1": "killed"})

    assert test_audit.run_prove(tmp_path / "before", tmp_path / "after") == 1
    assert "flows: measured before only" in capsys.readouterr().out


def test_the_prove_command_prints_each_module_s_scores(tmp_path, capsys):
    write_mutation(tmp_path / "before", "runs", {"m1": "killed", "m2": "survived"})
    write_mutation(tmp_path / "after", "runs", {"m1": "killed", "m2": "killed"})

    assert test_audit.run_prove(tmp_path / "before", tmp_path / "after") == 0
    assert "runs: 50.0% before, 100.0% after" in capsys.readouterr().out


def test_the_prove_command_names_the_deleted_test_that_ran_a_lost_mutant(tmp_path, capsys):
    tests = {"lado.runs.x_go": ["tests/test_runs.py::test_go", "tests/test_runs.py::test_kept"]}
    write_mutation(tmp_path / "before", "runs", {"lado.runs.x_go__mutmut_1": "killed"}, tests)
    write_mutation(tmp_path / "after", "runs", {"lado.runs.x_go__mutmut_1": "survived"})
    deleted = tmp_path / "deleted.txt"
    deleted.write_text("tests/test_runs.py::test_go\n")
    coverage = tmp_path / "coverage-unit.json"
    coverage.write_text(json.dumps({"tests/test_runs.py::test_go": {"src/lado/runs.py": [4]}}))

    code = test_audit.run_prove(
        tmp_path / "before", tmp_path / "after", deleted=deleted, coverage=[coverage]
    )

    assert code == 1
    out = capsys.readouterr().out
    assert "runs: lado.runs.x_go__mutmut_1 killed before, survived after" in out
    assert "deleted tests that ran it: tests/test_runs.py::test_go\n" in out


def test_a_deleted_test_of_no_module_rests_on_the_checklist(tmp_path, capsys):
    write_mutation(tmp_path / "before", "runs", {"m1": "killed"})
    write_mutation(tmp_path / "after", "runs", {"m1": "killed"})
    deleted = tmp_path / "deleted.txt"
    deleted.write_text("tests/test_readme.py::test_headings\ntests/test_runs.py::test_go\n")
    coverage = tmp_path / "coverage-unit.json"
    records = {
        "tests/test_readme.py::test_headings": {},
        "tests/test_runs.py::test_go": {"src/lado/runs.py": [4]},
    }
    coverage.write_text(json.dumps(records))

    code = test_audit.run_prove(
        tmp_path / "before", tmp_path / "after", deleted=deleted, coverage=[coverage]
    )

    assert code == 0
    out = capsys.readouterr().out
    assert "rests on the checklist: tests/test_readme.py::test_headings" in out


def test_a_module_a_deleted_test_ran_must_be_measured(tmp_path, capsys):
    write_mutation(tmp_path / "before", "runs", {"m1": "killed"})
    write_mutation(tmp_path / "after", "runs", {"m1": "killed"})
    deleted = tmp_path / "deleted.txt"
    deleted.write_text("tests/test_flows.py::test_load\n")
    coverage = tmp_path / "coverage-unit.json"
    coverage.write_text(json.dumps({"tests/test_flows.py::test_load": {"src/lado/flows.py": [1]}}))

    code = test_audit.run_prove(
        tmp_path / "before", tmp_path / "after", deleted=deleted, coverage=[coverage]
    )

    assert code == 1
    assert "flows: a deleted test ran it, but it was not measured" in capsys.readouterr().out


def test_a_deleted_test_without_a_coverage_record_fails_the_proof(tmp_path, capsys):
    write_mutation(tmp_path / "before", "runs", {"m1": "killed"})
    write_mutation(tmp_path / "after", "runs", {"m1": "killed"})
    deleted = tmp_path / "deleted.txt"
    deleted.write_text("tests/test_new.py::test_x\n")
    coverage = tmp_path / "coverage-unit.json"
    coverage.write_text("{}")

    code = test_audit.run_prove(
        tmp_path / "before", tmp_path / "after", deleted=deleted, coverage=[coverage]
    )

    assert code == 1
    assert "no coverage record: tests/test_new.py::test_x" in capsys.readouterr().out


def test_one_mutmut_run_s_mutants_are_split_by_module():
    names = [
        "lado.runs.x_go__mutmut_1",
        "lado.runs.xǁRunǁstep__mutmut_2",
        "lado.providers.x_get__mutmut_1",
        "lado.providers.claude.x_parse__mutmut_1",
    ]
    assert test_audit.of_module(names, "runs") == names[:2]
    assert test_audit.of_module(names, "providers") == [names[2]]
    assert test_audit.of_module(names, "providers.claude") == [names[3]]


def test_mutmut_mutates_only_the_modules_named(tmp_path):
    repo = tmp_path / "repo"
    (repo / "docs").mkdir(parents=True)
    (repo / "docs" / "a.md").write_text("a")
    (repo / "Makefile").write_text("")
    test_audit.git(repo, "init", "-q")
    test_audit.git(repo, "add", ".")
    config = test_audit.mutmut_config(repo, ["runs", "providers.claude"])
    assert 'only_mutate = ["src/lado/runs.py", "src/lado/providers/claude.py"]' in config
    assert 'also_copy = ["Makefile", "docs"]' in config


def test_the_module_of_a_path():
    assert test_audit.module_of("src/lado/runs.py") == "runs"
    assert test_audit.module_of("src/lado/providers/claude.py") == "providers.claude"
    assert test_audit.module_of("scripts/ci_ok.py") is None


# --- the report and make ----------------------------------------------------------------


def test_the_report_joins_what_was_measured(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    durations = {"wall": 62.75, "tests": {"t.py::slow": 20.15, "t.py::fast": 0.01}}
    (out / "durations-unit.json").write_text(json.dumps(durations))
    mutants = {"lado.runs.x_go__mutmut_1": "killed", "lado.runs.x_go__mutmut_2": "survived"}
    write_mutation(out, "runs", mutants)
    pseudo = {"pseudo": {"runs.go": ["t.py::a"]}, "not_covered": ["runs.stop"]}
    pseudo |= {"killed": [], "timeout": [], "errors": {}}
    (out / "pseudo.json").write_text(json.dumps(pseudo))

    assert test_audit.run_report(out) == 0

    report = (out / "report.md").read_text()
    assert "| unit | 2 | 62.75 s |" in report
    assert "| t.py::slow | 20.15 s |" in report
    assert "| runs | 2 | 50.0% |" in report
    assert "runs.go: t.py::a" in report
    assert "runs.stop" in report


def test_the_report_marks_a_part_not_measured(tmp_path):
    out = tmp_path / "out"
    out.mkdir()

    assert test_audit.run_report(out) == 0

    report = (out / "report.md").read_text()
    assert "not measured: `python scripts/test_audit.py durations --layer integration`" in report
    assert "not measured: `python scripts/test_audit.py flaky`" in report
    assert "not measured: `python scripts/test_audit.py mutation <module>...`" in report
    assert "not measured: `python scripts/test_audit.py pseudo`" in report
    assert "not measured: `python scripts/test_audit.py subsets`" in report


def make_dry_run(target: str) -> str:
    """`make -n <target>`: its commands, not run, without the OUT of a make that runs these
    tests (make test-audit OUT=...)."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("MAKE")}
    result = subprocess.run(
        ["make", "-n", "--no-print-directory", target, "OUT="],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout


def test_make_check_runs_no_audit():
    assert "test_audit" not in make_dry_run("_check")


def test_make_test_audit_measures_every_part_and_writes_the_report():
    commands = make_dry_run("_test-audit")
    for part in [
        "coverage --layer unit",
        "coverage --layer integration",
        "coverage --layer ui",
        "durations --layer unit",
        "durations --layer integration",
        "durations --layer ui",
        "flaky",
        "subsets",
        "pseudo",
        "report",
    ]:
        assert f"scripts/test_audit.py {part}" in commands
    assert commands.rstrip().splitlines()[-1].endswith("scripts/test_audit.py report")
