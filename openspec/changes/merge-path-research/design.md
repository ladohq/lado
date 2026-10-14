## Context

LAD-58 is research: why the way to a merge into `main` feels slow and what to do about it.
The analyst measured LADO's history in the design step; the human chose the
recommendations (design dialogue, 14 October 2026): R1-R6 taken, R7 and R8 not, the gate
`merge_ok` kept, tasks drafted in the report and created only on a separate yes.

Root cause, from the measurements below: the time a task spends on CI is set by one step,
the integration tests in one process (`-n0`, since LAD-41), 6-7 of a run's ~10 minutes,
paid two to three times per task (the developer's push, review fixes, the integrator's
push after bringing `main` in), and again for each flaky rerun. The largest share of a
task's whole time is the human's answer at `merge_ok` (49%), which is the human's choice
to keep. Reviews, caches and runner queues cost little.

## Measurements

Window 11-14 October 2026 (UTC). Sources: `gh api repos/ladohq/lado/actions/...` (runs,
their attempts and jobs with steps), `gh pr list --state all`, and a read-only copy of
`~/.lado/lado.db` (events `flow` and `flow_start` of runs `task/lad-*`). `measure.py`
(D2) reproduces them.

### CI wall time (start of the run to its last job's end)

| Period | Runs | Median | p90 |
|---|---|---|---|
| before LAD-41 (to 13.10 16:00) | 96 | 4.0 min | 4.9 min |
| after LAD-41 | 60 | 9.6 min | 12.5 min |

Steps of successful jobs after LAD-41 (median): `check` integration `-n0` 379 s
(3.10: 7.2 min, 3.13: 6.1 min), `check` unit `-n auto` 105 s, `ui` browser tests `-n 2`
206 s, `ui` `make dist` 63 s, `ui` Playwright install 21 s, smoke on macOS 65 s, on
Linux 27 s. Every setup step (checkout, setup-uv, `uv sync`, tmux, setup-node) is under
5 s: the caches work. Queue before a job starts: 0.1 min on Linux; on macOS up to 1.3 min
(p90). The unit job before LAD-41 ran integration with `-n auto` in ~2 min and failed on
timeouts; LAD-41 traded that for the longer `-n0`.

### CI runs per pull request

38 pull requests (#1-#38, Dependabot's and the releases' included): CI runs per pull
request median 3; LAD-52 (documents only) 7 full runs. Reruns of a failed attempt:
36 runs had more than one attempt; 19 of them were LAD-44's deliberate stress reruns.
Before LAD-41 most pull requests of tasks had 1-3 reruns for timeouts of
`pytest -m integration -n auto`; after it, required jobs failed for no cause in the work
4 times in 60 runs (integration 3.10 on the 0.38.0 release, LAD-57; integration 3.13 on
two runs; unit 3.10 on LAD-42). Smoke `macos-latest codex` failed 8 times in 156 runs;
not required, but a red mark on pull requests and on `main`. Pushes to `main`: 13 of 52
red since 11 October (most before LAD-41).

Opening to merge of the pull requests the task names: LAD-33 95 min, LAD-34 128 min,
LAD-42 24 min, LAD-44 515 min (overnight, 19 stress reruns), LAD-53 30 min. The pull
request opens late in the flow (in `build`), so this is review, `merge_ok` and merge.

### Time per flow state (10 runs of LAD tasks, minutes)

| Run | design | design_ok | build | review | merge_ok | merge | total |
|---|---|---|---|---|---|---|---|
| lad-31 | 36 | 1 | 63 | 15 | 92 | 8 | 217 |
| lad-35 | 14 | 4 | 111 | 8 | 4 | 6 | 147 |
| lad-38 | 3 | 1 | 4 | 5 | 0 | 17 | 30 |
| lad-39 | 11 | 3 | 48 | 6 | 2 | 7 | 76 |
| lad-40 | 3 | 7 | 8 | 21 | 1 | 13 | 52 |
| lad-41 | 2 | 5 | 75 | 11 | 109 | 46 | 248 |
| lad-34 | 30 | 28 | 33 | 11 | 100 | 13 | 215 |
| lad-33 | 60 | 4 | 17 | 9 | 73 | 12 | 175 |
| lad-52 | 7 | 2 | 43 | 25 | 488 | 15 | 581 |
| lad-53 | 11 | 0 | 16 | 3 | 2 | 14 | 45 |
| share | 10% | 3% | 23% | 6% | 49% | 9% | |

`merge` (6-46 min, median 13) is the integrator bringing `main` in, the local checks
when `main` moved, a push, and one more CI run. External review rounds (`@claude`, 33
runs) take about 1 min each, about one per pull request: rounds are not the bottleneck.

## Options

The CI time can be cut three ways:
1. **Parallel shards** of the slow suites (R1): the same tests, on more runners at once.
   Long-term cost: a few more job names to keep in the ruleset and in
   `tests/test_ci_workflow.py`; nothing in LADO's code.
2. **Run fewer tests per pull request** (R2's docs-only skip, R3's smoke filter, or
   integration on one Python only): cheaper, but every filter is a list that drifts from
   what the tests read, so each needs a guard. Integration on one Python saves runner
   minutes only, not wall time (the two Pythons run side by side), and the repository is
   public, so minutes are free: not taken.
3. **Change the merge discipline** (a merge queue, R7; dropping the integrator's local
   checks, R6): fewer sequential waits, at the price of the kit's and the ruleset's
   rules.

Against AGENTS.md: "Tested end to end" and the layers stay as they are (no test layer is
dropped from a pull request whose code it covers); "No silent drops": a skipped job says
why in its summary, and the aggregate check fails when any job it needs failed;
"One source of truth": the docs-only path list lives in one place, `ci.yml`, with a test
that no path on it is read by a test. ROADMAP's coming stages add providers and kits, which
grow the smoke matrix and the integration suite, so sharding pays more over time.

## Recommendations

- R1 (taken). Shard the integration tests into 3 jobs per Python version, each `-n0`, by a
  stable split of the test files; shard the UI tests into 2 jobs (`-n 2` each) with
  `make dist` in the first. Gain: CI wall ~9.6 → ~4-5 min; with 2-3 CI waits per task,
  ~10-15 min per task. Risk: low; the required check names change (ruleset), and
  AGENTS.md ("CI runs …", the worker counts) and `tests/test_ci_workflow.py` change.
- R2 (taken). One required check, `ci-ok`, a job that needs every other job and fails
  unless each succeeded or was skipped on purpose; the ruleset requires only it. On a
  pull request whose every changed file is on an allow-list of paths no test reads
  (`docs/research/`, `docs/superpowers/`, `openspec/`, `BACKLOG.md`, `ROADMAP.md`), the
  heavy jobs are skipped. A push to `main` always runs everything. Gain: a docs-only pull
  request's CI ~1 min instead of ~10 (5 of 38 pull requests); the ruleset stops depending
  on job names (R1 can reshape jobs freely). Risk: medium: a wrong path on the list lets
  untested code into `main`; guarded by a unit test that no file a test opens is under a
  listed path, and caught at the latest by `main`'s full run.
- R3 (taken). Smoke runs on pushes to `main`, once a day (schedule), on manual dispatch,
  and on pull requests that change `src/lado/providers/`, `runtime.py`, `hooks.py`,
  `agent_env.py`, `mcp_server.py`, `tests/smoke/`, `tests/real_clis.py`,
  `scripts/smoke_ci.py` or `ci.yml`. Gain: no flaky macOS red on unrelated pull requests;
  fewer macOS runners queued. Risk: a change outside the filter that breaks a CLI is seen
  only after the merge, on `main`. Changes AGENTS.md ("in CI on Linux and macOS (job
  smoke)", "on each pull request and push to main" in `tests/test_ci_workflow.py`'s
  docstring) and `.lado/sdlc.md` ("What CI proves": a green pull request is then not
  always the smoke).
