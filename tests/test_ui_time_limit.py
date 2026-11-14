"""Each UI test's time limit (tests/ui/conftest.py, LAD-271): every test under tests/ui/ has
it and no other layer's does; a test past it fails with the stack of where it waited, and
the run goes on with the next test and writes its junit report.

The conftest's own hook runs here, not a copy: it is taken from the conftest's source with
the limit set short (importing the conftest would bring in the browser tests' fixtures)."""

import ast
import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

pytest_plugins = "pytester"

ROOT = Path(__file__).parents[1]
UI_CONFTEST = ROOT / "tests" / "ui" / "conftest.py"


def _conftest() -> tuple[int, str]:
    """The UI conftest's TEST_TIMEOUT and the source of its hook pytest_itemcollected."""
    text = UI_CONFTEST.read_text()
    tree = ast.parse(text)
    (limit,) = [
        node.value.value
        for node in tree.body
        if isinstance(node, ast.Assign) and [t.id for t in node.targets] == ["TEST_TIMEOUT"]
    ]
    (hook,) = [
        ast.get_source_segment(text, node)
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "pytest_itemcollected"
    ]
    return limit, hook


# Writes each collected test's timeout markers (their arguments) to $LIMITS_OUT.
DUMP = """
import json
import os


def pytest_collection_finish(session):
    with open(os.environ["LIMITS_OUT"], "w") as out:
        limits = {i.nodeid: [m.args for m in i.iter_markers("timeout")] for i in session.items}
        json.dump(limits, out)
"""


def test_every_ui_test_has_the_limit_and_no_other_layers_test(tmp_path):
    """Collected in a process of its own: the real tests/ui/ and tests/integration/ with
    their conftests, which this session has already loaded as the unit tests' neighbours."""
    (tmp_path / "limits_dump.py").write_text(DUMP)
    out = tmp_path / "limits.json"
    env = {**os.environ, "PYTHONPATH": str(tmp_path), "LIMITS_OUT": str(out)}
    args = ["tests/ui", "tests/integration", "tests/test_shard.py", "-m", "ui or integration"]
    subprocess.run(
        [sys.executable, "-m", "pytest", *args, "-o", "addopts=", "--collect-only", "-q"]
        + ["-p", "limits_dump", "-p", "no:cacheprovider"],
        cwd=ROOT,
        env=env,
        check=True,
        capture_output=True,
    )
    limits = json.loads(out.read_text())
    limit, _ = _conftest()
    assert limit == 120
    ui = {k: v for k, v in limits.items() if k.startswith("tests/ui/")}
    others = {k: v for k, v in limits.items() if not k.startswith("tests/ui/")}
    assert ui and others
    assert {k: v for k, v in ui.items() if v != [[limit]]} == {}
    assert {k: v for k, v in others.items() if v} == {}


def test_a_test_past_its_limit_fails_with_its_stack_and_the_run_goes_on(pytester):
    _, hook = _conftest()
    pytester.makeconftest(f"import pytest\n\nTEST_TIMEOUT = 1\n\n\n{hook}\n")
    pytester.makepyfile(
        test_hang="import time\n\n\ndef test_hangs():\n    time.sleep(30)\n\n\n"
        "def test_next():\n    pass\n",
        test_after="import pytest\n\n\n@pytest.mark.parametrize('n', range(4))\n"
        "def test_after(n):\n    pass\n",
    )
    junit = pytester.path / "junit.xml"
    # In a process of its own: pytest-playwright refuses a run inside a test. By file, so
    # test_next runs after test_hangs on the same worker.
    result = pytester.runpytest_subprocess(
        "-p", "xdist", "-n", "2", "--dist", "loadfile", f"--junitxml={junit}"
    )
    result.assert_outcomes(passed=5, failed=1)
    result.stdout.fnmatch_lines(
        ["*time.sleep(30)*", "*Timeout*", "*FAILED test_hang.py::test_hangs*"]
    )
    assert result.duration < 25
    cases = {c.get("name"): c for c in ET.parse(junit).iter("testcase")}
    assert set(cases) == {"test_hangs", "test_next"} | {f"test_after[{n}]" for n in range(4)}
    (failure,) = cases["test_hangs"].iter("failure")
    assert "Timeout" in failure.get("message")
    assert not list(cases["test_next"])
