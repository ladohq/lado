## 1. Flake policy (R5)

- [x] 1.1 In `.lado/sdlc.md`, **Review traps**, add after the entry "A timeout failure
  under machine load" this entry (AC-1-AC-4):

  ```markdown
  - A CI job red with no cause in the work (a timeout, a runner or service that fails at
    random) — `gh run view <id>` names the failed job, step and test, and nothing in the
    diff or the target branch it meets explains it — the agent that waits for CI (the
    developer in `build`, the reviewer in `review`, the integrator in `merge`) reruns the
    failed jobs alone, `gh run rerun <id> --failed`, at most twice, without asking the
    supervisor first; any job of CI, the smoke included; never the whole run, never an
    automatic retry inside pytest. A pass on a rerun is a flake: name its job, step and
    test in the ledger (the developer in `build-report`, the integrator in its note);
    search the tracker for an open task on that test and name it when there is one,
    otherwise propose a task to the human at once with `ask_human` (as LAD-57), go on
    without waiting, and create it only on their "yes, create". Red after the second
    rerun follows kit sdlc's "A red check".
  ```

  Check: by reading against AC-1-AC-4; "What CI proves" and every other section of the
  file unchanged (`git diff origin/main -- .lado/sdlc.md` shows only additions in Review
  traps and Extra instructions).

## 2. Integrator's merge (R6)

- [x] 2.1 In `.lado/sdlc.md`, **Extra instructions**, Integrator, add after the item
  "Never bump the version" this item (AC-5, AC-6):

  ```markdown
  - After merging `origin/<target>` into the run's branch (the kit's Merge, step 2), run
    none of the settings' **Checks** locally but `openspec validate --specs --strict`
    (CI does not run it); with it green, push and wait for the pull request's CI, which
    runs the rest. A red CI then follows step 3 as written: the merge commit stays, and
    a cause in the work is `conflicts`, fixed by the developer on top. This replaces
    step 2's local run of the Checks on this project.
  ```

  Check: by reading against AC-5, AC-6.

## 3. Close

- [x] 3.1 (AC-7) `openspec validate ci-flake-policy --strict`, `openspec validate --specs
  --strict` and `make lint` pass; no other file than `.lado/sdlc.md` and this change
  changed (`git diff origin/main --stat`).
