# Live tests on a cloud model: implementation plan

**Goal:** Codex, OpenCode and Kilo's live tests run on a cheap OpenRouter model, by hand and weekly
in GitHub Actions, outside `ci-ok`, with the key out of reach of pull requests.

**Architecture:** the existing `LADO_LIVE_ENDPOINT` path, a bridge that can also point at it for
Codex, a `live` cell in `scripts/smoke_ci.py`, and a workflow `live.yml` of its own.

**Tech Stack:** Python 3.10+, pytest, GitHub Actions, LiteLLM through `uvx`, OpenRouter.

**Spec:** `docs/superpowers/specs/2026-11-07-cloud-live-tests-design.md`,
`openspec/changes/cloud-live-tests/`.

## Global Constraints

- No key value in a file, message, artifact, log or commit; `OPENROUTER_API_KEY` of the agents'
  environment is the human's own and is never used.
- No paid request before the human's explicit yes to the trial (design.md D10); stop at $4 spent.
- Every `uses:` pinned to a 40-character SHA with `# vX.Y.Z`, the same pins as ci.yml.
- `scripts/smoke_ci.py` stays standard library only and imports nothing of LADO.
- A live test is "written, not run" in the build report unless it ran.
- `.lado/sdlc.md`, docs/release.md and CHANGELOG.md stay as they are.

## Review Focus

1. A key in the pytest log of a passing cell: the upload is `if: always()`, so redaction must run
   on a pass too (test in Task 2).
2. A Codex cell red only because `test_codex_login.py` skips (test in Task 2).
3. The bridge's config with the value instead of the reference (test in Task 1).
4. A `-k opencode` or `-k kilo` that selects nothing: pytest exits 5, the cell must be red (test in
   Task 2).
5. A run left going when the limit is spent: a 402 ends a turn, and the test must fail, not hang
   past `timeout-minutes` (seen in the trial or named in its report).

---

### Task 1: The bridge reaches a remote endpoint

**Files:**
- Modify: `tests/local_models.py` (`Bridge.start`, new `codex_bridged`, constant `CODEX_BRIDGE`)
- Modify: `tests/live/conftest.py` (`codex_bridge`, `live_provider`, docstring)
- Test: `tests/test_local_models.py`

**Interfaces:**
- Produces: `local_models.CODEX_BRIDGE = "LADO_LIVE_CODEX_BRIDGE"`;
  `local_models.codex_bridged() -> bool`;
  `Bridge.start(folder, upstream, model, command=LITELLM, key_variable=None)`, `upstream` ending
  in `/v1`.

- [ ] **Step 1: Write the failing tests**

```python
def test_the_bridge_names_the_endpoints_key_by_reference(tmp_path, fake_litellm, endpoint_env):
    command, _ = fake_litellm
    bridge = local_models.Bridge.start(
        tmp_path, ENDPOINT, "m", command=command, key_variable=local_models.API_KEY
    )
    bridge.stop()
    config = (tmp_path / "litellm.yaml").read_text()
    assert f"api_base: {ENDPOINT}\n" in config
    assert "api_key: os.environ/LADO_LIVE_API_KEY\n" in config
    assert os.environ[local_models.API_KEY] not in config


def test_codex_goes_through_the_bridge_only_with_an_endpoint_and_the_switch(monkeypatch):
    monkeypatch.delenv(local_models.ENDPOINT, raising=False)
    monkeypatch.setenv(local_models.CODEX_BRIDGE, "1")
    assert not local_models.codex_bridged()
    monkeypatch.setenv(local_models.ENDPOINT, "https://example.test/v1")
    assert local_models.codex_bridged()
    monkeypatch.delenv(local_models.CODEX_BRIDGE)
    assert not local_models.codex_bridged()
```

`fake_litellm` and `endpoint_env` are the file's fixtures. The existing LM Studio bridge tests now
pass an upstream ending in `/v1`; add an assertion there that the config keeps `api_key: none`.

- [ ] **Step 2: Run them:** `uv run pytest tests/test_local_models.py -n0` — FAIL on the missing
  names.

- [ ] **Step 3: Implement**

```python
CODEX_BRIDGE = "LADO_LIVE_CODEX_BRIDGE"  # Codex through the bridge to the endpoint, when "1"


def codex_bridged() -> bool:
    """Whether Codex reaches the remote endpoint through the bridge: an endpoint's Responses
    API may drop its MCP tools, as LM Studio's does."""
    return bool(endpoint()) and os.environ.get(CODEX_BRIDGE) == "1"
```

