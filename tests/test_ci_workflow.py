""".github/workflows/ci.yml: the pytest commands of jobs `unit`, `integration` and `ui` and
their shards; job `smoke`, the smoke tests on Linux and macOS for every provider, where job
`changes` says a run needs it (every push to main, the daily schedule, a manual dispatch, a
pull request beyond the skip list); job `container`, LADO's image built and tested on amd64
and arm64 on every run, its layers from a cache only main writes (release.yml reads none);
job `ci-ok`, the one check `main` requires, over every other job; the triggers; and the
concurrency rule that cancels only a pull request's older run."""

import importlib.util
import os
import subprocess
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


def pytest_runs(job: dict) -> list[str]:
    return [s["run"] for s in job["steps"] if s.get("run", "").startswith("uv run pytest")]


def test_unit_tests_with_lint_on_each_python(workflow):
    unit = workflow["jobs"]["unit"]
    assert unit["name"] == "unit (${{ matrix.python-version }})"
    assert unit["strategy"]["matrix"] == {"python-version": ["3.10", "3.13"]}
    runs = [s["run"] for s in unit["steps"] if "run" in s]
    assert runs[-3:] == ["uv run ruff format --check", "uv run ruff check", "uv run pytest -n auto"]


def test_integration_tests_in_three_shards_per_python_each_in_one_process(workflow):
    """-n auto on GitHub's 4-vCPU runners starves LADO's short test timers (LAD-41): each
    shard is one process, and three of them run at once on runners of their own."""
    integration = workflow["jobs"]["integration"]
    assert integration["name"] == "integration (${{ matrix.python-version }}, ${{ matrix.shard }})"
    assert integration["strategy"] == {
        "fail-fast": False,
        "matrix": {"python-version": ["3.10", "3.13"], "shard": [1, 2, 3]},
    }
    assert pytest_runs(integration) == [
        "uv run pytest -m integration -n0 --shard ${{ matrix.shard }}/3"
    ]


def test_ui_tests_in_two_shards_on_two_workers_and_make_dist_once(workflow):
    ui = workflow["jobs"]["ui"]
    assert ui["name"] == "ui (${{ matrix.shard }})"
    assert ui["strategy"] == {"fail-fast": False, "matrix": {"shard": [1, 2]}}
    assert pytest_runs(ui) == ["uv run pytest -m ui -n 2 --shard ${{ matrix.shard }}/2"]
    (dist,) = [s for s in ui["steps"] if s.get("run") == "make dist"]
    assert dist["if"] == "matrix.shard == 1"
    (bundle,) = [s for s in ui["steps"] if s.get("name") == "web UI bundle"]
    assert bundle["if"] == "matrix.shard != 1"
    assert bundle["run"] == "cd web && npm ci --no-audit --no-fund && npm run build"


def test_ci_runs_on_pull_requests_pushes_to_main_daily_and_by_hand(workflow):
    # PyYAML reads the key `on` as True.
    assert workflow[True] == {
        "push": {"branches": ["main"]},
        "pull_request": None,
        "schedule": [{"cron": "47 3 * * *"}],
        "workflow_dispatch": None,
    }


def test_only_a_pull_requests_older_run_is_cancelled(workflow):
    """A push, schedule or dispatch run is alone in its group (its run id): never cancelled."""
    assert workflow["concurrency"] == {
        "group": "ci-${{ github.event_name == 'pull_request' && "
        "github.event.pull_request.number || github.run_id }}",
        "cancel-in-progress": "${{ github.event_name == 'pull_request' }}",
    }


# ci-ok: the one required check.


def test_ci_ok_needs_every_other_job_and_runs_whatever_their_results(workflow):
    ci_ok = workflow["jobs"]["ci-ok"]
    others = sorted(name for name in workflow["jobs"] if name != "ci-ok")
    assert sorted(ci_ok["needs"]) == others
    # Without it a failed job skips ci-ok, and a skipped required check counts as passed.
    assert ci_ok["if"] == "always()"


def test_ci_ok_gives_the_needs_to_its_script(workflow):
    (verdict,) = [s for s in workflow["jobs"]["ci-ok"]["steps"] if "run" in s]
    assert verdict["run"] == "python3 scripts/ci_ok.py"
    assert verdict["env"] == {"NEEDS": "${{ toJSON(needs) }}"}


# The smoke only where it can concern the change.

