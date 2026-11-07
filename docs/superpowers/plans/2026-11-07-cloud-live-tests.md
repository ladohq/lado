# Live tests on a cloud model: implementation plan

**Goal:** the live tests of all four providers run on cheap OpenRouter models, by hand and weekly
in GitHub Actions, outside `ci-ok`, with the key out of reach of pull requests.

**Architecture:** the existing `LADO_LIVE_ENDPOINT` path becomes the only one, proved by a trial
before anything is removed; a `live` cell in `scripts/smoke_ci.py`, and a workflow `live.yml` of
its own.

**Tech Stack:** Python 3.10+, pytest, GitHub Actions, OpenRouter.

**Spec:** `docs/superpowers/specs/2026-11-07-cloud-live-tests-design.md`,
`openspec/changes/cloud-live-tests/`.

## Global Constraints

- No key value in a file, message, artifact, log or commit; `OPENROUTER_API_KEY` of the agents'
  environment is the human's own and is never used.
- No paid request before the human's explicit yes to the trial (design.md D10); stop at $4 spent.
- Bridge code is written only if the human chooses it after a `redesign`; this plan has none.
- Every `uses:` pinned to a 40-character SHA with `# vX.Y.Z`, the same pins as ci.yml.
- `scripts/smoke_ci.py` stays standard library only and imports nothing of LADO.
- A live test is "written, not run" in the build report unless it ran.
- `.lado/sdlc.md` and CHANGELOG.md stay as they are.
- Task 1 comes first; nothing of LM Studio, LiteLLM or Claude's own setup goes before it worked.
- No subscription and no Anthropic key in any test; `test_codex_login.py` alone stays on
  a person's login.

## Review Focus

1. A job killed at its timeout with a log holding the key: nothing unredacted may be in `<out>`,
   as the upload is `if: always()` (test in Task 3).
2. A Codex cell red only because `test_codex_login.py` skips (test in Task 3).
3. A release that takes skipped providers for a pass: `make test-live` with no endpoint
   skips, so docs/release.md must not rest on it (Task 5).
4. A `-k opencode` or `-k kilo` that selects nothing: pytest exits 5, the cell must be red (test in
   Task 3).
5. A Claude Code agent on a model other than the test's (a dearer default): `check_models` fails
   (test by the trial; Task 2).
6. A run left going when the limit is spent: a 402 ends a turn, and the test must fail, not hang
   past the cell's limit (seen in the trial or named in its report).

---

### Task 1: The trial

Needs the human's yes and the key `OPENROUTER_LIVE_KEY` (the design doc's "What the human does").
Ask through the supervisor; do nothing paid before the answer. No code changes here. All commands
take `LADO_LIVE_ENDPOINT=https://openrouter.ai/api/v1 LADO_LIVE_API_KEY="$OPENROUTER_LIVE_KEY"
LADO_LIVE_IMAGE=1`, set for the command, never written to a file.

- [ ] **Step 1:** read the key's usage (`GET https://openrouter.ai/api/v1/key`), the starting
  figure; again after each step. Stop at $4.
- [ ] **Step 2:** `LADO_LIVE_MODEL=qwen/qwen3.7-flash uv run pytest -m live -n0 -v -k 'codex and
  test_worker_does_a_task'`. Does Codex keep its MCP tools? The same with
  `LADO_LIVE_MODEL=openai/gpt-5-nano`. Both red with the `namespace` error, or with no LADO tool:
  stop, ask the human through the supervisor: a bridge to OpenRouter or a direct OpenAI key.
  Report `redesign` with the answer.
- [ ] **Step 3:** Claude Code, by hand, as no live code knows the endpoint for it yet. In a shell
  with `CLAUDE_CONFIG_DIR` an empty folder holding `.claude.json` with `{"hasCompletedOnboarding":
  true}`, no `ANTHROPIC_API_KEY` and no `CLAUDE_CODE_OAUTH_TOKEN`:
  `ANTHROPIC_BASE_URL=https://openrouter.ai/api ANTHROPIC_AUTH_TOKEN="$OPENROUTER_LIVE_KEY"
  ANTHROPIC_MODEL=anthropic/claude-haiku-5.5 ANTHROPIC_DEFAULT_HAIKU_MODEL=anthropic/claude-haiku-5.5
  CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1 claude -p 'Reply OK.' --output-format json`. Then a
  real MCP tool call: a config with LADO's server is what Task 2 gives, so here a one-tool
  `--mcp-config` of a small script. Red: the same on `qwen/qwen3.7-flash`. Both red: stop, ask the
  human through the supervisor. The full Claude tests run at the end of Task 2.
