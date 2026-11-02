Task: LAD-175

## Why

Symptom: on PR #201 (LAD-174, commit 6c7d6f81) CI's job `smoke ubuntu-latest codex`
(run 41486435978, attempt 1) failed at the teardown of
`tests/smoke/test_smoke.py::test_a_codex_agent_gets_none_of_codex_s_own_subagents[codex]`:
"processes left after the test, killed", naming `git -c safe.bareRepository=explicit
ls-remote https://github.com/openai/plugins.git HEAD` and its `git-remote-https` helpers,
each "started in" that test. The test itself passed; rerunning the failed job was green.

Cause, checked in this run (Codex CLI 0.162.0, its source at tag `rust-v0.162.0` and by
hand in LADO's container):

- At its start Codex syncs OpenAI's curated plugins catalogue in a background thread
  (`core-plugins/src/startup_sync.rs`, thread `plugins-curated-repo-sync`): a
  `git ls-remote https://github.com/openai/plugins.git HEAD`, then a clone into
  `CODEX_HOME/.tmp/plugins`. Every entry to it (`maybe_start_plugin_startup_tasks_for_config`,
  `maybe_start_curated_repo_sync_for_config`) is gated by `features.plugins`.
- LADO's own Codex agents already have `features.plugins = false` (LAD-166, living spec
  `agent-start-screens`, "A Codex agent starts without Codex's plugins"), so the task's
  first guess, switching it off in the agent's config, is already done and is not the
  cause.
- The leftover comes from the test's own control run: before it starts the LADO session,
  the test runs a plain `codex exec --skip-git-repo-check hi` with the smoke's "user" Codex
  home (`codex_home`, whose config.toml has a model provider and nothing else), so its
  plugins are on. The fake endpoint answers at once, `codex exec` ends within a second or
  two, and the `ls-remote` it started on GitHub is orphaned; when GitHub is slow it
  outlives the test plus the teardown's 10 s wait.
- By hand, in LADO's container: a plain `codex exec` with such a home leaves
  `.tmp/plugins` (the catalogue cloned); the same run with `features.plugins = false` makes
  no `.tmp` at all. `codex login --with-api-key` (the fixture's login) syncs nothing.
- No other test runs a plain `codex exec`; every other Codex process of the smoke tests is
  a LADO agent (plugins off) or a `codex login`/`codex login status`/`codex sandbox`
  (no sync).

Why it is built so: the control run was added with the subagents check (codex-subagents-off,
D4) to prove that the model's metadata still turns Codex's subagents on; it was meant to be
"Codex with no LADO config" and took the user's config as it is, plugins on.

Options weighed:

- A (taken): the control run switches only the plugins off, `-c features.plugins=false` on
  its command line. It starts no network work of its own, and it still is Codex with none of
  LADO's subagent settings, which is what it checks. Long-term cost: one argument and its
  comment; a Codex release that adds other background network work at start would show up
  the same way and be named by the teardown.
- B: `[features] plugins = false` in the smoke fixture's user config.toml. Every smoke test
  would then run with a "user" whose plugins are off, which no real user has; it would hide
  a regression where LADO starts to carry the user's `[features]` into an agent's config
  (the plugins check of "A Codex agent starts without Codex's plugins" would pass for the
  wrong reason).
- C: the test waits for the orphaned `git` to end, or kills it itself. It keeps a network
  call to GitHub inside a test that needs none, slows the test by up to the ls-remote's own
  time, and hides the same leak from the teardown's check.

Held against the design principles and ROADMAP.md: the change is test-only; LADO's code and
its neutral core do not change; no silent drop (the teardown keeps naming any process a test
leaves); one source of truth (the switch is Codex's own `features.plugins`, the same key the
agents' config uses).

## What Changes

- `tests/smoke/test_smoke.py`, `test_a_codex_agent_gets_none_of_codex_s_own_subagents`: the
  control `codex exec` gets `-c features.plugins=false`, with a comment naming the cause
  (Codex's curated plugins sync, LAD-175).
- The living spec `codex-agent-turns`: the scenario "A model whose metadata turns the
  subagents on" says the plain `codex exec` runs with its plugins off.
- No CHANGELOG line: nothing a user sees changes. No version bump of its own (tests only).

## Scope

- The control run of that one smoke test.

## Out of scope

- LADO's Codex agent config: it already has `features.plugins = false` (LAD-166).
- The smoke fixture's user config (option B): it would make the smoke's user unlike a real
  one and weaken the agents' plugins check.
- Waiting for or killing the orphan in the test (option C): it keeps a needless network
  call and hides the leak.
- Raising the teardown's 10 s wait (`tests/leftovers.py`): it would hide slow leaks of every
  test, not fix this one.

## Decisions for the record

- D1. `-c features.plugins=false` on the control's command line rather than a line in the
  user's config.toml: the change stays inside the test that needs it, and the fixture keeps
  modelling a real user (option B, above).
- D2. The control keeps every other setting as it is (no `multi_agent`, `agents.enabled` or
  other LADO key): its job is to show that the model's metadata turns the subagents on
  without LADO's settings; the plugins feature has no part in the tool list (the build
  checks the control's assertion still holds with it).
- D3. No new unit test: the defect is in a smoke test's subprocess and only the smoke layer
  (real Codex) reaches it; the proof is that test's teardown (no "processes left") on CI's
  smoke cells, Linux and macOS, on the pull request, plus a local run of the Codex smoke.

## Impact

- Tests: `tests/smoke/test_smoke.py`.
- Specs: `codex-agent-turns` (one scenario reworded).
- Docs: none; CHANGELOG: none.
- Version: none of its own (a test fix).
