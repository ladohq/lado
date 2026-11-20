Task: LAD-302

## Why

Symptom: `tests/smoke/test_smoke.py::test_model_of_a_codex_agent_on_a_server_shows_its_model_alone[codex]`
failed in CI of PR #341 (run 44570527846, commit 90459655, job `smoke macos-latest codex`,
step Smoke test) with `assert 'On Шлюз' in screen`: Codex 0.162.0's screen ended with
`› /model` and, below it, `Шлюз GPT default · /private/var/folders/…`, with no list of models.
The same job was green on the next commit (3da05e7d, run 44573569195). The pull request did not
touch the test or `src/lado/providers/codex.py`.

Cause: a race in the test, not a defect of LADO or of Codex. After `/model` the test waits until
the screen holds `CODEX_MODEL` (`Шлюз GPT`), but Codex's status line under the composer shows the
current model the whole time (`Шлюз GPT default · <folder>`). So the wait is already true before
`/model` is sent, the test captures the screen at once, and it passes only when Codex has drawn
its list by then. On a fast machine it has; on a loaded macOS runner it sometimes has not, and
the screen still shows the composer with its status line. Of the task's two guesses, it is the
first: the screen was captured before the list was drawn; Codex does not show the list in
another form.

Checked by the analyst on Linux with Codex 0.162.0 (`uv run pytest -m smoke -n0 -s` on this
test, a probe not committed):

- before `/model` is sent, `CODEX_MODEL in tmux.capture(...)` is already `True`;
- the ready screen is Codex's list, which no longer shows the status line:

  ```
    Select Model and Effort

  › 1. Шлюз GPT (current)  On Шлюз

    enter default · s session · esc back
  ```

`On Шлюз` is LADO's own text: the description `On <server>` that `codex.py` writes into the
agent's model list for each model of a server. It shows only in the list.

The product is not at fault: the list is right whenever it is drawn, and the failed screen is the
one before it.

Options weighed:

- A (taken): wait for `On Шлюз`, the text of the list's own line, instead of `CODEX_MODEL`. The
  wait then ends only once the list is drawn; the assertions stay as they are. A list that never
  shows LADO's model (a real regression) fails on the wait's timeout, whose message carries the
  agent's screen (`agent_helpers.diagnostics`). Long-term cost: one line; it rests on LADO's own
  wording, which a Codex update does not change.
- B: wait for Codex's heading `Select Model and Effort`. Equally exact today, but it rests on
  Codex's wording, which changes between versions (the smoke runs the latest Codex), and a
  renamed heading would fail the test for no fault of LADO's. Long-term cost: a fix on each
  rewording.
- C: accept both forms, as the task allows "if both are right". The status-line form is not a
  form of the list: it shows the session's model, not the list Codex took from LADO, so the test
  would no longer check that Codex reads LADO's list and shows no OpenAI model. Rejected.

## What Changes

- `tests/smoke/test_smoke.py`: `test_model_of_a_codex_agent_on_a_server_shows_its_model_alone`
  waits for `On Шлюз` after `/model` instead of `CODEX_MODEL`.
- Neither a minor nor a patch of its own: tests only, users see nothing, so no CHANGELOG.md line,
  and no API, schema, MCP, CLI or UI change.

## Scope

- `tests/smoke/test_smoke.py`, this one test. Nothing in `src/` or `web/`.

## Out of scope

- `src/lado/providers/codex.py`: the list it writes shows right; nothing there to fix.
- The Claude twin `test_model_of_a_claude_agent_on_a_server_shows_its_model_alone`: it waits
  for `Default`, a word of Claude's list, not for the model's name, and it has no recorded
  flake; changing it without a failure is not this task.
- A rerun plugin or a longer timeout: they would not help, as the wait is true at once; the
  settings forbid retries inside pytest.
- BACKLOG.md: it has no entry for this test, so nothing to remove.

## Acceptance criteria

- AC-1: After `/model`, the test waits until the screen holds `On Шлюз`; the assertions after the
  wait are unchanged.
- AC-2: The race is shown by hand once, with a probe not committed: before `/model` is sent the
  screen already holds `CODEX_MODEL` (the old wait is true at once) and does not hold `On Шлюз`
  (the new wait is not). The build report quotes the probe's output.
- AC-3: `make test-smoke PROVIDER=codex` passes locally, its exit status read (not piped), and the
  test alone (`-m smoke -n0`, its node id) passes 10 times in a row.
- AC-4: `make lint` passes, and the pull request's `smoke macos-latest codex` cell is green on its
  first run and on 3 reruns of that cell (`gh run rerun <id> --job <job id>`), 4 green runs in
  a row; the build report names the runs.

## Impact

- `tests/smoke/test_smoke.py` only.
- No delta (`skip_specs` in `.openspec.yaml`): no behaviour rule changes; archived with
  `--skip-specs`.

## Decisions for the record

- Scale tweak: a test-only change of known shape, as the earlier flake fix
  `multiline-paste-test-waits-for-file`; review by precision.
- Option A over B: LADO's own text does not change with Codex's versions; over C: the status line
  proves nothing about the list.
- Test layer: smoke (real Codex, a local endpoint), the test itself; no new test. The race needs
  Codex's real screen, which no lower layer has.
- The macOS cell's reruns are the task's own check; they show no regression, while the probe of
  AC-2 is what proves the cause, since the flake is rare.
- Branch `fix/lad-302-codex-model-smoke-waits-for-list` to `main`; this pull request is the task's
  last.