# The paths a pull request may change without the smoke (openspec capability
# continuous-integration). ci.yml holds the list; this copy is the check of it.
SKIP_LIST = [
    "web/",
    "docs/",
    "openspec/",
    "tests/ui/",
    "tests/js/",
    "README.md",
    "CHANGELOG.md",
    "AGENTS.md",
    "BACKLOG.md",
    "ROADMAP.md",
    "SECURITY.md",
    ".github/dependabot.yml",
]
# What the smoke runs: no path of the skip list may be one of these or hold one.
SMOKE_RUNS = [
    "src/",
    "scripts/",
    "tests/",
    "docker/",
    "pyproject.toml",
    "uv.lock",
    ".github/workflows/",
]
ALLOWED_UNDER_TESTS = ["tests/ui/", "tests/js/"]


@pytest.fixture(scope="module")
def changes(workflow) -> dict:
    return workflow["jobs"]["changes"]


def needed_step(changes) -> dict:
    (step,) = [s for s in changes["steps"] if s.get("id") == "needed"]
    return step


def skip_list(changes) -> list[str]:
    return needed_step(changes)["env"]["SMOKE_SKIP"].split()


def test_the_skip_list_is_the_specs(changes):
    assert skip_list(changes) == SKIP_LIST


def concerns_the_smoke(path: str) -> bool:
    if path in ALLOWED_UNDER_TESTS:
        return False
    return any(path.startswith(r) or r.startswith(path) for r in SMOKE_RUNS)


@pytest.mark.parametrize("path", SKIP_LIST)
def test_no_path_of_the_skip_list_is_one_the_smoke_runs(path):
    assert not concerns_the_smoke(path)


@pytest.mark.parametrize(
    "path",
    ["scripts/", "tests/integration/", "tests/", "src/lado/", "pyproject.toml", "uv.lock"]
    + [".github/", ".github/workflows/ci.yml", "tests/smoke/", "docker/", "docker/Dockerfile"],
)
def test_the_guard_refuses_a_path_the_smoke_runs(path):
    assert concerns_the_smoke(path)


# The job `container`: LADO's image built and tested on each architecture.


@pytest.fixture(scope="module")
def container(workflow) -> dict:
    return workflow["jobs"]["container"]


def test_the_image_is_built_and_tested_on_each_architectures_own_runner(container):
    assert container["name"] == "container (${{ matrix.arch }})"
    assert container["runs-on"] == "${{ matrix.runner }}"
    assert container["strategy"] == {
        "fail-fast": False,
        "matrix": {
            "include": [
                {"arch": "amd64", "runner": "ubuntu-24.04"},
                {"arch": "arm64", "runner": "ubuntu-24.04-arm"},
            ]
        },
    }
    assert container["timeout-minutes"] == 30


def test_the_container_job_runs_on_every_run(container):
    assert "if" not in container and "needs" not in container


def test_the_container_job_builds_then_tests_and_keeps_its_out(container):
    steps = container["steps"]
    # The layers' sizes in the log: a new layer's is the image's growth.
    assert step_named(steps, "Image")["run"].endswith("\ndocker history lado:local\n")
    run = step_named(steps, "Container tests")["run"]
    assert run == 'uv run python scripts/smoke_ci.py container "$RUNNER_TEMP/container"'
    names = [s.get("name") for s in steps]
    assert names.index("Image") < names.index("Container tests")
    upload = step_using(steps, "actions/upload-artifact")
    assert upload["if"] == "always()"
    assert upload["with"]["name"] == "container-${{ matrix.arch }}"
    # With test_browser.py's screenshot (its SHOTS: the runner's temp dir is /tmp).
    assert upload["with"]["path"] == "${{ runner.temp }}/container\n/tmp/lado-container-shots\n"


def test_the_builder_and_the_caches_token_come_before_the_image(container):
    """make docker's own builder cannot use GitHub's cache: a BuildKit builder of its own,
    and the runtime's token and URLs in the build's environment."""
    steps = container["steps"]
    names = [s.get("name") or s.get("uses", "").split("@")[0] for s in steps]
    buildx = step_using(steps, "docker/setup-buildx-action")
    assert buildx["id"] == "buildx"
    step_using(steps, "crazy-max/ghaction-github-runtime")
    order = [
        names.index(n)
        for n in ("docker/setup-buildx-action", "crazy-max/ghaction-github-runtime", "Image")
    ]
    assert order == sorted(order)


