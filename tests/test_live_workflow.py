""".github/workflows/live.yml: the live tests in GitHub Actions, started by hand at release."""

import importlib.util
import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "live.yml"
PROBE = ROOT / ".github" / "workflows" / "windows-shell.yml"
SECRET = "LADO_LIVE_CLAUDE_TOKEN"
GUARDED = f"${{{{ matrix.provider == 'claude' && secrets.{SECRET} || '' }}}}"
SCRUBBED = "always() && steps.scrub.outcome == 'success'"


def _pins() -> dict:
    spec = importlib.util.spec_from_file_location("live_ci", ROOT / "scripts" / "live_ci.py")
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
    # PyYAML reads the key `on` as True. No push, pull request or schedule: only users with
    # write access start it, and a fork's pull request never gets the secret.
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
    # A named secret, guarded by the provider: never `secrets: inherit`.
    assert windows["secrets"] == {SECRET: GUARDED}
    assert set(workflow["jobs"]) == {"cell", "windows"}


def test_the_probe_takes_the_call(workflow):
    called = yaml.safe_load(PROBE.read_text())[True]["workflow_call"]
    assert set(workflow["jobs"]["windows"]["with"]) <= set(called["inputs"])
    assert called["secrets"] == {SECRET: {"required": False}}


def test_a_cell_sets_up_then_runs_its_provider(steps):
    names = [s.get("name") or s["uses"].split("@")[0] for s in steps]
    assert names[:2] == ["actions/checkout", "astral-sh/setup-uv"]
    order = [
        names.index(n)
        for n in ("tmux", "actions/setup-node", "uv sync", "Live tests", "Scrub", "Summary")
    ]
    assert order == sorted(order)
    assert names[-1] == "actions/upload-artifact"
    assert "brew install tmux" in step_named(steps, "tmux")["run"]
    assert "apt-get install -y tmux" in step_named(steps, "tmux")["run"]
    assert step_named(steps, "uv sync")["run"] == "uv sync --locked"
    live = step_named(steps, "Live tests")
    assert "uv run python scripts/live_ci.py run" in live["run"]
    assert live["env"]["PROVIDER"] == "${{ matrix.provider }}"


def test_the_token_only_in_guarded_expressions_of_the_run_and_the_scrub(text, steps):
    assert text.count(f"secrets.{SECRET}") == text.count(GUARDED) == 3
    assert "secrets: inherit" not in text
    for step in steps:
        has = SECRET in str(step.get("env", {}))
        assert has == (step.get("name") in ("Live tests", "Scrub")), step
        if has:
            assert step["env"][SECRET] == GUARDED


def test_scrub_runs_always_on_the_cells_out_and_the_upload_needs_it(steps):
    scrub = step_named(steps, "Scrub")
    assert scrub["id"] == "scrub" and scrub["if"] == "always()"
    assert 'uv run python scripts/live_ci.py scrub "$OUT"' in scrub["run"]
    upload = step_using(steps, "actions/upload-artifact")
    assert upload["if"] == SCRUBBED
    assert upload["with"]["name"] == "live-${{ matrix.os }}-${{ matrix.provider }}"
    assert upload["with"]["path"] == "${{ env.OUT }}"
    assert 1 <= upload["with"]["retention-days"] <= 7
    live = step_named(steps, "Live tests")
    assert '"$OUT"' in live["run"]


def test_summary_names_the_cell_its_exit_and_its_logs_end(steps):
    summary = step_named(steps, "Summary")
    # It shows the log's end: only once the scrub went through.
    assert summary["if"] == SCRUBBED
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