- R4 (taken). Cancel a pull request's superseded runs (`concurrency` keyed by the pull
  request, `cancel-in-progress` only for pull requests, never for `main`). Gain: small,
  runners freed when fixes are pushed quickly. Risk: none.
- R5 (taken). Flake policy in `.lado/sdlc.md`: rerun only the failed jobs (`gh run rerun
  <id> --failed`), at most twice; each flake that passed on rerun is named in the ledger
  and proposed to the human as a tracker task (as LAD-57); no automatic retry in pytest,
  since LADO's timing failures have been real races (LAD-44). Gain: ~5 min per flake (the
  green jobs are not run again). Risk: low.
- R6 (taken). The integrator does not run the Checks locally after bringing `main` in; it
  pushes and relies on the pull request's CI, which it waits for anyway. A red CI in the
  work follows the existing rule (the merge commit stays, the developer fixes on top).
  Gain: 2-5 min per merge where `main` moved, and the machine-wide test lock stays free
  for other sessions. Risk: low. Set in `.lado/sdlc.md`'s Extra instructions for the
  integrator (they win over the kit's default); kit sdlc itself unchanged.
- R7 (not taken). A merge queue: tasks merge mostly one at a time and `main` seldom moves
  under a pull request; a queue adds a `merge_group` CI run per merge and a change of the
  integrator's routine. Revisit when parallel sessions merging into `main` the same hour
  are usual.
- R8 (not taken). More caching (setup steps take seconds), sharding the unit tests (under
  2 min, off the critical path once R1 lands) and a lower review round cap (rounds take
  about a minute, about one per pull request): no time is lost there.

## Proposed tasks

- A (size M): «CI: параллельные шарды тестов, одна обязательная проверка ci-ok, smoke по
  путям» — R1-R4: `ci.yml`, `tests/test_ci_workflow.py`, AGENTS.md (Commands, Testing),
  `.lado/sdlc.md` ("What CI proves"); the ruleset of `main` changed by the human (or with
  their yes) to require `ci-ok` once the job is green on `main`. Depends on nothing.
- B (size S): «sdlc.md: политика флейков и слияние без локальных проверок» — R5, R6 in
  `.lado/sdlc.md` (Review traps, Extra instructions for the integrator). Independent of A;
  after A the CI wait it relies on is shorter.

## Decisions

- D1. The report lives in `docs/research/merge-path.md`, beside LAD-52's
  `docs/research/docker-install.md`: research, not a guide or a design. English; the human
  gets a Russian summary in the tracker.
- D2. `docs/research/merge-path/measure.py` is evidence, standard library only, run by
  hand with `python3`: `--since`/`--until` (UTC dates), `--repo` (default
  `ladohq/lado`), `--db PATH` (a copy of `lado.db`, opened read-only with
  `mode=ro`; without it the flow table is left out), and the LAD-41 split as an option
  `--split <ISO time>`. It calls only `gh api` GET endpoints and `gh pr list`; it prints
  Markdown tables. Nothing in CI or the package uses it, and no test covers it (a research
  script, as LAD-52's Dockerfile).
- D3. The numbers in the report are the ones `measure.py` prints for 11-14 October 2026;
  when the developer's run differs from this design (a run's jobs changed since, a
  rerun), the report takes the script's and says so.
- D4. No CHANGELOG line, no version bump: users get nothing from this change.
- D5. Tracker tasks A and B are created only after the human's explicit "yes, create" for
  that list, asked by the developer once the report is written.