def image_build(container, event: str, arch: str, tmp_path) -> subprocess.CompletedProcess:
    """The step Image's script run for `event` on `arch`, with make and docker stubs that
    write their arguments, one call a line, to tmp_path/calls."""
    step = step_named(container["steps"], "Image")
    values = {
        "${{ github.event_name }}": event,
        "${{ matrix.arch }}": arch,
        "${{ steps.buildx.outputs.name }}": "builder-1",
    }
    env = {}
    for name, value in step["env"].items():
        for expression, filled in values.items():
            value = value.replace(expression, filled)
        assert "${{" not in value, value
        env[name] = value
    bin = tmp_path / "bin"
    bin.mkdir()
    for command in ("make", "docker"):
        stub = bin / command
        calls = tmp_path / "calls"
        stub.write_text(f'#!/bin/sh\nprintf "%s|" {command} "$@" >> "{calls}"\necho >> "{calls}"\n')
        stub.chmod(0o755)
    env["PATH"] = f"{bin}:{os.environ['PATH']}"
    return subprocess.run(
        ["bash", "-e", "-c", step["run"]], env=env, capture_output=True, text=True
    )


def build_flags(container, event: str, arch: str, tmp_path) -> list[str]:
    """The flags the step Image gives `docker build` through make docker."""
    done = image_build(container, event, arch, tmp_path)
    assert done.returncode == 0, done.stderr
    calls = (tmp_path / "calls").read_text().splitlines()
    [make] = [c.split("|")[:-1] for c in calls if c.startswith("make|")]
    assert make[:2] == ["make", "docker"] and len(make) == 3, make
    name, flags = make[2].split("=", 1)
    assert name == "DOCKER_BUILD_FLAGS"
    return flags.split()


def cache_flags(scope: str, read: bool, write: bool) -> list[str]:
    flags = ["--builder", "builder-1", "--load"]
    flags += ["--cache-from", f"type=gha,scope={scope}"] if read else ["--no-cache"]
    if write:
        flags += ["--cache-to", f"type=gha,mode=min,scope={scope}"]
    return flags


@pytest.mark.parametrize("arch", ["amd64", "arm64"])
def test_a_pull_request_reads_mains_cache_and_writes_none(container, arch, tmp_path):
    flags = build_flags(container, "pull_request", arch, tmp_path)
    assert flags == cache_flags(f"container-{arch}", read=True, write=False)
    assert "--cache-to" not in flags


@pytest.mark.parametrize("arch", ["amd64", "arm64"])
def test_a_push_to_main_reads_and_writes_its_architectures_cache(container, arch, tmp_path):
    flags = build_flags(container, "push", arch, tmp_path)
    assert flags == cache_flags(f"container-{arch}", read=True, write=True)


@pytest.mark.parametrize("event", ["schedule", "workflow_dispatch"])
def test_the_daily_and_a_manual_run_build_anew_and_write_the_cache(container, event, tmp_path):
    flags = build_flags(container, event, "amd64", tmp_path)
    assert flags == cache_flags("container-amd64", read=False, write=True)
    assert "--cache-from" not in flags


def test_an_event_the_image_does_not_know_fails_the_step(container, tmp_path):
    """A trigger added to ci.yml later must choose its cache, not get one by default."""
    done = image_build(container, "merge_group", "amd64", tmp_path)
    assert done.returncode != 0
    assert "merge_group" in done.stdout + done.stderr


def test_the_image_is_listed_after_its_build(container, tmp_path):
    build_flags(container, "push", "amd64", tmp_path)
    calls = (tmp_path / "calls").read_text().splitlines()
    assert calls[-1] == "docker|history|lado:local|"


def test_the_release_builds_without_any_cache():
    """The published image is built from nothing: no layer CI wrote can enter it."""
    release = (ROOT / ".github" / "workflows" / "release.yml").read_text()
    for word in ("cache-from", "cache-to", "type=gha"):
        assert word not in release


def test_the_container_job_pushes_nothing(container):
    job = yaml.safe_dump(container)
    for word in ("docker login", "docker push", "--push", "login-action", "build-push-action"):
        assert word not in job


def test_changes_answers_from_the_pull_requests_diff(changes):
    assert changes["outputs"] == {"smoke": "${{ steps.needed.outputs.smoke }}"}
    checkout = step_using(changes["steps"], "actions/checkout")
    # The merge base of base...head needs the history.
    assert checkout["with"] == {"fetch-depth": 0}
    step = needed_step(changes)
    assert step["env"]["EVENT"] == "${{ github.event_name }}"
    assert step["env"]["BASE"] == "${{ github.event.pull_request.base.sha }}"
    assert step["env"]["HEAD"] == "${{ github.event.pull_request.head.sha }}"
    assert 'python3 scripts/smoke_ci.py needed "$EVENT" "$@" >> "$GITHUB_OUTPUT"' in step["run"]


def test_the_smoke_is_skipped_by_its_jobs_condition_not_by_the_triggers(workflow, smoke):
    assert smoke["needs"] == "changes"
    assert smoke["if"] == "needs.changes.outputs.smoke == 'true'"
    assert "paths-ignore" not in str(workflow[True]) and "paths" not in str(workflow[True])


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
