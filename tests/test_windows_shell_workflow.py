""".github/workflows/windows-shell.yml: a Windows (+ WSL2) shell over tmate, started by hand."""

import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "windows-shell.yml"
# The wsl input as GitHub's web form gives it (a boolean) or the API (a string).
WSL = "inputs.wsl == true || inputs.wsl == 'true'"


@pytest.fixture(scope="module")
def text() -> str:
    return WORKFLOW.read_text()


@pytest.fixture(scope="module")
def workflow(text) -> dict:
    return yaml.safe_load(text)


@pytest.fixture(scope="module")
def steps(workflow) -> list[dict]:
    (job,) = workflow["jobs"].values()
    return job["steps"]


def step_using(steps, action: str) -> dict:
    (step,) = [s for s in steps if s.get("uses", "").startswith(action + "@")]
    return step


def test_started_only_by_hand(workflow):
    # PyYAML reads the key `on` as True.
    triggers = workflow[True]
    assert list(triggers) == ["workflow_dispatch"]


def test_inputs(workflow):
    inputs = workflow[True]["workflow_dispatch"]["inputs"]
    assert inputs["runner"]["type"] == "choice"
    assert inputs["runner"]["options"] == ["windows-latest", "windows-11-arm"]
    assert inputs["runner"]["default"] == "windows-latest"
    assert inputs["wsl"]["type"] == "boolean"
    assert inputs["wsl"]["default"] is True
    assert inputs["minutes"]["type"] == "number"
    assert inputs["minutes"]["default"] == 120


def test_job_runs_on_the_chosen_runner_for_the_chosen_minutes(workflow):
    (job,) = workflow["jobs"].values()
    assert job["runs-on"] == "${{ inputs.runner }}"
    # Started through the API (gh workflow run -f minutes=120), the input is the string
    # '120', which timeout-minutes refuses; fromJSON makes it a number either way.
    assert job["timeout-minutes"] == "${{ fromJSON(inputs.minutes) }}"


def test_wsl_steps_run_only_when_wsl_is_true_as_a_boolean_or_a_string(text):
    # From the API (gh workflow run -f wsl=false) the input may be the string 'false',
    # which a bare `if: inputs.wsl` takes as true.
    assert re.findall(r"inputs\.wsl\b.*", text)
    for line in re.findall(r"inputs\.wsl\b.*", text):
        assert line.startswith(WSL), line


def test_reads_contents_only(workflow):
    assert workflow["permissions"] == {"contents": "read"}
    for job in workflow["jobs"].values():
        assert "permissions" not in job


def test_third_party_actions_pinned_to_a_commit_with_its_version(text):
    uses = re.findall(r"uses:\s*(\S+)(.*)", text)
    assert uses
    for action, rest in uses:
        if action.startswith("actions/"):
            continue
        assert re.fullmatch(r"[\w.-]+/[\w.-]+@[0-9a-f]{40}", action), action
        assert re.fullmatch(r"\s*# v\d+(\.\d+)*", rest), (action, rest)


def test_wsl2_ubuntu_with_the_tools(steps):
    step = step_using(steps, "Vampire/setup-wsl")
    assert step["if"] == WSL
    assert step["with"]["distribution"] == "Ubuntu-24.04"
    assert str(step["with"]["wsl-version"]) == "2"
    packages = step["with"]["additional-packages"].split()
    assert {"tmux", "git", "curl", "build-essential", "less"} <= set(packages)
    assert all("continue-on-error" not in s for s in steps)


def test_wsl_on_arm_fails_before_setup(steps):
    """setup-wsl's Ubuntu 24.04 is an amd64 image: no silent WSL1 fallback on ARM."""
    setup = steps.index(step_using(steps, "Vampire/setup-wsl"))
    guards = [
        i
        for i, s in enumerate(steps)
        if "windows-11-arm" in s.get("if", "")
        and "inputs.wsl" in s.get("if", "")
        and "exit 1" in s.get("run", "")
    ]
    assert guards and guards[0] < setup


def test_wsl_checked_before_the_shell(steps):
    tmate = steps.index(step_using(steps, "mxschmitt/action-tmate"))
    checks = [
        i for i, s in enumerate(steps) if s.get("if") == WSL and "wsl -l -v" in s.get("run", "")
    ]
    assert checks and checks[0] < tmate
    run = steps[checks[0]]["run"]
    for command in ("wsl --version", "uname -m", "tmux -V"):
        assert command in run


def test_only_the_starter_can_connect(steps):
    step = step_using(steps, "mxschmitt/action-tmate")
    assert step["with"]["limit-access-to-actor"] is True
    assert steps[-1] is step
