# Research: CI before and after its speedup (LAD-252)

The question: did the CI speedup of 2026-11-09 (LAD-248, LAD-249, the GitHub Team plan,
LAD-236) bring a pull request's wait for CI to about 7-8.5 minutes at the median, and does
each part pay for itself. Both windows are measured by one script,
`docs/research/ci-speedup-check/measure.py`, with the definitions of the baseline (the
LADO session artifacts `ci-analysis` and `ci-external` of 2026-11-09). Openspec change:
`openspec/changes/ci-speedup-check/`.

1. [Summary](#1-summary)
2. [What changed in CI and when](#2-what-changed-in-ci-and-when)
3. [Before and after](#3-before-and-after)
4. [The four questions](#4-the-four-questions)
5. [Proposed tasks](#5-proposed-tasks)
6. [How the numbers were taken](#6-how-the-numbers-were-taken)

## 1. Summary

**The goal is reached: a pull request waits 8.0 minutes for a green CI at the median
(13.0 before), 10.5 at p90 (20.6 before).** The UI jobs no longer set the wait: the
macOS smoke does, in 69 % of green pull request runs, because its test step grew from
about 1.5 to about 7 minutes on 2026-11-08 with the new smoke tests (LAD-217, LAD-220,
LAD-230), independently of the speedup. A pull request that skips the smoke waits 6.7
minutes. The browser cache works (304 of 306 hits, step 20 s → 4 s, no tail), the Team
plan is needed (24 % of jobs start with 20 or more running; on Free those waited 160 s at
the median), reruns halved (6.7 % → 3.3 % of runs). The Docker layer cache does not pay:
it saves 14-16 s of a job that ends the run in 1.5 % of pull requests, and takes 7.0 GB,
which puts the repository's Actions cache at 11.06 GB, over its 10 GB.

Proposed (section 5, drafts until the human's "yes, create"): **A** remove the Docker
layer cache; **B** bring the smoke step back off the critical path; **C** a task for the
new flaky UI test `test_layout.py::test_the_session_list_and_session_windows_give_the_focus_back`.

## 2. What changed in CI and when

| When (UTC) | Change | Commit / PR |
|---|---|---|
| 2026-11-06 to 11-08 | New smoke tests: Claude Code and OpenCode/Kilo on fake model servers, refusals held to each CLI's repeats (LAD-217, LAD-220, LAD-230) | `d0b1f31a`, `ba156044`, `30a68301` and after |
| 2026-11-09 12:30 | LAD-248: time limit on every job; UI in four shards; `make dist` and the Node tests in a job `web`; Chromium and its system packages from a cache saved by `main`; container tests in two shards per architecture | PR #262 (`65d836cb`, `298ee7c0`, `c328f6f1`, `01922c18`) |
| 2026-11-09 | LAD-249: the image's layers from GitHub's cache (`type=gha`), written by `main` and the daily run only, from shard 1; the wheel in the image's last layer | `581b7689`, `4e8d8783` |
| 2026-11-09 | The organisation moved to GitHub Team (concurrent jobs 20 → 60; macOS stays 5 by GitHub's table) | settings, no commit |
| 2026-11-09 17:04 | LAD-236: the stop-as-typed integration test ends the session loop first | PR #265 (`aea2ae56`) |
| 2026-11-11 13:08 | LAD-246: the LoginSheet vitest waits for the login window's socket | PR #287 (`87a4d7bd`) |
| 2026-11-11 to 11-12 | Unit tests on Python 3.10 and 3.14 (was 3.13); every test cell keeps its junit report 90 days; `ci-rerun.yml` also restarts runs stuck in GitHub's queue (LAD-274) | `4814cf0c`, `3bbd1b70`, `8cd84886` |

Of the later changes, only the smoke tests move the wait (section 3, point 2). The unit
job on 3.14 ran in 5 runs of the window, too few to compare; junit uploads take about 2 s
per cell; `ci-rerun.yml` restarted no run in the window "after".

## 3. Before and after

Windows: **before** 2026-11-05 21:00 to 2026-11-09 12:30 UTC (the baseline's "last 3.4
days"), runs of the old job set (`ui (1)`, `ui (2)`, no `web`): 169 pull request, 38 push,
3 schedule runs; 11 runs left out (10 of the new job set, PR #262's branch, and 1 of
neither). **After**
2026-11-09 12:30 to 2026-11-13 00:00 UTC, runs of the new job set (`ui (1..4)` and `web`,
design D2): 78 pull request, 39 push, 3 schedule runs; 3 runs of neither job set left out. Commands (`--cache-dir` keeps GitHub's answers for a rerun):

```bash
python3 docs/research/ci-speedup-check/measure.py --since 2026-11-05T21:00Z --until 2026-11-09T12:30Z --job-set old
python3 docs/research/ci-speedup-check/measure.py --since 2026-11-09T12:30Z --until 2026-11-13T00:00Z --job-set new
python3 docs/research/ci-speedup-check/measure.py --caches    # run 2026-11-13 06:46 UTC
```

Every number below comes from these three outputs; n is the sample.

| # | Point | Before | After |
|---|---|---|---|
| 1 | Pull request's wait for a green first attempt, median / p90 (min) | **13.0 / 20.6** (n=108) | **8.0 / 10.5** (n=65) |
| 1 | ... smoke ran / smoke skipped | 12.7 / 20.6 (73); 13.2 / 19.6 (35) | 8.2 / 12.6 (46); 6.7 / 7.0 (19) |
| 1 | Push to main / daily run, median (min) | 12.7 (33) / 12.3 (3) | 8.2 (37) / 8.4 (3) |
| 2 | Job that ends a green pull request run | `ui (1)` 61 %, `ui (2)` 31 %, smoke 6.5 %, container 1.9 % (n=108) | macOS smoke 69 % (`claude` 34 %, `opencode` 29 %, `kilo` 6 %), UI 26 %, integration 3 %, container 1.5 % (n=65) |
| 2 | Job durations, median (min) | `ui` 9.4-11.1, container 7.5-8.2, integration 4.3-4.8, macOS smoke 2.2-3.1 | macOS smoke 4.8-7.5, `ui` 5.5-6.4, integration 5.3-6.0, container 4.3-5.5, unit 3.7-4.1, `web` 2.2 |
| 3 | Browser step: cache hits | none (no cache) | 304 of 306 pull request, 155 of 156 push restores |
| 3 | Browser step: apt downloads in its log | 419 of 444 jobs | 5 of 494 jobs |
| 3 | Browser step, median / p90 / max (s), pull requests | 20 / 329 / 749 (n=360) | 4 / 6 / 32 (n=328) |
| 3 | Browser step over 60 s / at 10 min | 54 of 444 / 10 | 0 / 0 |
| 4 | Step `Image`, pull request, median / p90 (s) | amd64 77 / 88 (166), arm64 66 / 72 (167) | amd64 63 / 92 (154), arm64 50 / 64 (154) |
| 4 | Step `Image`, push, median (s) | amd64 76, arm64 66 (39 each) | amd64 70, arm64 53 (78 each) |
| 4 | Layers `CACHED` in a pull request's build | 0 | 24 at the median; no pull request build without one (0 of 308) |
| 4 | Daily build from nothing (s) | amd64 72-91, arm64 61-67 (3 runs) | amd64 124-243, arm64 96-157 (3 runs, 2 cells each), all green |
| 5 | Linux queue, p50 / p90 (s); waited over 60 s | 2 / 148; 16.4 % (n=4356) | 2 / 4; 1.6 % (n=2952) |
| 5 | Linux queue when 10-19 / 20-29 jobs ran: p50 (s), waited over 60 s | 8, 30.8 % / **160, 70.6 %** | 2, 0 % / 2, 0 % |
| 5 | Linux queue when 40-59 jobs ran | 3 s, 0 % (13 jobs) | p50 3 s, p90 118 s, 20.2 % (198 jobs) |
| 5 | Jobs created with 20 or more running | 10.3 % | **23.8 %** (802 of 3365) |
| 5 | Peak of running jobs (all) / macOS | 60 / 13 | 76 / 9 |
| 5 | macOS queue, p50 / p90 (s); waited over 60 s | 3 / 223; 29.4 % (n=680) | 3 / 219; 18.6 % (n=413) |
| 6 | Actions cache | not measured then | **11.06 GB of 10 GB**, 398 entries: Docker layers 7.00 GB (345), setup-uv 2.92 GB (44), browser 0.91 GB (3), npm 0.24 GB (6); oldest last access 2026-11-10 |
| 6 | Misses in pull request runs | - | browser 2 of 306 (a new runner image's key before `main` saved it), Docker 0 of 308 |
| 7 | Jobs ended by a time limit | - (limits came with LAD-248) | 0 with a log saying so; 2 UI cells cancelled at 30.0 min with no log kept (LAD-271) |
| 7 | Jobs above 80 % of their limit | ui 7, integration 1, changes 1 (of today's limits) | ui 2 (the two above), all else 0 |
| 8 | Runs with more than one attempt | 14 of 210 (6.7 %): 10 flakes, 2 no runner, 2 still red | 4 of 120 (3.3 %): 2 flakes, 2 UI cells cancelled while running |
| 8 | Red first attempts (not superseded) | pull request 23, push 5 | pull request 5, push 2 |
| 8 | Known flakes of LAD-236, 246, 188, 245, 210 failed on a commit with their fix | - | 0 (LAD-236 and LAD-246 failed once each, on commits made before their fix) |

**"Before" against the baseline.** The baseline gives 12.8 / 20.4 min (n=106) for pull
requests and `ui (1)` 88 + `ui (2)` 43 of 141 runs as last jobs; the script gives 13.0 /
20.6 (n=108) and 99 of 108. The differences (0.2 min, a few runs) come from the window's
end (the baseline was cut when it was fetched on 2026-11-09, the script at 12:30), from
leaving out PR #262's runs, and from counting only pull requests in point 2. Job durations
and the step `Image` (76 / 66 s) agree to 0.1 min and 1 s. The browser p90 differs (329 s
against 171-438 s per shard) because the script pools both shards. The queue by load
agrees in kind (20-29 running: 160 s against 113 s median) but not exactly: the baseline
measured three weeks, the script 3.4 days.

**Flaky tests of the window "after"** (point 8, design D7; failed tests from the job logs):

| Test | Where | Open task |
|---|---|---|
| `tests/smoke/test_smoke.py::test_a_provider_s_refusal_ends_the_turn_within_the_cli_s_repeats[429-kilo]` | smoke macOS kilo, PR run 43007535491, passed on rerun | LAD-270 (Backlog) |
| `ui (1)`/`ui (2)` hung to 30 min, no log | PR runs 42890628200, 43005984528, passed on rerun | LAD-271 (Backlog) |
| `tests/ui/test_layout.py::test_the_session_list_and_session_windows_give_the_focus_back` | `ui (2)` of push run 42968074369 on `main`, not rerun; the next push was green | none: proposed task C |
| `web/src/LoginSheet.test.tsx` (LAD-246) | PR run 42848370463, a commit without the fix | closed task, fixed after |
| `test_human_messages.py::test_a_stop_as_the_message_is_typed...` (LAD-236) | push run 42620194203, 15 min before the fix's merge | closed task, fixed after |

## 4. The four questions

**Is the goal reached? Yes.** The median wait of a pull request is 8.0 minutes (target
7-8.5, from 13.0), p90 10.5 (from 20.6). The job on the critical path is now the macOS
smoke (`smoke macos-latest claude` and `opencode`, 7.3-7.5 min), not the UI (5.5-6.4
min). The smoke's test step on macOS grew from 82-88 s (2026-11-05 to 11-07) to 396-424 s
(from 2026-11-08) with the new smoke tests, so the speedup's own gain is larger than the
median shows: a pull request that skips the smoke (19 of 65) waits 6.7 minutes, p90 7.0.

**Does the Docker layer cache pay? No.** In a pull request it saves 14 s (amd64) and 16 s
(arm64) of the step `Image` at the median, and nothing at p90 on amd64 (92 s against 88):
a cached build still downloads the cached layers (about 1 GB, ~25 s in one push run's log) and
loads the image into Docker (~30 s there). A container cell ends the run in 1 of 65 green pull request runs, so
the wait gains about nothing. The cost: 7.0 GB of the repository's cache (63 % of what is
used), which puts it over the 10 GB limit, and the daily build from nothing that writes
the cache takes 96-243 s instead of 61-91 s. Without it, a container cell takes 15 s more
and stays below the UI and the smoke.

**Is the Team plan needed? Yes.** 23.8 % of jobs were created while 20 or more jobs ran
(design D6's threshold is 5 %). On Free (the window "before"), a Linux job created at
20-29 running waited 160 s at the median and 70.6 % waited over a minute; now 0 %
below 40 running. Going back to Free would bring that queue back for about a quarter of
the jobs, on top of the 8-minute wait. A queue remains above 40 running jobs (198 jobs,
p90 118 s), near the plan's 60. The macOS queue is GitHub's runner supply, which Team does
not change: p90 223 s before, 219 s after; the measured macOS peak (13 before, 9 after)
is above the 5 of GitHub's table, so the table's limit is not what binds there.

**Are 10 GB of cache enough? No, with the Docker cache; yes, without it.** On 2026-11-13
the repository holds 11.06 GB in 398 entries; GitHub evicts the least recently used
(the oldest last access is 2026-11-10). No run has missed a needed entry yet: the two
browser misses were a new runner image's key that `main` had not saved yet, and every
pull request build found Docker layers. Without the Docker layers the cache is about
4.1 GB (setup-uv 2.9, browser 0.9, npm 0.2).

## 5. Proposed tasks

Drafts; none is created without the human's "yes, create" (AC-6). Titles in Russian, as
the tracker's.

**A. «CI: убрать кэш слоёв Docker из контейнерных заданий»** (S). Return the step `Image`
to a plain `make docker` (no buildx, no `type=gha`), keep the wheel as the image's last
layer; update the comment in ci.yml, `docs/testing.md` and `tests/test_ci_workflow.py`.
Why: 14-16 s saved per container cell, 0 s on the wait (a container cell ends 1.5 % of
runs); 7.0 GB of 11.06 GB of the cache; the daily build 2× longer. Check: the cache under
10 GB a week later; the wait's median unchanged.

**B. «CI: смоук-тесты на macOS — вернуть их с критического пути»** (M). Find what in the
smoke's test step grew from ~90 s to ~400 s on 2026-11-08 (durations per test in the junit
reports or `--durations`), then speed it up or split the slow cases into a second cell per
provider, with the same tests on every pull request that needs the smoke. Why: the macOS
smoke ends 69 % of green pull request runs at 7.3-7.5 min; without it the wait is 6.7 min
at the median (19 runs), so up to ~1.5 min per run, ×4 runs per pull request.

**C. «Flaky UI-тест: test_layout.py — фокус не возвращается к списку сессий»** (S).
`tests/ui/test_layout.py::test_the_session_list_and_session_windows_give_the_focus_back`
failed in `ui (2)` of push run 42968074369 on `main` (2026-11-11), not rerun, the next
push green. Find the cause, fix the test or the code, no retries. Why: point 8, no open
task found.

Not proposed, as the numbers do not support them now: larger or third-party runners
(Linux queue p90 4 s; the critical path is macOS); skipping heavy jobs for documentation
pull requests (the wait is set by the smoke, already skipped for them); `--durations` and
cheaper UI tests (each cell keeps its junit report with durations since `3bbd1b70`, and
the test audit, `docs/research/test-audit.md`, covers the UI suite's size). The UI cell
hang is LAD-271 and the Kilo 429 flake LAD-270, both open. Integration cells grew by about
a minute (4.3-4.8 → 5.3-6.0 min) without reaching the critical path; not investigated.

## 6. How the numbers were taken

- Runs: every run of every workflow created in the window plus 3 hours before it (`gh api
  repos/ladohq/lado/actions/runs?created=<day>`), the jobs of all attempts (`.../runs/<id>/jobs?filter=all`),
  job logs (`.../actions/jobs/<id>/logs`), the cache list and usage
  (`.../actions/caches`, `.../actions/cache/usage`); only GET requests through `gh`.
- Wait = the last `completed_at` of a run's first-attempt jobs − the run's `created_at`,
  green first attempts only. Queue = a job's `started_at − created_at`; running jobs = jobs
  of every workflow started and not completed at the job's creation.
- A flake = a run whose first attempt failed a job and whose later attempt passed; no
  runner = a job cancelled with no step and no runner. Failed tests are read from the job
  log (pytest's `FAILED` lines, vitest's `FAIL`); the junit artifacts were not needed, as
  every failed job of the windows kept its log.
- Browser cache hit = the restore step logs `Cache restored from key: ui-browser-...`; an
  apt download = `apt-get update` or `Get:` lines in the step `Browser` (or, before, the
  `playwright install` step). Docker layer cache hit = `CACHED` layers in the step `Image`.
- Time limits: a log saying the job exceeded its time, or, as GitHub keeps no log of a job
  it cancelled, a cancelled job that ran its limit or longer.
- Known limits: the cache list is the state at the time of the run, not of the windows; the
  macOS limit's 5 comes from GitHub's documentation, not from a measurement.
