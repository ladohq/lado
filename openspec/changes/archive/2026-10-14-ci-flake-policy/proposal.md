Task: LAD-61

## Why

The research LAD-58 (`docs/research/merge-path.md`, R5 and R6) found two costs on the way
to a merge that the project's own settings can remove, without changing kit sdlc:

- A CI job that fails with no cause in the work (a timeout under load, a runner that fails
  at random) stops the agent that waits for CI: kit sdlc's rule "A red check" sends the
  supervisor the output and waits for its answer, and the run then goes on by a full rerun
  (~10 min) or none. After LAD-41 required jobs failed so four times in 63 runs, and the
  smoke of Codex on macOS 15 times in 214 jobs. Nobody owns such a flake unless the human
  happens to file it (LAD-57).
- In `merge`, after bringing `origin/main` into the branch, the integrator runs the
  settings' Checks locally, then pushes and waits for the pull request's CI, which runs
  the same checks and more. The local run costs 2-5 minutes per merge where `main` moved
  and holds the machine-wide test lock that other sessions' developers wait for.

## What Changes

All in `.lado/sdlc.md`, which wins over the kit's defaults (`sdlc-settings`, "Extra
instructions"):

- **Review traps**, a new entry (R5), the flake policy for CI: a CI job red with no cause
  in the work is rerun alone, `gh run rerun <id> --failed`, at most twice, by the agent
  that waits for CI (the developer in `build`, the reviewer in `review`, the integrator in
  `merge`) without asking the supervisor first; any job of CI, the smoke included. A pass
  on a rerun is a flake: its job, step and test go into the ledger (the developer's
  `build-report`, the integrator's note); the agent searches the tracker for an open task
  on that test, names it when there is one, and otherwise proposes a task to the human at
  once with `ask_human` (as LAD-57) and goes on without waiting; the task is created only
  on the human's "yes, create". The reviewer has no tracker: it leaves the search and the
  proposal to the supervisor with `send_message`. Red after the second rerun follows kit
  sdlc's "A red check". No automatic retry inside pytest.
- **Extra instructions**, Integrator, a new item (R6): after merging `origin/<target>` into
  the run's branch, the integrator runs none of the settings' Checks locally but
  `openspec validate --specs --strict`, then pushes and waits for the pull request's CI.
  A red CI follows the kit's step 3 as written, after the Review trap's reruns for a job
  red with no cause in the work: the merge commit stays, a cause in the work goes back to
  the developer, who fixes on top.

## Acceptance criteria

- AC-1: Review traps say that a CI job red with no cause in the work is rerun with `gh run
  rerun <id> --failed`, failed jobs only, at most twice, by the agent that waits for CI,
  without asking the supervisor first, for any job of CI, the smoke included.
- AC-2: A pass on a rerun is named a flake, and its job, step and test go into the ledger
  (the developer's `build-report`, the integrator's note).
- AC-3: For a flake the agent searches the tracker for an open task on that test and names
  it; without one it proposes a task with `ask_human` at once, goes on without waiting, and
  creates it only on the human's "yes, create". The reviewer, which has no tracker, leaves
  the search and the proposal to the supervisor with `send_message`.
- AC-4: The entry forbids an automatic retry inside pytest and sends a job still red after
  the second rerun to kit sdlc's "A red check".
- AC-5: Extra instructions, Integrator, say that after merging `origin/<target>` the
  integrator runs no local Check but `openspec validate --specs --strict`, then pushes and
  waits for the pull request's CI.
- AC-6: The same item keeps the kit's rule for a red CI: the merge commit stays and a cause
  in the work goes back to the developer as `conflicts`, after the Review trap's reruns for
  a job red with no cause in the work.
- AC-7: No other part of `.lado/sdlc.md` changes ("What CI proves" in particular), and no
  file outside `.lado/sdlc.md` and this change.

## Scope

- The two items above in `.lado/sdlc.md`; nothing else in that file changes.
- The existing Review trap about local timeout failures ("A timeout failure under machine
  load") stays: it is about a local rerun of one test, this one about CI jobs.

## Out of scope

- Kit sdlc (its integrator step, "A red check", `review-loop`): the research's decision;
  `.lado/sdlc.md` overrides it for this project only.
- `.lado/sdlc.md` "What CI proves", `.github/workflows/ci.yml`, AGENTS.md and
  `tests/test_ci_workflow.py`: the parallel run LAD-60 changes them; touching them here
  would make the two pull requests conflict.
- An automatic retry in pytest (`pytest-rerunfailures`, `--reruns`): LADO's timing
  failures have been real races (LAD-44), and a retry would hide the next one.
- A guard test that no automatic retry is configured: nothing configures one, and a test
  for a rule of a process document is a second source of truth ("Only what is used").
- Rerunning a whole CI run, or more than twice: a whole rerun repeats every green job
  (~10 min instead of ~5); a third pass hides a race that fails two times in three.
- Behaviour rules of LADO: none change, so the change has no delta spec and is archived
  with `--skip-specs`.

## Impact

- `.lado/sdlc.md` only. No code, no tests, no schema: no version bump and no CHANGELOG
  line (nothing users of LADO see).
- Agents of kit sdlc on this project read the new rules at their next step.