- [ ] **Step 4:** `make test-live PROVIDER=codex`, `opencode`, `kilo` on the first model that worked
  (`qwen/qwen3.7-flash` for OpenCode and Kilo first). A provider red: the same on
  `openai/gpt-5-nano`. Red on both: stop, report `redesign`.
- [ ] **Step 5:** three full runs of the chosen setup, each provider.
- [ ] **Step 6:** artifact `trial-report` and
  `docs/superpowers/reports/2026-11-07-cloud-live-tests-trial.md`: a table of provider, scenario,
  passes out of three; model; cost of a run; each failure's cause. Grep the report for the key
  before committing. Commit by path: `The trial of the live tests on OpenRouter (LAD-231)`. Claude
  Code's three runs come after Task 2, on the same key and within the same $4; add them then.

### Task 2: One setup for four providers

**Files:**
- Rename: `tests/local_models.py` to `tests/live_models.py`, `tests/test_local_models.py` to
  `tests/test_live_models.py`
- Modify: `tests/live/conftest.py`, `tests/live/test_live.py`, `tests/real_clis.py` (`with_model`
  goes if nothing else uses it)

**Interfaces:**
- Produces: `live_models.endpoint()`, `endpoint_model(provider)`, `endpoint_problem(provider)`
  (now also for no endpoint), `SETUPS: dict[str, Callable[[str, Path], dict[str, str]]]` (replaces
  `write_endpoint_config`), `LOGIN_VARIABLES: tuple[str, ...]`, `opencode_config(model, base_url,
  key_variable)`, `codex_config(model, base_url, env_key, name)`, `API_KEY`, `CONFIG_VARIABLES`,
  `MODEL_VARIABLES`.

- [ ] **Step 1:** `git mv` both files, fix the imports, and write the failing test:

```python
@pytest.mark.parametrize("provider", ["codex", "opencode", "kilo"])
def test_without_an_endpoint_the_tests_name_what_to_set(monkeypatch, provider):
    monkeypatch.delenv(live_models.ENDPOINT, raising=False)
    problem = live_models.endpoint_problem(provider)
    for variable in (live_models.ENDPOINT, live_models.API_KEY, live_models.ENDPOINT_MODEL):
        assert variable in problem


def test_every_provider_has_an_entry():
    assert sorted(live_models.SETUPS) == sorted(providers.names())


def test_claude_codes_entry_gives_only_variables(endpoint_env, tmp_path):
    variables = live_models.SETUPS["claude"]("anthropic/claude-haiku-5.5", tmp_path)
    assert variables == {
        "ANTHROPIC_BASE_URL": ENDPOINT.removesuffix("/v1"),
        "ANTHROPIC_AUTH_TOKEN": os.environ[live_models.API_KEY],
        "ANTHROPIC_MODEL": "anthropic/claude-haiku-5.5",
        "ANTHROPIC_DEFAULT_HAIKU_MODEL": "anthropic/claude-haiku-5.5",
        "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
    }
    assert list(tmp_path.iterdir()) == []
```

- [ ] **Step 2: Run it:** `uv run pytest tests/test_live_models.py -n0` — FAIL.

- [ ] **Step 3: Implement.** In `endpoint_problem`, first:

```python
    if not endpoint():
        return f"no model to run on: set {ENDPOINT}, {API_KEY} and {ENDPOINT_MODEL}"
```

The entries, in place of `write_endpoint_config`:

```python
# What a person's login would give; each provider's entry alone says what a test uses.
LOGIN_VARIABLES = (
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_AUTH_TOKEN",
    "CLAUDE_CODE_OAUTH_TOKEN",
    "OPENAI_API_KEY",
    "OPENAI_BASE_URL",
)


def _claude(model: str, folder: Path) -> dict[str, str]:
    """Claude Code at the endpoint, as a value: it has no reference to a variable. A token,
    not ANTHROPIC_API_KEY: that is a question, and it would take it for Anthropic's own."""
    return {
        "ANTHROPIC_BASE_URL": endpoint().removesuffix("/v1"),
        "ANTHROPIC_AUTH_TOKEN": os.environ[API_KEY],
        "ANTHROPIC_MODEL": model,
        "ANTHROPIC_DEFAULT_HAIKU_MODEL": model,  # its background calls name a haiku of their own
        "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
    }


def _codex(model: str, folder: Path) -> dict[str, str]:
    """`folder` is the test's CODEX_HOME."""
    (folder / "config.toml").write_text(codex_config(model, endpoint(), API_KEY, ENDPOINT_PROVIDER))
    return {}


def _opencode_family(provider: str):
    def setup(model: str, folder: Path) -> dict[str, str]:
        path = folder / f"{provider}-config.json"
        path.write_text(json.dumps(opencode_config(model, endpoint(), API_KEY)))
        return {CONFIG_VARIABLES[provider]: str(path)}

    return setup


# One entry per provider: a new CLI's whole setup on the endpoint.
SETUPS = {
    "claude": _claude,
    "codex": _codex,
    "kilo": _opencode_family("kilo"),
    "opencode": _opencode_family("opencode"),
}
```

