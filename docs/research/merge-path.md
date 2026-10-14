# Research: the way to a merge into main (LAD-58)

The question: where does the time go between a task's start and its merge into `main`
(CI, reviews, the human's answers, bringing `main` in), what do other projects do about
it, and what should LADO change, with each change's gain and risk. Measured on LADO's own
history, 11-14 October 2026 (UTC), with `docs/research/merge-path/measure.py`. The human
chose the recommendations at the design gate; implementing them is tasks A and B
(section 6). Openspec change: `openspec/changes/merge-path-research/`.

1. [Summary](#1-summary)
2. [How we merge today](#2-how-we-merge-today)
3. [Measurements](#3-measurements)
4. [What others do](#4-what-others-do)
5. [Recommendations](#5-recommendations)
6. [Proposed tasks](#6-proposed-tasks)

## 1. Summary

**Half of a task's time is the human's answer at `merge_ok` (49%), kept on purpose; of
the rest, CI is the one cost worth cutting, and it is set by one step.** Since LAD-41 a
CI run takes 9.7 minutes in the median (4.0 before): the integration tests in one process
(`-n0`) take 6 of them, on each Python version. A task waits for CI two to three times
(the developer's push, review fixes, the integrator's push after bringing `main` in), and
again for each flaky rerun. Reviews (about 1 minute per external round), caches (every
setup step under 5 s) and runner queues (0.0-0.1 min on Linux) cost little.

Taken (the human's decision): **R1** shard the integration tests (3 jobs per Python) and
the UI tests (2 jobs), CI ~9.7 → ~4-5 min, 10-15 min less per task; **R2** one required
check `ci-ok` (taken in part: heavy jobs are not skipped for research-only pull requests);
**R3** no smoke for a pull request that changes only the web UI, its tests or
documentation (13 of 38), and a daily smoke on `main`; **R4** cancel a pull
request's superseded runs; **R5** a flake policy in `.lado/sdlc.md`; **R6** the
integrator relies on the pull request's CI instead of running the checks locally. Not
taken: **R7** a merge queue, **R8** more caching, sharded unit tests, a lower review
round cap. The gate `merge_ok` stays.

## 2. How we merge today

**CI** (`.github/workflows/ci.yml`, workflow `CI`) runs on every pull request and every
push to `main`, 12 jobs at once:

| Job | Runner | What it runs |
|---|---|---|
| `check (3.10)`, `check (3.13)` | ubuntu-latest | `ruff format --check`, `ruff check`, unit tests (`-n auto`), integration tests (`-m integration -n0`) |
| `js` | ubuntu-latest | `node --test tests/js/*.test.mjs` |
| `ui` | ubuntu-latest | `make dist` (web UI built, sdist and wheel), Playwright's Chromium, UI tests (`-m ui -n 2`) |
| `smoke <os> <provider>` (8) | ubuntu-latest, macos-latest | each provider's real CLI against a local endpoint (`scripts/smoke_ci.py run`) |

**The ruleset of `main`** requires `check (3.10)`, `check (3.13)`, `js` and `ui`. The
smoke is not required, but its red shows on the pull request and on `main`. There is no
"branch must be up to date" requirement: the integrator brings `main` in itself.

**Kit sdlc's flow `task`** (v0.5.0): `design` → gate `design_ok` → `build` → `review` →
gate `merge_ok` → `merge` → `done`. CI is waited for in three places:

- `build`: the developer pushes; the reviewer's stop criterion needs a green CI ("no
  findings over a red pipeline is not mergeable").
- `review`: each round of fixes is a push and a new CI run.
- `merge`: the integrator archives the openspec change and pushes (one run), merges
  `origin/main` into the branch, runs the settings' Checks locally when `main` brought
  changes, pushes again (another run), waits for the pull request's CI (ceiling 40
  minutes), then merges with a merge commit.

What CI proves today (`.lado/sdlc.md`, "What CI proves"): a green CI is the full `make
check` plus the smoke. docs/release.md asks for a green CI with the smoke on the release
commit on `main`.

## 3. Measurements

Every table below is printed by one command, run on 14 October 2026 against a copy of
this machine's `lado.db`:

```bash
python3 docs/research/merge-path/measure.py --since 2026-10-11 --until 2026-10-14T17:00:00Z \
    --split 2026-10-13T16:00:00Z --db <a copy of lado.db>
```

Window: 2026-10-11 00:00 to 2026-10-14 17:00 UTC. The split, 2026-10-13 16:00 UTC, is
LAD-41's merge (integration tests from `-n auto` to `-n0`, UI tests to `-n 2`). Sources:
GitHub's Actions API (runs of `ci.yml` and `claude.yml`, each attempt's jobs with their
steps), `gh pr list` and each pull request's files, and the events `flow_start`, `flow`
and `flow_end` of the flow runs `task/lad-*` in `lado.db`.

**Where the numbers differ from the design** (decision D3: the report takes the
script's). The design's window ended earlier on 14 October, so the script counts a few
more runs: 159 CI runs (design 156), 63 after the split (60), median 9.7 min (9.6). The
design's "36 runs had more than one attempt, 19 of them LAD-44's" is 29 runs with 55
reruns, 19 of those reruns in one run of LAD-44. The median of CI runs per pull request
is 2.5 (design 3): a run after the window's end is not counted. Pull requests that change
only R2's docs-only paths: 1 of 38 (design: 5 of 38); the documentation pull requests
the design also counted (#3, #4, #7, #28) change CHANGELOG.md, which the release tests
read, README.md, which `make dist` packs, or code. This is why R2's skip of heavy jobs
was then not taken (section 5). The flow table is the design's to the minute.

### 3.1 CI wall time

First attempt of each run: from the run's creation to its last job's end. Cancelled runs
are left out.

| Period | Runs | Median, min | p90, min |
|---|---|---|---|
| before 2026-10-13 16:00 UTC | 96 | 4.0 | 5.0 |
| from 2026-10-13 16:00 UTC | 63 | 9.7 | 12.5 |

### 3.2 Jobs and steps after LAD-41

Successful jobs, from start to end; queue is from the job's creation to its start.

| Job | Jobs | Median, min | p90, min | Queue median, min | Queue p90, min |
|---|---|---|---|---|---|
| check (3.10) | 82 | 7.8 | 10.1 | 0.0 | 0.1 |
| check (3.13) | 81 | 7.9 | 9.3 | 0.0 | 0.1 |
| js | 85 | 0.1 | 0.2 | 0.0 | 0.1 |
| ui | 83 | 5.3 | 5.6 | 0.0 | 0.1 |
| smoke macos-latest claude | 84 | 1.4 | 1.7 | 0.1 | 3.9 |
| smoke macos-latest codex | 81 | 1.4 | 1.7 | 0.1 | 3.4 |
| smoke macos-latest kilo | 84 | 1.7 | 2.0 | 0.1 | 4.8 |
| smoke macos-latest opencode | 83 | 1.8 | 2.0 | 0.1 | 3.4 |
| smoke ubuntu-latest claude | 85 | 0.6 | 0.8 | 0.0 | 0.1 |
| smoke ubuntu-latest codex | 85 | 0.7 | 0.8 | 0.0 | 0.1 |
| smoke ubuntu-latest kilo | 85 | 0.8 | 1.0 | 0.0 | 0.1 |
| smoke ubuntu-latest opencode | 85 | 0.9 | 1.1 | 0.0 | 0.1 |

Steps of those jobs with a median of at least 10 s, in seconds:

| Job | Step | Samples | Median | Max |
|---|---|---|---|---|
| check (3.10) | `uv run pytest -m integration -n0` | 82 | 360 | 525 |
| check (3.10) | `uv run pytest -n auto` | 82 | 108 | 196 |
| check (3.13) | `uv run pytest -m integration -n0` | 81 | 364 | 449 |
| check (3.13) | `uv run pytest -n auto` | 81 | 97 | 241 |
| ui | `uv run pytest -m ui -n 2` | 83 | 210 | 224 |
| ui | `make dist` | 83 | 67 | 120 |
| ui | `uv run playwright install --with-deps chromium` | 83 | 21 | 43 |
| smoke macos-latest | Smoke test | 332 | 64 | 118 |
| smoke ubuntu-latest | Smoke test | 340 | 27 | 63 |

Every other step (checkout, setup-uv, `uv sync`, tmux, setup-node, ruff) is under 10 s:
the caches work. The critical path is `check`: its integration step alone is 6 minutes,
and the unit step runs before it in the same job.

### 3.3 Failures and reruns

159 runs, 29 with more than one attempt, 55 reruns in all (19 of them LAD-44's stress
reruns of one run). Failed jobs over all attempts (214 of each job ran):

| Job | Failed | Of them from the split | Failing step (count) |
|---|---|---|---|
| check (3.10) | 25 | 2 | integration `-n auto` (16); unit `-n auto` (8); integration `-n0` (1) |
| ui | 20 | 2 | UI `-n auto` (9); `make dist` (8); UI `-n 2` (3) |
| smoke macos-latest codex | 15 | 4 | Smoke test (15) |
| check (3.13) | 12 | 2 | unit `-n auto` (5); integration `-n auto` (5); integration `-n0` (2) |
| smoke ubuntu-latest codex | 1 | 0 | Smoke test (1) |
| smoke macos-latest opencode | 1 | 1 | Smoke test (1) |

Each failed job after the split:

| Run created (UTC) | Run | Event | Job | Step | Green on rerun |
|---|---|---|---|---|---|
| 10-13 17:21 | merge of #20 (LAD-43) | push | smoke macos-latest codex | Smoke test | no rerun |
| 10-13 17:37 | Bump typescript to 7.0.2 | pull_request | ui | `make dist` | no rerun |
| 10-13 17:38 | Bump @types/node to 26.6.4 | pull_request | ui | UI `-n 2` | no rerun |
| 10-13 19:30 | LAD-48's pull request (#27) | pull_request | smoke macos-latest codex | Smoke test | yes |
| 10-13 20:21 | merge of #28 (release doc) | push | check (3.13) | integration `-n0` | no rerun |
| 10-13 20:21 | merge of #28 (release doc) | push | smoke macos-latest opencode | Smoke test | no rerun |
| 10-13 20:21 | merge of #28 (release doc) | push | smoke macos-latest codex | Smoke test | no rerun |
| 10-13 20:24 | Bump actions/setup-node to 7.1.0 | pull_request | check (3.13) | integration `-n0` | no rerun |
| 10-13 20:51 | LAD-42's pull request (#29) | pull_request | check (3.10) | unit `-n auto` | no rerun |
| 10-13 21:15 | merge of #29 (LAD-42) | push | smoke macos-latest codex | Smoke test | no rerun |
| 10-14 16:12 | Release 0.38.0 (#38) | pull_request | check (3.10) | integration `-n0` | yes (LAD-57) |

Before LAD-41, most failures were timeouts of the integration and UI tests under `-n
auto`, which LAD-41 traded for the longer `-n0`. After it, required jobs failed four
times in 63 runs with no cause in the work (integration 3.13 twice, unit 3.10 once,
integration 3.10 on the release, LAD-57); the two `ui` failures are on Dependabot's
upgrades (TypeScript 7 is not merged). The smoke of Codex on macOS is the most frequent
red: 15 of 214 jobs, not required, but red on pull requests and on `main`. Pushes to
`main`: 52 runs, 13 not green, 3 of them after the split.

### 3.4 Pull requests

38 pull requests opened in the window (#1-#38, Dependabot's six and the two releases
included). CI runs per pull request: median 2.5, max 7 (LAD-52's documents). Opening to
merge, the 32 merged ones not by a bot: median 34 min; the 28 that name a LAD task:
median 35 min. Dependabot's wait about a day for the human. The tasks LAD-58 names:

| Task | PR | CI runs | Reruns | Open to merge, min |
|---|---|---|---|---|
| LAD-33 | #34 | 2 | 0 | 95 |
| LAD-34 | #35 | 3 | 0 | 128 |
| LAD-42 | #29 | 3 | 0 | 24 |
| LAD-44 | #30 | 3 | 19 | 515 (overnight, stress reruns) |
| LAD-52 | #33 | 7 | 0 | 539 |
| LAD-53 | #36 | 3 | 0 | 30 |

The pull request opens in `build`, so this is review, `merge_ok` and merge. Only #33
changes nothing but R2's docs-only paths (research report, openspec, review report). 13
of the 38 (#3, #4, #7, #9, #16, #20, #23-#27, #29, #33) change nothing but R3's paths the
smoke cannot concern (`web/`, `docs/`, `openspec/`, `tests/ui/`, `tests/js/`, the top-level
Markdown files, `.github/dependabot.yml`): the web UI, its tests and documentation.

### 3.5 Reviews

The external reviewer (`claude.yml`, `@claude review`): 33 runs not skipped, all
successful, median 1.0 min, p90 1.4 min; about one round per pull request of a task.

### 3.6 Time per flow state

The 10 ended runs of `task/lad-*` that started in the window, minutes from entering a
state to leaving it (a state visited twice counts both visits):

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

A task's total: median 161 min. `merge` (6-46 min, median 13) is the archive push, the
merge of `main`, the local checks when `main` moved, a second push and its CI run: one or
two CI waits. `build` holds the developer's work and its first CI; `review` its rounds.

## 4. What others do

**Merge queues and the "not rocket science" rule.** Keep `main` always green by testing
each change on top of the exact `main` it lands on, and merging only what passed
([Graydon Hoare, "The Not Rocket Science Rule"](https://graydon2.dreamwidth.org/1597.html);
[bors](https://bors.tech/), Rust's homu). Hosted forms: [GitHub's merge
queue](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/managing-a-merge-queue)
(a `merge_group` CI run per entry, batching) and [GitLab's merge
trains](https://docs.gitlab.com/ci/pipelines/merge_trains/). They pay off when many
changes land on a busy `main` and each would otherwise rebase and rerun. **For LADO:**
not now. Tasks merge mostly one at a time; the integrator already brings `main` in and
waits for CI, which is the same guarantee for a queue of one. A queue would add a run per
merge and change the integrator's routine (R7).

**Path filters and one aggregate required check.** Run a job only when the files it
covers change ([`on.<event>.paths`](https://docs.github.com/en/actions/writing-workflows/workflow-syntax-for-github-actions),
or a job-level filter such as [dorny/paths-filter](https://github.com/dorny/paths-filter)).
A required check that a path filter skips leaves the pull request waiting ([GitHub,
"Handling skipped but required
checks"](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/collaborating-on-repositories-with-code-quality-features/troubleshooting-required-status-checks)),
so projects require one final job that needs all others and decides
([re-actors/alls-green](https://github.com/re-actors/alls-green) is a published action
for exactly that). **For LADO:** the aggregate check yes (R2); a path filter only for the
smoke (R3), written as the paths it skips for (any other change runs it, so a new file
is covered by default) and guarded by a test, since a list of paths drifts from what the
code and tests read. Skipping the required jobs for documents is not worth it here (R2).

**Fast required checks, slow ones after the merge or nightly.** Large projects keep the
pull request's checks short and run the slow or platform-wide ones on the merged branch
and on a [schedule](https://docs.github.com/en/actions/writing-workflows/choosing-when-your-workflow-runs/events-that-trigger-workflows)
(Kubernetes' periodic jobs, Chromium's post-submit bots). The price: a break is seen
after the merge and someone must own the red. **For LADO:** a daily smoke on `main`
besides each pull request that can concern it (R3); the unit, integration and UI tests
stay required on every pull request ("Tested end to end").

**Caching.** Dependency and tool caches ([GitHub's
cache](https://docs.github.com/en/actions/writing-workflows/choosing-what-your-workflow-does/caching-dependencies-to-speed-up-workflows),
[setup-uv's cache](https://docs.astral.sh/uv/guides/integration/github/)). **For LADO:**
done already: every setup step is under 5 s (3.2). Nothing to win (R8).

**Test sharding.** Split a slow suite over parallel jobs by file or by recorded duration
([pytest-split](https://github.com/jerry-git/pytest-split), [Playwright's
`--shard`](https://playwright.dev/docs/test-sharding)). **For LADO:** yes for the
integration and UI tests (R1). They cannot run more workers on one runner (LAD-41: four
at once starve each other past LADO's short timers), but more runners each with `-n0` or
`-n 2` keep that condition. The unit tests (under 2 min) are not worth it (R8).

**Cancelling superseded runs.** A [`concurrency`
group](https://docs.github.com/en/actions/writing-workflows/choosing-what-your-workflow-does/control-the-concurrency-of-workflows-and-jobs)
per pull request with `cancel-in-progress`, never on the default branch, so each `main`
commit keeps its verdict. **For LADO:** yes (R4); it matters most in `merge`, where the
archive push is followed within minutes by the push of the merge with `main`.

**Flake policies.** Google reruns a failing test and quarantines flaky ones, with an
owner to fix them ([Flaky Tests at Google and How We Mitigate
Them](https://testing.googleblog.com/2016/05/flaky-tests-at-google-and-how-we.html));
Kubernetes files an issue per flake and expects the owner to fix or skip it ([Flaky
tests](https://github.com/kubernetes/community/blob/master/contributors/devel/sig-testing/flaky-tests.md)).
Tools: automatic retry ([pytest-rerunfailures](https://github.com/pytest-dev/pytest-rerunfailures)),
or rerunning only a run's failed jobs ([GitHub, re-running failed
jobs](https://docs.github.com/en/actions/managing-workflow-runs-and-deployments/managing-workflow-runs/re-running-workflows-and-jobs)).
**For LADO:** a rerun of the failed jobs only, at most twice, and each flake a tracker
task proposed to the human (R5). No automatic retry in pytest: LADO's timing failures
have been real races (LAD-44), and a retry would hide the next one.

**Caps on review rounds.** Google's review guide favours fast, small rounds over a fixed
number ([Speed of Code
Reviews](https://google.github.io/eng-practices/review/reviewer/speed.html)); kit sdlc
caps external rounds already (2 for a full change, 1 for a tweak). **For LADO:** nothing
to change: a round costs about a minute of the reviewer and there is about one per pull
request (3.5, R8).

**"Branch must be up to date".** GitHub can require the branch to contain the latest
`main` before a merge ([About protected
branches](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches)),
which costs a CI run each time `main` moves. **For LADO:** not needed: the integrator
merges `main` in and waits for that CI before every merge, which is the same check.

## 5. Recommendations

Gains are measured against section 3: a CI run of 9.7 min, two to three CI waits per task,
a task of 161 min in the median, of which the human's two gates are 52%.

### R1. Shard the integration and UI tests — taken

What: split `check` into a lint and unit job per Python, and the integration tests into
3 jobs per Python, each `-n0`, by a stable split of the test files (by file name, so a
new file lands in a known shard); split the UI tests into 2 jobs (`-n 2` each), `make
dist` only in the first (the second builds the web UI it needs).

Gain: the integration step 6 min → ~2 min plus ~1 min setup per shard; the UI job 5.3 →
~3.5 min. CI wall ~9.7 → ~4-5 min; with two to three CI waits per task, 10-15 min less
per task (6-9% of the median task), and the integrator's `merge` (median 13 min) about 5
min shorter.

Risk: low. More jobs (12 → 19), all on Linux runners, which queued 0.0-0.1 min. A file
split leaves one shard slower when a heavy file lands there; the split is checked against
the measured job times once it runs.

Rules it changes, named: the ruleset of `main` (the required names, unless R2 lands
first); AGENTS.md "Commands" (CI runs the integration tests in one process; "on two
workers" for the UI tests becomes "two jobs of two workers") and "Testing"; the pinned
commands in `tests/test_ci_workflow.py`. `make check` and the local commands are
unchanged.

### R2. One required check `ci-ok` — taken in part

What was proposed: a last job `ci-ok` that needs every other job and fails unless each
succeeded or was skipped on purpose, the only check the ruleset of `main` requires; and,
on a pull request whose every changed file is under a path no test reads
(`docs/research/`, `docs/superpowers/`, `openspec/`, `BACKLOG.md`, `ROADMAP.md`), the
jobs `check`, `ui` and `smoke` skipped, with `ci-ok` saying why.

Taken: the aggregate check `ci-ok`. Gain: the ruleset stops naming jobs, so R1 and later
changes reshape jobs without touching it. Risk: low; a `ci-ok` that passed over a failed
job would be silent, so the job checks each needed result explicitly ("No silent
drops"); the only job it may see skipped is the smoke under R3's filter.

Not taken (the human's decision after the measurement): the skip for research-only pull
requests. Its gain is small: a research pull request's CI ~1 min instead of ~10, but in
the window that was 1 pull request of 38 (#33, LAD-52's seven runs), not 5 as the design
estimated; CHANGELOG.md, docs/release.md and docs/telemetry.md are read by tests and
README.md is packed by `make dist`, so documentation for users never fits the list. Its
risk is medium: a wrong path on the list lets untested code into `main`, and the list
needs a guard test that keeps up with every file the code and tests read.

Rules it changes, named: the ruleset of `main` (required: `ci-ok` only, set once the job
is green on `main`); `tests/test_ci_workflow.py` (`ci-ok` needs every other job).
`.lado/sdlc.md` "What CI proves" is unchanged by R2: every pull request still runs the
full suite.

### R3. No smoke for pull requests it cannot concern, a daily smoke on `main` — taken

What: the smoke jobs run on every push to `main`, on a daily schedule, on manual
dispatch, and on every pull request except one whose every changed file is under a path
the smoke cannot concern: `web/`, `docs/`, `openspec/`, `tests/ui/`, `tests/js/`,
`README.md`, `CHANGELOG.md`, `AGENTS.md`, `BACKLOG.md`, `ROADMAP.md`, `SECURITY.md`,
`.github/dependabot.yml`. The list names what the smoke skips for, not what it runs for:
the smoke imports most of LADO (`tests/smoke/test_smoke.py`: `loop`, `runtime`, `state`,
`tmux`, the providers; through them `interpreter`, `cli`, `mcp_exec`, `gui_session`,
`hooks`, the built-in kits) and runs on the locked dependencies (`pyproject.toml`,
`uv.lock`), so a list of what it runs for would miss a file, and a new file runs it by
default.

Guard: a test in `tests/test_ci_workflow.py` that the list in `ci.yml` is exactly the
one the test holds, and that no listed path is or contains `src/`, `scripts/`,
`tests/` (but `tests/ui/` and `tests/js/`), `pyproject.toml`, `uv.lock` or
`.github/workflows/`: what the smoke runs. It holds because LADO at run time reads its
own package (`src/lado/`) and the agents' repositories, never its checkout's `docs/` or
`web/` sources (the code names `docs/...` and `BACKLOG.md` only in comments; the smoke
runs from `uv sync`, without the built web UI). Adding a path to the list is a change of
that test, seen in review.

Gain: in the window 13 pull requests of 38 (the web UI's, its tests' and documentation)
would not have run it: four fewer macOS runners each (their queue p90 3.4-4.8 min) and no
red from Codex on macOS (15 of 214 failed) on a change that cannot cause it; #27 had one.

Risk: low. Every pull request that changes LADO's code, its tests (but the UI's and the
Node ones), its scripts, dependencies or workflows still runs the smoke, on Linux and on
macOS, before the merge: CI's only check on macOS stays on every change that can break
it there. A web UI change, which the smoke never ran in the browser, loses nothing.
What is lost: a pull request on the list gets no smoke until `main`, and a wrong path on
the list would skip it for a change it concerns, which the guard test catches. The
release keeps its rule: the release commit is a push to `main`, so it gets the smoke
(docs/release.md, section 2, unchanged).

Rules it changes, named: AGENTS.md "Commands" (CI's job `smoke` "on Linux and macOS"
becomes "on `main`, daily and on pull requests that change more than the web UI, its
tests and documentation") and "Testing" (layer 5, "in CI on Linux and macOS"); the
docstring of `tests/test_ci_workflow.py` ("on each pull request and push to main");
`.lado/sdlc.md` "What CI proves" ("A green CI is the full `make check` plus the smoke",
but for a pull request on the list).

### R4. Cancel a pull request's superseded runs — taken

What: `concurrency: {group: ci-${{ github.event.pull_request.number || github.sha }},
cancel-in-progress: ${{ github.event_name == 'pull_request' }}}`: a new push to a pull
request cancels its older run; `main` never cancels.

Gain: small: runners freed when fixes come quickly, and the archive push's run in
`merge` no longer runs beside the merge push's run.

Risk: none known; a cancelled run is not a red one (`ci-ok` of the newer run decides).

Rules it changes: none; `tests/test_ci_workflow.py` gains a check that `main` is never
cancelled.

### R5. A flake policy — taken

What, in `.lado/sdlc.md` (Review traps): a required job red with no cause in the work is
rerun alone (`gh run rerun <id> --failed`), at most twice; a pass on rerun is a flake,
named in the ledger with its job, step and test, and proposed to the human as a tracker
task (as LAD-57); no automatic retry inside pytest.

Gain: ~5 min per flake (the green jobs do not run again; a full rerun is ~10 min), and
each flake gets an owner instead of a silent rerun.

Risk: low: a real race that passes twice in a row is still filed, not hidden.

Rules it changes, named: `.lado/sdlc.md` Review traps (the existing timeout trap is about
local reruns; this one is about CI); nothing in AGENTS.md.

### R6. The integrator relies on the pull request's CI — taken

What: after merging `origin/main` into the branch, the integrator does not run the
settings' Checks locally; it pushes and waits for the pull request's CI, as it does
anyway. A red CI caused by the work follows the existing rule (the merge commit stays,
the developer fixes on top). Set in `.lado/sdlc.md`'s Extra instructions for the
integrator, which win over the kit's step; kit sdlc itself unchanged.

Gain: 2-5 min per merge where `main` moved, and the machine-wide test lock stays free for
other sessions' developers.

Risk: low: a conflict that merges cleanly but breaks is caught by the same CI one step
later; the cost is a CI run instead of a local check.

Rules it changes, named: `.lado/sdlc.md` Extra instructions, Integrator; kit sdlc's
integrator step 2 is overridden for this project only.

### R7. A merge queue — not taken

Why not: tasks merge mostly one at a time and `main` seldom moves under a pull request;
the integrator's merge of `main` and its CI wait already give the queue's guarantee. A
queue would add a `merge_group` run per merge and change the integrator's routine.
Revisit when parallel sessions merging into `main` within the same hour are usual.

### R8. More caching, sharded unit tests, a lower round cap — not taken

Why not: setup steps take seconds (3.2); the unit tests take under 2 min and run beside
the integration shards once R1 lands; an external round takes about a minute and there is
about one per pull request (3.5). No time is lost there.

## 6. Proposed tasks

In the order to build them. The human said "yes, create" for this list, with R2's skip
of heavy jobs taken out of A; each is a tracker task with the label `component lado`,
derived from LAD-58.

**A (LAD-60). «CI: параллельные шарды тестов, одна обязательная проверка ci-ok, smoke по
путям»** (size M). R1, R2's aggregate check only, R3, R4: `ci.yml`,
`tests/test_ci_workflow.py` (the shards, `ci-ok` and the jobs it needs, R3's list of paths
the smoke skips for and its guard, the concurrency rule), AGENTS.md (Commands, Testing),
`.lado/sdlc.md` ("What CI proves"). The ruleset of `main` is changed by the human (or
with their yes) to require `ci-ok` once the job is green on `main`. Depends on nothing.
Measured again with `measure.py` after a week of runs.

**B (LAD-61). «sdlc.md: политика флейков и слияние без локальных проверок»** (size S).
R5, R6 in `.lado/sdlc.md` (Review traps; Extra instructions for the integrator). Independent of A;
after A the CI wait it relies on is shorter.
