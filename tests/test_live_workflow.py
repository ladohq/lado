""".github/workflows/live.yml: the live tests in GitHub Actions, started by hand at release."""

import importlib.util
import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "live.yml"
PROBE = ROOT / ".github" / "workflows" / "windows-shell.yml"


def _live_ci():
    spec = importlib.util.spec_from_file_location("live_ci", ROOT / "scripts" / "live_ci.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PINS = _live_ci().PINS
LOCAL_ONLY = _live_ci().LOCAL_ONLY


@pytest.fixture(scope="module")
def text() -> str:
    return WORKFLOW.read_text()


@pytest.fixture(scope="module")
def workflow(text) -> dict:
    return yaml.safe_load(text)


@pytest.fixture(scope="module")
def cell(workflow) -> dict:
    return workflow["jobs"]["cell"]


@pytest.fixture(scope="module")
def steps(cell) -> list[dict]:
    return cell["steps"]


def step_named(steps, name: str) -> dict:
    (step,) = [s for s in steps if s.get("name") == name]
    return step


def step_using(steps, action: str) -> dict:
    (step,) = [s for s in steps if s.get("uses", "").startswith(action + "@")]
    return step


def test_started_by_hand_only(workflow):
    # PyYAML reads the key `on` as True. No push, pull request or schedule.
    assert workflow[True] == {"workflow_dispatch": None}


def test_reads_contents_only(workflow):
    assert workflow["permissions"] == {"contents": "read"}
    for job in workflow["jobs"].values():
        assert "permissions" not in job


def test_linux_and_macos_cells_for_each_cloud_provider(cell):
    strategy = cell["strategy"]
    assert strategy["fail-fast"] is False
    assert strategy["matrix"] == {
        "os": ["ubuntu-latest", "macos-latest"],
        "provider": list(PINS),
    }
    assert cell["runs-on"] == "${{ matrix.os }}"
    assert cell["timeout-minutes"] == 45


def test_windows_calls_the_probe_once_per_provider_live_only(workflow):
    windows = workflow["jobs"]["windows"]
    assert windows["strategy"] == {"fail-fast": False, "matrix": {"provider": list(PINS)}}
    assert windows["uses"] == "./.github/workflows/windows-shell.yml"
    assert windows["with"] == {"tests": False, "live": True, "provider": "${{ matrix.provider }}"}
    assert "secrets" not in windows
    assert set(workflow["jobs"]) == {"cell", "windows"}


def test_the_probe_takes_the_call(workflow):
    called = yaml.safe_load(PROBE.read_text())[True]["workflow_call"]
    assert set(workflow["jobs"]["windows"]["with"]) <= set(called["inputs"])


def test_no_secret_and_no_local_only_provider_in_the_cloud(workflow):
    """Claude Code runs only locally (the human's rule), Codex too (its local model)."""
    for path in (WORKFLOW, PROBE):
        assert "secrets" not in path.read_text(), path.name
    probe = yaml.safe_load(PROBE.read_text())
    named = [
        *workflow["jobs"]["cell"]["strategy"]["matrix"]["provider"],
        *workflow["jobs"]["windows"]["strategy"]["matrix"]["provider"],
        *probe[True]["workflow_dispatch"]["inputs"]["provider"]["options"],
    ]
    assert not set(named) & set(LOCAL_ONLY)
    probe_settings = probe["jobs"]["settings"]["steps"][0]["run"]
    for provider in LOCAL_ONLY:
        assert provider not in probe_settings, provider


def test_a_cell_sets_up_then_runs_its_provider(steps):
    names = [s.get("name") or s["uses"].split("@")[0] for s in steps]
    assert names[:2] == ["actions/checkout", "astral-sh/setup-uv"]
    order = [
        names.index(n) for n in ("tmux", "actions/setup-node", "uv sync", "Live tests", "Summary")
    ]
    assert order == sorted(order)
    assert names[-1] == "actions/upload-artifact"
    assert "brew install tmux" in step_named(steps, "tmux")["run"]
    assert "apt-get install -y tmux" in step_named(steps, "tmux")["run"]
    assert step_named(steps, "uv sync")["run"] == "uv sync --locked"
    live = step_named(steps, "Live tests")
    assert 'uv run python scripts/live_ci.py run "$PROVIDER" "$OUT"' in live["run"]
    assert live["env"] == {"PROVIDER": "${{ matrix.provider }}"}


def test_the_cells_out_is_uploaded_always(steps):
    upload = step_using(steps, "actions/upload-artifact")
    assert upload["if"] == "always()"
    assert upload["with"]["name"] == "live-${{ matrix.os }}-${{ matrix.provider }}"
    assert upload["with"]["path"] == "${{ env.OUT }}"
    assert 1 <= upload["with"]["retention-days"] <= 7


def test_summary_names_the_cell_its_exit_and_its_logs_end(steps):
    summary = step_named(steps, "Summary")
    assert summary["if"] == "always()"
    assert "GITHUB_STEP_SUMMARY" in summary["run"] and "tail" in summary["run"]
    assert summary["env"]["CODE"] == "${{ steps.live.outputs.code }}"
    live = step_named(steps, "Live tests")
    assert live["id"] == "live" and "GITHUB_OUTPUT" in live["run"]


def test_actions_pinned_to_a_commit_with_its_version(text):
    uses = re.findall(r"uses:\s*(\S+)(.*)", text)
    assert uses
    for action, rest in uses:
        if action.startswith(("actions/checkout@", "./")):
            continue
        assert re.fullmatch(r"[\w.-]+/[\w.-]+@[0-9a-f]{40}", action), action
        assert re.fullmatch(r"\s*# v\d+(\.\d+)*", rest), (action, rest)
