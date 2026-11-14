"""Each UI test's time limit (tests/time_limit.py, given by tests/ui/conftest.py, LAD-271):
every test under tests/ui/ has it and no other layer's does; a test past it fails, its
worker's stacks in the log, and the run goes on with the next test and writes its junit
report. A hang inside Playwright: tests/ui/test_time_limit.py."""

import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import time_limit

pytest_plugins = "pytester"

ROOT = Path(__file__).parents[1]

# Writes each collected test's timeout markers (their arguments) and whether it has the
# fixture of the stacks to $LIMITS_OUT.
DUMP = """
import json
import os


def pytest_collection_finish(session):
    with open(os.environ["LIMITS_OUT"], "w") as out:
        limits = {
            i.nodeid: [
                [[m.args, m.kwargs] for m in i.iter_markers("timeout")],
                "stacks_before_the_limit" in i.fixturenames,
            ]
            for i in session.items
        }
        json.dump(limits, out)
"""
LIMIT = [[[[time_limit.TEST_TIMEOUT], {"method": "thread"}]], True]
NONE = [[], False]


def test_every_ui_test_has_the_limit_and_no_other_layers_test(tmp_path):
    """Every layer's tests collected (no marker deselects any) in a process of its own, with
    their conftests, which this session has already loaded as the unit tests' neighbours."""
    (tmp_path / "limits_dump.py").write_text(DUMP)
    out = tmp_path / "limits.json"
    env = {**os.environ, "PYTHONPATH": str(tmp_path), "LIMITS_OUT": str(out)}
    subprocess.run(
        [sys.executable, "-m", "pytest", "tests", "-o", "addopts=", "--collect-only", "-q"]
        + ["-p", "limits_dump", "-p", "no:cacheprovider"],
        cwd=ROOT,
        env=env,
        check=True,
        capture_output=True,
    )
    limits = json.loads(out.read_text())
    assert time_limit.TEST_TIMEOUT == 120
    ui = {k: v for k, v in limits.items() if k.startswith("tests/ui/")}
    others = {k: v for k, v in limits.items() if not k.startswith("tests/ui/")}
    layers = {k.split("/")[1] for k in others if k.count("/") > 1}
    assert ui and {"integration", "live", "smoke", "container"} <= layers
    assert [k for k in others if k.count("/") == 1]  # the unit tests
    assert {k: v for k, v in ui.items() if v != LIMIT} == {}
    assert {k: v for k, v in others.items() if v != NONE} == {}


def run_past_the_limit(pytester, monkeypatch, hang: str, limit: int, stacks_before: int):
    """A run under -n 2 of `hang`, a test module whose test_hangs waits forever and whose
    test_next passes after it, and of four passing tests, with time_limit's own hook and
    fixture at a short limit. Checks that test_hangs alone fails, named, in well under the
    time of its wait, that the rest pass, and that the junit report names it; returns the
    run's result."""
    monkeypatch.setenv("PYTHONPATH", os.pathsep.join([str(ROOT / "tests"), *sys.path]))
    pytester.makeconftest(
        "import time_limit\n\n"
        f"time_limit.TEST_TIMEOUT = {limit}\ntime_limit.STACKS_BEFORE = {stacks_before}\n\n"
        "from time_limit import pytest_itemcollected, stacks_before_the_limit  # noqa: F401\n"
    )
    pytester.makepyfile(
        test_hang=hang,
        test_after="import pytest\n\n\n@pytest.mark.parametrize('n', range(4))\n"
        "def test_after(n):\n    pass\n",
    )
    junit = pytester.path / "junit.xml"
    # In a process of its own: pytest-playwright refuses a run inside a test. xdist's default
    # scheduling, as in CI: `--dist loadfile` would run the crashed test again on each new
    # worker.
    result = pytester.runpytest_subprocess(
        "-p", "xdist", "-n", "2", f"--junitxml={junit}", timeout=60
    )
    result.assert_outcomes(passed=5, failed=1)
    result.stdout.fnmatch_lines(["*worker 'gw*' crashed while running 'test_hang.py::test_hangs*"])
    assert result.duration < 60
    cases = {c.get("name"): c for c in ET.parse(junit).iter("testcase")}
    (hangs,) = [c for name, c in cases.items() if name.startswith("test_hangs")]
    # xdist reports a crashed worker's test as an error of its setup.
    (error,) = hangs.iter("error")
    assert "crashed while running 'test_hang.py::test_hangs" in error.get("message")
    (after,) = [c for name, c in cases.items() if name.startswith("test_next")]
    assert not list(after.iter("failure"))
    assert len(cases) == 6
    result.stderr.fnmatch_lines([f"Timeout (0:00:0{limit - stacks_before})!"])
    return result


def test_a_test_past_its_limit_fails_with_its_stack_and_the_run_goes_on(pytester, monkeypatch):
    hang = (
        "import time\n\n\ndef test_hangs():\n    time.sleep(60)\n\n\ndef test_next():\n    pass\n"
    )
    result = run_past_the_limit(pytester, monkeypatch, hang, limit=2, stacks_before=1)
    result.stderr.fnmatch_lines(['*File "*test_hang.py", line 5 in test_hangs'])
