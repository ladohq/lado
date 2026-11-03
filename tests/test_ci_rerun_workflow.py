""".github/workflows/ci-rerun.yml: a CI run that failed on its first attempt is handed to
scripts/ci_rerun.py, which reruns its failed jobs once when they only got no runner; the
workflow runs main's files, never a pull request's code, with the least permissions."""

from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "ci-rerun.yml"


@pytest.fixture(scope="module")
def text() -> str:
    return WORKFLOW.read_text()


@pytest.fixture(scope="module")
def workflow(text) -> dict:
    return yaml.safe_load(text)


@pytest.fixture(scope="module")
def job(workflow) -> dict:
    (only,) = workflow["jobs"].values()
    return only


def test_it_starts_when_a_ci_run_completes(workflow):
    ci = yaml.safe_load((ROOT / ".github" / "workflows" / "ci.yml").read_text())
    # PyYAML reads the key `on` as True.
    assert workflow[True] == {"workflow_run": {"workflows": [ci["name"]], "types": ["completed"]}}


def test_it_looks_only_at_a_first_attempt_that_failed(job):
    """A superseded run ends cancelled, and the rerun is attempt 2: no loop."""
    assert job["if"] == (
        "github.event.workflow_run.conclusion == 'failure' && "
        "github.event.workflow_run.run_attempt == 1"
    )


def test_it_holds_only_the_permissions_it_needs(workflow, job):
    assert "permissions" not in workflow or workflow["permissions"] == {}
    assert job["permissions"] == {"actions": "write", "checks": "read", "contents": "read"}


def test_it_runs_the_script_with_rerun_on_the_completed_run(job):
    (step,) = [s for s in job["steps"] if "run" in s]
    assert step["run"] == 'python3 scripts/ci_rerun.py "$RUN_ID" --rerun'
    assert step["env"] == {
        "RUN_ID": "${{ github.event.workflow_run.id }}",
        "GH_TOKEN": "${{ github.token }}",
        "GH_REPO": "${{ github.repository }}",
    }


def test_it_checks_out_mains_files_only(job):
    """workflow_run checks out the default branch; a ref of the run would be the PR's code."""
    (checkout,) = [s for s in job["steps"] if s.get("uses", "").startswith("actions/checkout@")]
    assert "with" not in checkout


def test_no_code_of_the_pull_request_and_no_secret(text):
    for word in ("head_sha", "head_branch", "head_repository", "pull_requests", "secrets"):
        assert word not in text, word
