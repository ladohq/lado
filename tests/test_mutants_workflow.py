"""mutants.yml: mutation testing of one module, by hand (docs/testing.md)."""

import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).parents[1]
WORKFLOW = yaml.safe_load((ROOT / ".github" / "workflows" / "mutants.yml").read_text())
JOB = WORKFLOW["jobs"]["mutants"]
RUNS = [step["run"] for step in JOB["steps"] if "run" in step]


def test_it_runs_only_by_hand_and_only_reads_the_repository():
    # PyYAML reads the key `on` as True.
    assert set(WORKFLOW[True]) == {"workflow_dispatch"}
    assert WORKFLOW["permissions"] == {"contents": "read"}


def test_the_inputs_reach_the_shell_only_through_the_environment():
    """A module's name typed into the form is never pasted into a script."""
    assert set(JOB["env"].values()) == {"${{ inputs.module }}", "${{ inputs.tests }}"}
    assert [run for run in RUNS if "${{" in run] == []


@pytest.mark.parametrize(
    "command", sorted({m for run in RUNS for m in re.findall(r"mutants\.py (\w+)", run)})
)
def test_each_command_it_runs_is_one_of_the_script(command):
    script = [sys.executable, str(ROOT / "scripts" / "mutants.py"), command, "--help"]
    assert subprocess.run(script, capture_output=True).returncode == 0


def test_what_a_timed_out_run_did_is_uploaded():
    [mutants] = [step for step in JOB["steps"] if step.get("name") == "Mutants"]
    upload = JOB["steps"][-1]
    assert upload["uses"].startswith("actions/upload-artifact@")
    assert upload["if"] == "always()"
    assert "*.partial" in upload["with"]["path"]
    assert mutants["timeout-minutes"] < JOB["timeout-minutes"]


FAKE_UV = """#!/bin/sh
echo "$*" >> "$CALLS"
case "$*" in
  *"--collect-only"*) echo "tests/test_m.py::test_a"; echo "1 test collected" ;;
  *"mutants.py run"*) echo "{'killed': 2}"; exit "${FAKE_RUN_EXIT:-0}" ;;
esac
"""


def mutants_step(tmp_path, tests="", **env):
    """The step Mutants run by bash as GitHub runs it (`bash -e`), with a fake uv."""
    [step] = [step for step in JOB["steps"] if step.get("name") == "Mutants"]
    fake = tmp_path / "bin"
    fake.mkdir()
    (fake / "uv").write_text(FAKE_UV)
    (fake / "uv").chmod(0o755)
    (tmp_path / "m").mkdir()
    summary, calls = tmp_path / "summary.md", tmp_path / "calls"
    done = subprocess.run(
        ["bash", "-e", "-c", step["run"]],
        env={"PATH": f"{fake}:/usr/bin:/bin", "RUNNER_TEMP": str(tmp_path), "CALLS": str(calls),
             "GITHUB_STEP_SUMMARY": str(summary), "MODULE": "src/lado/m.py", "TESTS": tests,
             **env},
        capture_output=True, text=True,
    )  # fmt: skip
    return done, calls.read_text().splitlines(), summary.read_text() if summary.exists() else ""


def test_a_test_file_is_judged_with_its_own_node_ids(tmp_path):
    done, calls, summary = mutants_step(tmp_path, tests="tests/test_m.py")
    assert done.returncode == 0, done.stderr
    [run] = [call for call in calls if "mutants.py run" in call]
    ids = tmp_path / "m" / "ids.txt"
    assert run.endswith(f"--judge tests/test_m.py --enough 3 --also {ids}")
    assert ids.read_text() == "tests/test_m.py::test_a\n"
    assert "{'killed': 2}" in summary


def test_without_a_test_file_every_test_judges(tmp_path):
    done, calls, _ = mutants_step(tmp_path)
    assert done.returncode == 0, done.stderr
    assert calls == [
        f"run python scripts/mutants.py run src/lado/m.py {tmp_path}/m/sub/.coverage "
        f"{tmp_path}/m/kills.json --jobs 4"
    ]


def test_a_failed_run_fails_the_step(tmp_path):
    """GitHub's bash runs without pipefail: `run ... | tee` would be green whatever run did."""
    done, _, _ = mutants_step(tmp_path, FAKE_RUN_EXIT="1")
    assert done.returncode != 0