`live_provider` is then the same for all: the CLI's check, `endpoint_problem`, `delenv` of
`LOGIN_VARIABLES`, `folder = codex_home if name == "codex" else tmp_path` (or give every provider
its own folder and set `CODEX_HOME` in Codex's entry, if `codex_home` allows), the entry, `setenv`
of what it returns, and `XDG_STATE_HOME` for all; params `sorted(live_models.SETUPS)`.

Delete from `live_models.py`: `MODEL`, `LITELLM`, `INSTALL_TIMEOUT`, `START_TIMEOUT`, `lmstudio_url`,
`lmstudio_models`, `_instances`, `lmstudio_problem`, `lmstudio_sees_images`,
`write_lmstudio_config`, `BridgeError`, `_free_port`, `Bridge`; in `opencode_config` the `lmstudio`
case, keeping `endpoint/<id>`. `MIN_CONTEXT` stays as the config's context limit. The docstring
says what is left. In `tests/live/conftest.py` delete `LOCAL`, `CODEX_BASE_URL`, `BRIDGE_KEY`,
`lmstudio_model`, `codex_bridge`, `BRIDGES`; `MODELS` takes `endpoint_model(p)` for every provider;
`live_provider` calls `endpoint_problem` itself and keeps no branch on a provider. Delete too
`_local_unusable`, `_claude_unusable`, `UNUSABLE`, `CLAUDE_REPO` and `live_repo`'s Claude branch, the `delenv` of
`CLAUDE_CONFIG_DIR`, the `with_model` call; `declared_vision` only `LADO_LIVE_IMAGE`; `keep_evidence`
gets no bridge log, and its `files`
parameter goes when nothing else passes it. In `tests/live/test_live.py`: `claude_tools` takes the model from
`os.environ["ANTHROPIC_MODEL"]`, its "trusts the repo already" print goes, and `check_models` gains:

```python
        if provider == "claude":
            used = {
                entry["message"]["model"]
                for transcript in claude_transcripts(agent_cwd, since)
                for entry in transcript
                if entry.get("type") == "assistant" and entry.get("message", {}).get("model")
            }
            assert used <= {model}, (agent.name, used)
```

(`agent_cwd`, `since`: pass what the caller has; a synthetic entry such as `<synthetic>` is left
out if the transcripts show one.) Then, on the trial's key, `LADO_LIVE_MODEL=<Claude's model>
make test-live PROVIDER=claude` with the endpoint's variables, three times: the report's Claude
rows. A test that cannot pass on the endpoint: stop, ask through the supervisor.

In `tests/test_live_models.py` delete the fake LM
Studio, `fake_litellm` and their tests. Docstrings of both, and of `tests/live/test_live.py` where
they name LM Studio.

- [ ] **Step 4: Run:** `uv run pytest tests/test_live_models.py -n0`, then `uv run pytest -m live
  --collect-only -q` (collects; no model), and with no endpoint `make test-live PROVIDER=kilo`
  shows the skips. `grep -rn -i 'lm studio\|lmstudio\|litellm' tests/live tests/live_models.py
  tests/test_live_models.py` is empty.
- [ ] **Step 5: Commit** by path: `All four providers' live tests run on a remote endpoint, set up by
  one entry each (LAD-231)`.

### Task 3: The live cell

**Files:**
- Modify: `scripts/smoke_ci.py`
- Test: `tests/test_smoke_ci.py`

**Interfaces:**
- Consumes: `install_once`, `cell`, `PINS`.
- Produces: `install(provider) -> dict | None` (the environment, or None after the third failure),
  `live(provider, out) -> int`, `redact(folder, secret) -> None`.

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


@pytest.fixture
def live_cell(monkeypatch):
    """`live` with its install and pytest replaced; `seen` holds each pytest command."""
    seen = []
    monkeypatch.setattr(smoke_ci, "install", lambda provider: dict(os.environ))
    monkeypatch.setenv("LADO_LIVE_API_KEY", "s3cr3t")
    return seen


@pytest.mark.parametrize("code", [0, 1])
def test_a_live_cell_leaves_only_redacted_files_in_its_folder(
    code, tmp_path, monkeypatch, live_cell
):
    out = tmp_path / "out"

    def cell(tests, log, work, name, env=None):
        live_cell.append(tests)
        assert not out.exists() or not any(out.iterdir())  # nothing there while it runs
        log.write_text("s3cr3t")
        (work / "evidence").mkdir()
        (work / "evidence" / "screen").write_text("s3cr3t")
        return code

    monkeypatch.setattr(smoke_ci, "cell", cell)
    assert smoke_ci.live("codex", out) == code
    assert live_cell[0][:4] == ["timeout", "--kill-after=30", "1500", "uv"]
    assert live_cell[0][-5:] == [
        "-n0",
        "-v",
        "-k",
        "codex",
        "--ignore=tests/live/test_codex_login.py",
    ]
    assert (out / "live-codex.log").read_text() == "<redacted>"
    assert (out / "evidence" / "screen").read_text() == "<redacted>"


def test_a_crash_during_the_tests_leaves_nothing_to_upload(tmp_path, monkeypatch, live_cell):
    out = tmp_path / "out"

    def cell(tests, log, work, name, env=None):
        log.write_text("s3cr3t")
        raise OSError("killed")

    monkeypatch.setattr(smoke_ci, "cell", cell)
    with pytest.raises(OSError):
        smoke_ci.live("codex", out)
    assert not out.exists() or not any(out.iterdir())


def test_no_tests_is_no_pass():
    assert not smoke_ci.passed("===== no tests ran in 0.01s =====", 5)
    assert not smoke_ci.passed("===== 2 passed, 1 skipped in 9.00s =====", 0)


def test_an_unknown_provider_has_no_live_cell(capsys):
    assert smoke_ci.main(["live", "nobody", "out"]) == 2
```

- [ ] **Step 2: Run them:** `uv run pytest tests/test_smoke_ci.py -n0` — FAIL.

- [ ] **Step 3: Implement**

```python
LIVE_LIMIT = "1500"  # seconds: under the job's 30 minutes, so a hang leaves a log and evidence


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
    """One cell of live.yml. It works in a folder of its own and moves the files to `out`
    only once redacted: the workflow uploads `out` whatever happened, a killed job too."""
    env = install(provider)
    if env is None:
        return 1
    work = Path(tempfile.mkdtemp(prefix="lado-live-"))
    tests = [
        "timeout",
        "--kill-after=30",
        LIVE_LIMIT,
        "uv",
        "run",
        "pytest",
        "-m",
        "live",
        "-n0",
        "-v",
        "-k",
        provider,
        "--ignore=tests/live/test_codex_login.py",
    ]
    code = cell(tests, work / f"live-{provider}.log", work, f"live {provider}", env)
    redact(work, os.environ.get("LADO_LIVE_API_KEY", ""))
    shutil.copytree(work, out, dirs_exist_ok=True)
    shutil.rmtree(work, ignore_errors=True)
    return code
```

`install` is `run`'s loop moved out, with `run` calling it; `main` takes `live` as it takes `run`,
with the same check on `PINS`; docstring and USAGE name it.

- [ ] **Step 4: Run them:** the same command — PASS.
- [ ] **Step 5: Commit** by path: `A live cell for CI, its key redacted from what it leaves
  (LAD-231)`.

### Task 4: The workflow

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


def test_every_provider_has_a_cell_with_a_model_on_linux(job):
    cells = job["strategy"]["matrix"]["include"]
    assert sorted(c["provider"] for c in cells) == sorted(PINS)
    assert all(c["model"] for c in cells)
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
# The live tests of every provider on cheap cloud models (docs/testing.md): weekly on
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
        # Each provider with its cheapest model that passed the trial (Task 1).
        include:
          - {provider: claude, model: anthropic/claude-haiku-5.5}
          - {provider: codex, model: qwen/qwen3.7-flash}
          - {provider: kilo, model: qwen/qwen3.7-flash}
          - {provider: opencode, model: qwen/qwen3.7-flash}
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
          LADO_LIVE_MODEL: ${{ matrix.model }}
          LADO_LIVE_IMAGE: "1"
        run: uv run python scripts/smoke_ci.py live "$PROVIDER" "$RUNNER_TEMP/live"
      - uses: actions/upload-artifact@cf430e030ddbb5b0abf93d22962f4752f3646cd9 # v7.0.2
        if: always()
        with:
          name: live-${{ matrix.provider }}
          path: ${{ runner.temp }}/live
          retention-days: 5
```

Write in each row the model Task 1 settled for that provider.

- [ ] **Step 4: Run:** `uv run pytest tests/test_live_workflow.py tests/test_workflow_security.py -n0`
  — PASS.
- [ ] **Step 5: Commit** by path: `The live tests run weekly and by hand in a workflow of their own
  (LAD-231)`.

### Task 5: Documents

**Files:** `docs/testing.md`, `docs/release.md`, `AGENTS.md`, `BACKLOG.md`.

- [ ] **Step 1:** docs/testing.md, the live section: rewrite it without LM Studio, the bridge,
  `uvx`, `LADO_LIVE_CODEX_BASE_URL`, `LADO_LIVE_LMSTUDIO_URL` and Claude Code's human config. It
  says: all four providers run on `LADO_LIVE_ENDPOINT`, which has no default, each by its entry in
  `live_models.SETUPS`; without it, its key and a model their tests skip, naming what to set, and
  a run of skips proves nothing. Claude Code's route (design.md D15) and the gap of D16. Replace `never a paid model` with the
  rule: a paid model only with a limited key and the human's yes, the schedule in CI being that
  yes, given once by LAD-231; "Claude Code only with the human's yes" goes. Replace "Live tests are not in CI" with `live.yml`: when it runs,
  the environment `live`, the secret, the cost, a red run. Layer 6 likewise.
- [ ] **Step 2:** docs/release.md, section 2, step 3 becomes: `gh workflow run live.yml` on `main`
  at the RC's commit, every cell green, and `gh run list --workflow live.yml --limit 1 --json
  headSha,conclusion` shows the SHA of `git rev-parse HEAD`; a failed cell is rerun by the flaky
  rule of the checks (a pass on rerun is a flake, noted, no code changed for it). Check its other mentions of `make test-live` (lines 383-384) and
  say the same there.
- [ ] **Step 3:** AGENTS.md's Testing, layer 6: `Not in CI: at release; Claude Code only with the
  human's yes` becomes `Weekly and by hand in live.yml, every provider on OpenRouter, outside
  ci-ok, and on each RC.`
- [ ] **Step 4:** BACKLOG.md, "Live: qwen3.5 answers a tool call as text now and then" and "Flaky:
  the Codex live image test's w1 stays busy on its task on LM Studio": add a line that LM Studio
  left the live tests (LAD-231), and whether the trial saw the same.
- [ ] **Step 5:** `uv run pytest tests/test_agents_md.py -n0`, `make lint`, `make test`, the three
  openspec checks of `.lado/sdlc.md`.
- [ ] **Step 6: Commit** by path: `docs/testing.md and the release say where the live tests run now
  (LAD-231)`.