In `Bridge.start`: add `key_variable: str | None = None`; the config's lines become
`f"      api_base: {upstream}\n"` and
`f"      api_key: {f'os.environ/{key_variable}' if key_variable else 'none'}\n"`.

In `tests/live/conftest.py`, `codex_bridge`: `upstream, key = (local_models.endpoint(),
local_models.API_KEY) if ENDPOINT else (f"{local_models.lmstudio_url()}/v1", None)`, passed to
`Bridge.start(folder, upstream, MODELS["codex"], key_variable=key)`. In `live_provider`, before
`elif ENDPOINT:`, a branch `elif name == "codex" and local_models.codex_bridged():` that takes the
fixture, sets `BRIDGE_KEY`, and writes `codex_config(MODELS[name], bridge.base_url, BRIDGE_KEY)`
as the LM Studio branch does. Docstring: one sentence on the switch.

- [ ] **Step 4: Run them:** the same command — PASS.
- [ ] **Step 5: Commit** by path: `Live tests' bridge reaches a remote endpoint (LAD-231)`.

### Task 2: The live cell

**Files:**
- Modify: `scripts/smoke_ci.py`
- Test: `tests/test_smoke_ci.py`

**Interfaces:**
- Consumes: `install_once`, `cell`, `PINS`.
- Produces: `install(provider) -> dict | None` (the environment, or None after the third failure),
  `live(provider, out) -> int`, `redact(folder, secret) -> None`; `LIVE_PROVIDERS = ("codex",
  "opencode", "kilo")`.

- [ ] **Step 1: Write the failing tests**

```python
def test_redact_replaces_the_key_in_every_file(tmp_path):
    (tmp_path / "evidence").mkdir()
    (tmp_path / "evidence" / "screen").write_bytes(b"KEY=s3cr3t\n")
    (tmp_path / "live-codex.log").write_bytes(b"s3cr3t s3cr3t")
    smoke_ci.redact(tmp_path, "s3cr3t")
    assert (tmp_path / "evidence" / "screen").read_bytes() == b"KEY=<redacted>\n"
    assert (tmp_path / "live-codex.log").read_bytes() == b"<redacted> <redacted>"


def test_redact_without_a_key_changes_nothing(tmp_path):
    (tmp_path / "log").write_bytes(b"text")
    smoke_ci.redact(tmp_path, "")
    assert (tmp_path / "log").read_bytes() == b"text"


@pytest.mark.parametrize("code", [0, 1])
def test_a_live_cell_runs_the_providers_tests_and_redacts_on_a_pass_and_a_failure(
    code, tmp_path, monkeypatch
):
    calls = []

    def cell(tests, log, out, name, env=None):
        calls.append(tests)
        log.write_text("s3cr3t")
        return code

    monkeypatch.setattr(smoke_ci, "cell", cell)
    monkeypatch.setattr(smoke_ci, "install", lambda provider: dict(os.environ))
    monkeypatch.setenv("LADO_LIVE_API_KEY", "s3cr3t")
    assert smoke_ci.live("codex", tmp_path) == code
    assert calls[0][-5:] == ["-n0", "-v", "-k", "codex", "--ignore=tests/live/test_codex_login.py"]
    assert (tmp_path / "live-codex.log").read_text() == "<redacted>"


def test_no_tests_is_no_pass():
    assert not smoke_ci.passed("===== no tests ran in 0.01s =====", 5)
    assert not smoke_ci.passed("===== 2 passed, 1 skipped in 9.00s =====", 0)


def test_claude_has_no_live_cell(capsys):
    assert smoke_ci.main(["live", "claude", "out"]) == 2
```

- [ ] **Step 2: Run them:** `uv run pytest tests/test_smoke_ci.py -n0` — FAIL.

- [ ] **Step 3: Implement**

