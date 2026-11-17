"""scripts/test_counts.py: the tests per layer in CI's summary."""

import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts" / "test_counts.py"


def counts(repo: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "-p", "no:randomly", "tests"],
        cwd=repo, capture_output=True, text=True,
    )  # fmt: skip


def test_each_test_counts_in_the_layer_of_its_marker_and_cases_apart(tmp_path):
    (tmp_path / "pytest.ini").write_text(
        "[pytest]\naddopts = -m 'not ui'\nmarkers =\n    ui: a browser\n    integration: tmux\n"
    )
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_x.py").write_text(
        "import pytest\n\n"
        "def test_a():\n    pass\n\n"
        "@pytest.mark.parametrize('n', [1, 2, 3])\ndef test_b(n):\n    pass\n\n"
        "@pytest.mark.ui\ndef test_c():\n    pass\n\n"
    )
    (tmp_path / "tests" / "test_y.py").write_text(
        "import pytest\n\npytestmark = pytest.mark.integration\n\ndef test_d():\n    pass\n"
    )
    done = counts(tmp_path)
    assert done.returncode == 0, done.stderr
    rows = {line.split("|")[1].strip(): line for line in done.stdout.splitlines() if "|" in line}
    # Not the default run's -m: the ui test counts too. No pytest line besides the table.
    assert rows["unit"] == "| unit | 2 | 4 |"
    assert rows["integration"] == "| integration | 1 | 1 |"
    assert rows["ui"] == "| ui | 1 | 1 |"
    assert rows["**all**"] == "| **all** | **4** | **6** |"
    assert "test_x.py::test_a" not in done.stdout


def test_a_collection_error_fails_and_says_why(tmp_path):
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_x.py").write_text("import no_such_module\n")
    done = counts(tmp_path)
    assert done.returncode != 0
    assert "no_such_module" in done.stderr


def test_ci_writes_it_to_the_summary_of_one_unit_run():
    ci = yaml.safe_load((ROOT / ".github" / "workflows" / "ci.yml").read_text())
    unit = ci["jobs"]["unit"]
    [step] = [s for s in unit["steps"] if "test_counts.py" in s.get("run", "")]
    assert step["run"].endswith('>> "$GITHUB_STEP_SUMMARY"')
    assert (
        step["if"]
        == f"matrix.python-version == '{unit['strategy']['matrix']['python-version'][-1]}'"
    )
