""".github/workflows/live.yml: the live tests of every provider, weekly and by hand, outside
ci-ok, the key out of reach of a pull request (openspec change cloud-live-tests)."""

import importlib.util
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).parents[1]
FOLDER = ROOT / ".github" / "workflows"
WORKFLOW = FOLDER / "live.yml"


def _pins() -> dict:
    spec = importlib.util.spec_from_file_location("smoke_ci", ROOT / "scripts" / "smoke_ci.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.PINS


PINS = _pins()


@pytest.fixture(scope="module")
def workflow() -> dict:
    return yaml.safe_load(WORKFLOW.read_text())


@pytest.fixture(scope="module")
def job(workflow) -> dict:
    return workflow["jobs"]["live"]


def test_only_the_schedule_and_the_button_start_it(workflow):
    assert set(workflow[True]) == {"schedule", "workflow_dispatch"}  # YAML reads `on` as True


def test_it_is_the_one_job_of_a_workflow_of_its_own(workflow):
    assert list(workflow["jobs"]) == ["live"]
    assert "live" not in yaml.safe_load((FOLDER / "ci.yml").read_text())["jobs"]


def test_every_provider_has_a_cell_with_a_model_on_linux(job):
    cells = job["strategy"]["matrix"]["include"]
    assert sorted(c["provider"] for c in cells) == sorted(PINS)
    assert all(c["model"] for c in cells)
    assert job["runs-on"] == "ubuntu-latest"
    assert job["strategy"]["fail-fast"] is False


def test_a_cell_ends_after_its_own_limit(job):
    assert job["timeout-minutes"] == 30


def test_the_key_stands_in_the_test_step_alone(job, workflow):
    assert job["environment"] == "live"
    assert "secrets." not in str({k: v for k, v in workflow.items() if k != "jobs"})
    assert "secrets." not in str({k: v for k, v in job.items() if k != "steps"})
    named = [s for s in job["steps"] if "secrets." in str(s)]
    assert [s["name"] for s in named] == ["Live tests"]
    assert named[0]["env"]["LADO_LIVE_API_KEY"] == "${{ secrets.LADO_LIVE_API_KEY }}"


def test_the_token_reads_and_the_checkout_keeps_no_credentials(workflow, job):
    assert workflow["permissions"] == {"contents": "read"}
    assert "permissions" not in job
    checkout = next(s for s in job["steps"] if "actions/checkout" in s.get("uses", ""))
    assert checkout["with"]["persist-credentials"] is False


def test_two_runs_wait_for_each_other(workflow):
    assert workflow["concurrency"] == {"group": "live", "cancel-in-progress": False}


def test_what_a_cell_leaves_is_uploaded_whatever_happened(job):
    [upload] = [s for s in job["steps"] if "upload-artifact" in s.get("uses", "")]
    assert upload["if"] == "always()"
    assert upload["with"]["retention-days"] == 5
    [cell] = [s for s in job["steps"] if s.get("name") == "Live tests"]
    assert 'smoke_ci.py live "$PROVIDER" "$RUNNER_TEMP/live"' in cell["run"]
    assert upload["with"]["path"] == "${{ runner.temp }}/live"


@pytest.mark.parametrize(
    "path", [p for p in sorted(FOLDER.iterdir()) if p.name != "live.yml"], ids=lambda p: p.name
)
def test_no_other_workflow_names_the_key_or_the_environment(path):
    text = path.read_text()
    assert "LADO_LIVE_API_KEY" not in text
    assert "environment: live" not in text