```python
LIVE_PROVIDERS = ("codex", "opencode", "kilo")  # Claude Code needs a subscription's login


def redact(folder: Path, secret: str) -> None:
    """Replace `secret` by <redacted> in every file under `folder`: artifacts of a public
    repository can be downloaded by anyone, and GitHub masks only logs."""
    if not secret:
        return
    for path in folder.rglob("*"):
        if path.is_file() and not path.is_symlink():
            data = path.read_bytes()
            if secret.encode() in data:
                path.write_bytes(data.replace(secret.encode(), b"<redacted>"))


def live(provider: str, out: Path) -> int:
    env = install(provider)
    if env is None:
        return 1
    tests = ["uv", "run", "pytest", "-m", "live", "-n0", "-v", "-k", provider,
             "--ignore=tests/live/test_codex_login.py"]
    code = cell(tests, out / f"live-{provider}.log", out, f"live {provider}", env)
    redact(out, os.environ.get("LADO_LIVE_API_KEY", ""))
    return code
```

`install` is `run`'s loop moved out, with `run` calling it; `main` takes `live` as it takes `run`,
with `LIVE_PROVIDERS` in place of `PINS` in the check; docstring and USAGE name it.

- [ ] **Step 4: Run them:** the same command — PASS.
- [ ] **Step 5: Commit** by path: `A live cell for CI, its key redacted from what it leaves
  (LAD-231)`.

### Task 3: The workflow

**Files:**
- Create: `.github/workflows/live.yml`
- Create: `tests/test_live_workflow.py`
- Modify: `tests/test_workflow_security.py:41` (the set gains `live.yml`)

**Interfaces:**
- Consumes: `scripts/smoke_ci.py live <provider> <out>`.

- [ ] **Step 1: Write the failing test** `tests/test_live_workflow.py`, with the fixtures of
  `tests/test_ci_workflow.py` (`text`, `workflow`; note YAML reads `on` as `True`):

```python
def test_only_the_schedule_and_the_button_start_it(workflow):
    assert set(workflow[True]) == {"schedule", "workflow_dispatch"}


def test_the_cells_are_the_three_providers_on_linux(job):
    assert job["strategy"]["matrix"] == {"provider": ["codex", "opencode", "kilo"]}
    assert job["runs-on"] == "ubuntu-latest"
    assert job["strategy"]["fail-fast"] is False


def test_the_key_stands_in_the_test_step_alone(job, workflow):
    assert job["environment"] == "live"
    named = [s for s in job["steps"] if "secrets." in str(s)]
    assert [s["name"] for s in named] == ["Live tests"]


def test_the_token_reads_and_the_checkout_keeps_no_credentials(workflow, job):
    assert workflow["permissions"] == {"contents": "read"}
    checkout = next(s for s in job["steps"] if "actions/checkout" in s.get("uses", ""))
    assert checkout["with"]["persist-credentials"] is False


def test_two_runs_wait_for_each_other(workflow):
    assert workflow["concurrency"] == {"group": "live", "cancel-in-progress": False}


def test_no_other_workflow_names_the_key_or_the_environment():
    for path in WORKFLOWS:
        if path.name != "live.yml":
            assert "LADO_LIVE_API_KEY" not in path.read_text(), path.name
            assert "environment: live" not in path.read_text(), path.name
```

- [ ] **Step 2: Run it:** `uv run pytest tests/test_live_workflow.py -n0` — FAIL (no file).

- [ ] **Step 3: Write `.github/workflows/live.yml`**

```yaml
# The live tests of Codex, OpenCode and Kilo on a cheap cloud model (docs/testing.md): weekly on
# main and by hand. Not part of ci.yml, so never of ci-ok: a provider's outage looks like a
# failed test. The key is a secret of the environment live, open only to main and tags v*, so
# no run of a pull request gets it. GitHub mails a red scheduled run to whoever last changed
# the cron line.
name: Live tests

on:
  schedule:
    - cron: "23 4 * * 1"
  workflow_dispatch:

permissions:
  contents: read

concurrency:
  group: live
  cancel-in-progress: false

jobs:
  live:
    name: live ${{ matrix.provider }}
    if: github.repository == 'ladohq/lado'
    runs-on: ubuntu-latest
    environment: live
    timeout-minutes: 30
    strategy:
      fail-fast: false
      matrix:
        provider: [codex, opencode, kilo]
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          persist-credentials: false
      - uses: astral-sh/setup-uv@07a047e608db84b3d8c06cd9a7c7dcc9c355c18e # v10.3.2
        with:
          version: "0.12.3"
          python-version: "3.13"
      - run: sudo apt-get install -y tmux
      - uses: actions/setup-node@949feb2413d6458794dcd2491c4babbbce0c15c1 # v7.1.0
        with:
          node-version: lts/*
      - name: uv sync
        run: uv sync --locked
      # Red unless the tests passed and none skipped. What it leaves has the key redacted.
      - name: Live tests
        env:
          PROVIDER: ${{ matrix.provider }}
          LADO_LIVE_ENDPOINT: https://openrouter.ai/api/v1
          LADO_LIVE_API_KEY: ${{ secrets.LADO_LIVE_API_KEY }}
          LADO_LIVE_MODEL: qwen/qwen3.7-flash
          LADO_LIVE_IMAGE: "1"
          LADO_LIVE_CODEX_BRIDGE: "1"
        run: uv run python scripts/smoke_ci.py live "$PROVIDER" "$RUNNER_TEMP/live"
      - uses: actions/upload-artifact@cf430e030ddbb5b0abf93d22962f4752f3646cd9 # v7.0.2
        if: always()
        with:
          name: live-${{ matrix.provider }}
          path: ${{ runner.temp }}/live
          retention-days: 5
```

