""".github/workflows/ci.yml: every job's time limit; the pytest commands of jobs `unit`,
`integration` and `ui` and their shards; the `ui` pytest step's limit under its job's; job
`web`, make dist and the Node tests; the UI jobs' browser from a cache only runs outside a
pull request save; job `smoke`, the smoke
tests on Linux and macOS for every provider, where job `changes` says a run needs it (every
push to main, the daily schedule, a manual dispatch, a pull request beyond the skip list);
job `container`, LADO's image built and tested in two shards on amd64 and arm64 on every
run, from nothing without a layer cache (release.yml reads none either); job
`ci-ok`, the one check `main` requires, over every other job; the triggers; and the
concurrency rule that cancels only a pull request's older run."""

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


def pytest_runs(job: dict) -> list[str]:
    return [s["run"] for s in job["steps"] if s.get("run", "").startswith("uv run pytest")]


def test_unit_tests_with_lint_on_each_python(workflow):
    unit = workflow["jobs"]["unit"]
    assert unit["name"] == "unit (${{ matrix.python-version }})"
    assert unit["strategy"]["matrix"] == {"python-version": ["3.10", "3.14"]}
    runs = [s["run"] for s in unit["steps"] if "run" in s]
    assert runs[-3:] == ["uv run ruff format --check", "uv run ruff check", JUNIT_UNIT]


JUNIT_UNIT = "uv run pytest -n auto --junitxml=junit.xml"


@pytest.mark.parametrize(
    ("job", "name"),
    [
        ("unit", "junit-unit-${{ matrix.python-version }}"),
        ("integration", "junit-integration-${{ matrix.python-version }}-${{ matrix.shard }}"),
        ("ui", "junit-ui-${{ matrix.shard }}"),
    ],
)
def test_the_test_jobs_keep_their_junit_report_also_when_red(workflow, job, name):
    """The test audit reads durations and failures over weeks (docs/research/test-audit.md):
    each cell's report, uploaded right after its pytest run whatever its result."""
    steps = workflow["jobs"][job]["steps"]
    upload = step_using(steps, "actions/upload-artifact")
    assert steps.index(upload) == len(steps) - 1
    assert steps[-2]["run"].endswith(" --junitxml=junit.xml")
    assert upload["if"] == "always()"
    assert upload["with"] == {"name": name, "path": "junit.xml", "retention-days": 90}


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
        "uv run pytest -m integration -n0 --shard ${{ matrix.shard }}/3 --junitxml=junit.xml"
    ]


def test_ui_tests_in_four_shards_on_two_workers_each_building_only_the_bundle(workflow):
    """Two workers: four on the 4-vCPU runner starve LADO's test timers (LAD-41). The browser
    tests need the bundle, not the type check or vitest: those are job web's."""
    ui = workflow["jobs"]["ui"]
    assert ui["name"] == "ui (${{ matrix.shard }})"
    assert ui["strategy"] == {"fail-fast": False, "matrix": {"shard": [1, 2, 3, 4]}}
    assert pytest_runs(ui) == [
        "uv run pytest -m ui -n 2 --shard ${{ matrix.shard }}/4 --junitxml=junit.xml"
    ]
    bundle = step_named(ui["steps"], "web UI bundle")
    assert "if" not in bundle
    assert bundle["run"] == "cd web && npm ci --no-audit --no-fund && npm run build"
    runs = [s.get("run", "") for s in ui["steps"]]
    assert not [r for r in runs if "make dist" in r or "make web" in r or "npm test" in r]


def test_the_ui_tests_step_ends_before_its_job_so_its_log_and_junit_stay(workflow):
    """A job cancelled by its own limit keeps neither the log nor the junit report (LAD-271):
    the pytest step has a shorter one, and the upload runs after it whatever its end."""
    ui = workflow["jobs"]["ui"]
    (step,) = [s for s in ui["steps"] if s.get("run", "").startswith("uv run pytest")]
    assert step["timeout-minutes"] == 12
    assert step["timeout-minutes"] < ui["timeout-minutes"] == 25
    assert step_using(ui["steps"], "actions/upload-artifact")["if"] == "always()"


# The UI jobs' browser: Chromium and the packages --with-deps downloads, from a cache.

BROWSER_PATHS = "~/.cache/ms-playwright\n~/.cache/lado-apt\n"


@pytest.fixture(scope="module")
def ui_steps(workflow) -> list[dict]:
    return workflow["jobs"]["ui"]["steps"]


def test_the_browser_cache_is_the_images_and_playwrights_and_saved_outside_a_pull_request(
    ui_steps,
):
    """A new runner image takes a fresh --with-deps, never debs built for the one before;
    restore and save take the same paths under the same key; a pull request's cache is
    visible to it alone and would spend the 10 GB."""
    key = step_named(ui_steps, "Browser cache key")
    # :? fails the step loudly on a runner without them, never a key without the image.
    for part in ("${ImageOS:?}", "${ImageVersion:?}", 'version("playwright")'):
        assert part in key["run"]
    restore = step_using(ui_steps, "actions/cache/restore")
    save = step_using(ui_steps, "actions/cache/save")
    assert restore["with"] == save["with"]
    assert restore["with"]["key"] == f"${{{{ steps.{key['id']}.outputs.key }}}}"
    assert set(restore["with"]["path"].split()) == set(BROWSER_PATHS.split())
    hit = f"steps.{restore['id']}.outputs.cache-hit != 'true'"
    assert "github.event_name != 'pull_request'" in save["if"] and hit in save["if"]


