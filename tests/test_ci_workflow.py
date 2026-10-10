""".github/workflows/ci.yml's job `smoke`: the smoke tests on Linux and macOS for every
provider, on each pull request and push to main."""

import importlib.util
import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"


def _pins() -> dict:
    spec = importlib.util.spec_from_file_location("smoke_ci", ROOT / "scripts" / "smoke_ci.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.PINS


PINS = _pins()


@pytest.fixture(scope="module")
def text() -> str:
    return WORKFLOW.read_text()


@pytest.fixture(scope="module")
def workflow(text) -> dict:
    return yaml.safe_load(text)


@pytest.fixture(scope="module")
def smoke(workflow) -> dict:
    return workflow["jobs"]["smoke"]


@pytest.fixture(scope="module")
def steps(smoke) -> list[dict]:
    return smoke["steps"]


def step_named(steps, name: str) -> dict:
    (step,) = [s for s in steps if s.get("name") == name]
    return step


def step_using(steps, action: str) -> dict:
    (step,) = [s for s in steps if s.get("uses", "").startswith(action + "@")]
    return step


def test_ci_runs_on_pull_requests_and_pushes_to_main(workflow):
    # PyYAML reads the key `on` as True.
    assert workflow[True] == {"push": {"branches": ["main"]}, "pull_request": None}


def test_smoke_on_linux_and_macos_for_every_provider(smoke):
    assert smoke["runs-on"] == "${{ matrix.os }}"
    assert smoke["strategy"] == {
        "fail-fast": False,
        "matrix": {"os": ["ubuntu-latest", "macos-latest"], "provider": list(PINS)},
    }
    assert smoke["timeout-minutes"] == 20


def test_a_cell_sets_up_then_runs_its_provider(steps):
    names = [s.get("name") or s["uses"].split("@")[0] for s in steps]
    assert names[:2] == ["actions/checkout", "astral-sh/setup-uv"]
    order = [names.index(n) for n in ("tmux", "actions/setup-node", "uv sync", "Smoke test")]
    assert order == sorted(order)
    assert names[-1] == "actions/upload-artifact"
    tmux = step_named(steps, "tmux")["run"]
    assert "brew install tmux" in tmux and "apt-get install -y tmux" in tmux
    assert step_named(steps, "uv sync")["run"] == "uv sync --locked"
    run = step_named(steps, "Smoke test")
    assert run["run"] == 'uv run python scripts/smoke_ci.py run "$PROVIDER" "$RUNNER_TEMP/smoke"'
    assert run["env"] == {"PROVIDER": "${{ matrix.provider }}"}


def test_a_cells_out_is_uploaded_always(steps):
    upload = step_using(steps, "actions/upload-artifact")
    assert upload["if"] == "always()"
    assert upload["with"]["name"] == "smoke-${{ matrix.os }}-${{ matrix.provider }}"
    assert upload["with"]["path"] == "${{ runner.temp }}/smoke"
    assert 1 <= upload["with"]["retention-days"] <= 7


def test_no_secret(text):
    """No model, no account: the smoke points each CLI at a local endpoint."""
    assert "secrets" not in text


def test_the_smoke_jobs_actions_pinned_to_a_commit_with_its_version(text, smoke):
    lines = yaml.safe_dump(smoke)
    uses = [u for u in re.findall(r"uses:\s*(\S+)(.*)", text) if u[0] in lines]
    assert uses
    for action, rest in uses:
        if action.startswith("actions/checkout@"):
            continue
        assert re.fullmatch(r"[\w.-]+/[\w.-]+@[0-9a-f]{40}", action), action
        assert re.fullmatch(r"\s*# v\d+(\.\d+)*", rest), (action, rest)