The model and the switch are the first guess; Task 4 fixes them.

- [ ] **Step 4: Run:** `uv run pytest tests/test_live_workflow.py tests/test_workflow_security.py -n0`
  — PASS.
- [ ] **Step 5: Commit** by path: `The live tests run weekly and by hand in a workflow of their own
  (LAD-231)`.

### Task 4: The trial

Needs the human's yes and the key `OPENROUTER_LIVE_KEY` (the design doc's "What the human does").
Ask through the supervisor; do nothing paid before the answer. All commands take
`LADO_LIVE_ENDPOINT=https://openrouter.ai/api/v1 LADO_LIVE_API_KEY="$OPENROUTER_LIVE_KEY"
LADO_LIVE_IMAGE=1`, set for the command, never written to a file.

- [ ] **Step 1:** read the key's usage (`GET https://openrouter.ai/api/v1/key`), the starting
  figure; again after each step. Stop at $4.
- [ ] **Step 2:** `LADO_LIVE_MODEL=qwen/qwen3.7-flash uv run pytest -m live -n0 -v -k 'codex and
  test_worker_does_a_task'` direct: does Codex keep its MCP tools? Then the same with
  `LADO_LIVE_CODEX_BRIDGE=1`.
- [ ] **Step 3:** `make test-live PROVIDER=codex`, `opencode`, `kilo` on that model. Any provider
  red: the same on `qwen/qwen3.5-35b-a3b`. Red on both: stop, report `redesign`.
- [ ] **Step 4:** three full runs of the chosen setup, each provider.
- [ ] **Step 5:** artifact `trial-report` and
  `docs/superpowers/reports/2026-11-07-cloud-live-tests-trial.md`: a table of provider, scenario,
  passes out of three; model; direct or bridge; cost of a run; each failure's cause. Grep the
  report for the key before committing.
- [ ] **Step 6:** set `LADO_LIVE_MODEL` and `LADO_LIVE_CODEX_BRIDGE` in `live.yml` by the result
  (without a bridge, drop the line). Commit by path: `The live workflow takes the trial's model
  (LAD-231)`.

### Task 5: Documents

**Files:** `docs/testing.md`, `AGENTS.md`.

- [ ] **Step 1:** docs/testing.md. Replace `never a paid model` with the rule: a paid model only
  with a limited key and the human's yes, the schedule in CI being that yes, given once by LAD-231.
  Describe `LADO_LIVE_CODEX_BRIDGE`, and that without it the endpoint's Responses API must keep
  Codex's MCP tools. Replace "Live tests are not in CI" with `live.yml`: when it runs, the
  environment `live`, the secret, the cost, a red run. Layer 6: "and weekly in `live.yml`".
- [ ] **Step 2:** AGENTS.md's Testing, layer 6: `Not in CI: at release` becomes `Weekly and by hand
  in live.yml for Codex, OpenCode and Kilo, outside ci-ok; at release; Claude Code only with the
  human's yes.`
- [ ] **Step 3:** `uv run pytest tests/test_agents_md.py -n0`, `make lint`, `make test`, the three
  openspec checks of `.lado/sdlc.md`.
- [ ] **Step 4: Commit** by path: `docs/testing.md says where the live tests run now (LAD-231)`.