def test_a_cache_hit_asks_no_mirror_and_a_miss_keeps_its_debs(ui_steps):
    browser = step_named(ui_steps, "Browser")
    assert "cache-hit" in browser["env"]["HIT"]
    # A hung mirror ends this step, not the job's whole budget.
    assert "timeout-minutes" in browser
    hit, miss = browser["run"].split("else\n")
    assert "$HIT" in hit.splitlines()[0]
    assert "dpkg -i ~/.cache/lado-apt/" in hit and "playwright install chromium" in hit
    assert "--with-deps" not in hit and "apt-get" not in hit
    assert "Keep-Downloaded-Packages" in miss
    assert miss.index("Acquire::Retries") < miss.index("--with-deps")
    assert miss.index("--with-deps") < miss.index("/var/cache/apt/archives")


def test_the_browser_is_saved_after_its_install_and_before_the_tests(ui_steps):
    """Saved before the tests: a red test does not lose main's cache."""
    labels = [s.get("name") or s.get("uses", "").split("@")[0] or s["run"] for s in ui_steps]
    order = ["uv sync --locked", "Browser cache key", "actions/cache/restore", "Browser"]
    order += ["actions/cache/save"]
    order += ["uv run pytest -m ui -n 2 --shard ${{ matrix.shard }}/4 --junitxml=junit.xml"]
    positions = [labels.index(label) for label in order]
    assert positions == sorted(positions)


def test_web_runs_make_dist_and_the_node_tests_beside_the_ui_tests(workflow):
    """make dist: the web UI's stale-types check, tsc, vitest, the build and the bundle in
    the sdist and the wheel; the Node tests of the OpenCode-family plugin."""
    jobs = workflow["jobs"]
    runs = [step.get("run", "") for step in jobs["web"]["steps"]]
    assert "make dist" in runs and "node --test tests/js/*.test.mjs" in runs
    # No UI job waits for it: a vitest failure does not hold the browser tests back.
    assert "needs" not in jobs["ui"] and "needs" not in jobs["web"]


def test_every_job_has_a_time_limit(workflow):
    """Without one a hung job runs GitHub's six hours (ui (1) on an apt mirror, 2026-10-31)."""
    unlimited = [name for name, job in workflow["jobs"].items() if "timeout-minutes" not in job]
    assert unlimited == []


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


def test_the_image_is_tested_whole_on_each_architectures_own_runner(container):
    """amd64 and arm64 each on a native runner (no emulation), each cell to its end
    (fail-fast off), and the shards the matrix makes those the tests' K/N divides into."""
    strategy = container["strategy"]
    matrix = strategy["matrix"]
    assert sorted(matrix["arch"]) == ["amd64", "arm64"]
    runners = {one["arch"]: one["runner"] for one in matrix["include"]}
    assert set(runners) == {"amd64", "arm64"}
    assert "arm" in runners["arm64"] and "arm" not in runners["amd64"]
    assert container["runs-on"] == "${{ matrix.runner }}"
    assert strategy["fail-fast"] is False
    tests = step_named(container["steps"], "Container tests")["run"]
    [shards] = re.findall(r"\$\{\{ matrix\.shard \}\}/(\d+)", tests)
    assert matrix["shard"] == list(range(1, int(shards) + 1))


def test_the_container_job_runs_on_every_run(container):
    assert "if" not in container and "needs" not in container


def test_the_container_job_builds_then_tests_and_keeps_its_out(container):
    steps = container["steps"]
    # The layers' sizes in the log: a new layer's is the image's growth.
    assert step_named(steps, "Image")["run"].endswith("\ndocker history lado:local\n")
    run = step_named(steps, "Container tests")["run"]
    assert run == (
        'uv run python scripts/smoke_ci.py container "$RUNNER_TEMP/container" ${{ matrix.shard }}/2'
    )
    names = [s.get("name") for s in steps]
    assert names.index("Image") < names.index("Container tests")
    upload = step_using(steps, "actions/upload-artifact")
    assert upload["if"] == "always()"
    assert upload["with"]["name"] == "container-${{ matrix.arch }}-${{ matrix.shard }}"
    # With test_browser.py's screenshot (its SHOTS: the runner's temp dir is /tmp).
    assert upload["with"]["path"] == "${{ runner.temp }}/container\n/tmp/lado-container-shots\n"


def test_the_container_job_uses_no_layer_cache(container):
    """LAD-252's measurement: GitHub's cache saved 14-16 s of a cell that ends 1.5 % of
    green pull request runs, and took 7 GB of the repository's 10 GB Actions cache. Each cell
    builds from nothing on the runner's own Docker, on every event."""
    job = yaml.safe_dump(container)
    for word in (
        "setup-buildx-action",
        "ghaction-github-runtime",
        "type=gha",
        "cache-from",
        "cache-to",
        "--builder",
    ):
        assert word not in job


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
    assert "brew install" in tmux and "apt-get install" in tmux  # macOS and Linux
    run = step_named(steps, "Smoke test")
    assert "scripts/smoke_ci.py run " in run["run"] and '"$PROVIDER"' in run["run"]
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
