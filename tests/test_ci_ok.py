"""scripts/ci_ok.py: the verdict of ci.yml's job `ci-ok`, the one check `main` requires."""

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts" / "ci_ok.py"

spec = importlib.util.spec_from_file_location("ci_ok", SCRIPT)
ci_ok = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ci_ok)


def needs(smoke_needed="true", **results) -> dict:
    """`toJSON(needs)` of a run: every job a success unless named."""
    jobs = {
        name: {"result": results.get(name, "success"), "outputs": {}}
        for name in ("unit", "integration", "ui", "js", "changes", "smoke")
    }
    if smoke_needed is not None:
        jobs["changes"]["outputs"] = {"smoke": smoke_needed}
    return jobs


def test_every_job_succeeded_passes():
    assert ci_ok.problems(needs()) == []


@pytest.mark.parametrize("result", ["failure", "cancelled", "skipped"])
@pytest.mark.parametrize("job", ["unit", "integration", "ui", "js", "changes"])
def test_a_job_that_did_not_succeed_fails_and_is_named(job, result):
    assert ci_ok.problems(needs(**{job: result})) == [f"{job}: {result}"]


def test_the_smoke_skipped_because_changes_said_so_passes():
    assert ci_ok.problems(needs(smoke_needed="false", smoke="skipped")) == []


@pytest.mark.parametrize("smoke_needed", ["true", None, ""])
def test_the_smoke_skipped_while_it_was_needed_fails(smoke_needed):
    assert ci_ok.problems(needs(smoke_needed=smoke_needed, smoke="skipped")) == ["smoke: skipped"]


@pytest.mark.parametrize("result", ["failure", "cancelled"])
def test_the_smoke_not_needed_still_fails_when_it_ran_and_did_not_succeed(result):
    assert ci_ok.problems(needs(smoke_needed="false", smoke=result)) == [f"smoke: {result}"]


def test_no_job_at_all_fails():
    """An empty `needs` is a broken ci.yml, not a green run."""
    assert ci_ok.problems({}) == ["no job to check"]


def run(env_needs: str | None) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if k != "NEEDS"}
    if env_needs is not None:
        env["NEEDS"] = env_needs
    return subprocess.run(
        [sys.executable, str(SCRIPT)], env=env, capture_output=True, text=True, timeout=60
    )


def test_the_script_passes_and_prints_each_job():
    done = run(json.dumps(needs(smoke_needed="false", smoke="skipped")))
    assert done.returncode == 0, done.stderr
    assert "unit: success\n" in done.stdout
    assert "smoke: skipped\n" in done.stdout


def test_the_script_fails_and_names_the_job():
    done = run(json.dumps(needs(integration="failure")))
    assert done.returncode == 1
    assert "ci-ok: integration: failure" in done.stderr


@pytest.mark.parametrize("value", [None, "", "not json", "[]"])
def test_the_script_fails_without_needs(value):
    done = run(value)
    assert done.returncode == 1
    assert "NEEDS" in done.stderr


def test_the_script_imports_only_the_standard_library():
    """ci-ok runs it with the runner's python3, no uv sync."""
    code = (
        "import sys; sys.path.insert(0, 'scripts'); before = set(sys.modules); "
        "import ci_ok; "
        "print('\\n'.join(sorted(m for m in set(sys.modules) - before)))"
    )
    loaded = subprocess.run(
        [sys.executable, "-I", "-c", code], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.split()
    assert [m for m in loaded if m.split(".")[0] not in sys.stdlib_module_names] == ["ci_ok"]
