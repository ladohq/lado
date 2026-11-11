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
