Task: LAD-219

## Why

Symptom: `web/src/Launch.test.tsx` > "Start in starts in the project's repository chosen"
fails with `AssertionError: expected true to be false` at line 2599, the wait for Start in to
come on. Seen in CI on PR #230 (run 42267569487, attempt 1, job `ui (1)`, step `make dist`), a
pull request that did not touch the window or the test; the rerun of the failed job passed.

Cause, reproduced on 2026-11-06: the test picks a provider before the window has the list of
providers; the product is right. While the human's choice of a repository is asked, the window
has no answer about the project, so it forgets the list of providers, which it asks per project
(`loginsOf` in `web/src/Launch.tsx`). When the first list had not come before the click, the
second one is asked only once the answer about the repository is in, which is what the test
has just waited for (the name `shop-frontend`). The field Provider is then off and holds only
"checking…". `fireEvent.change` reaches it all the same: the option `claude` is not there, so
the select's value is the empty string, and `chooseProvider("")` records it as the human's
choice. The list comes, nothing suggests a provider any more, and Start in stays off for good.
No human can do this, since a disabled field takes no choice. The other `fireEvent.change` of
the field in this file come after a wait for it.

A throwaway copy of the test with `/api/providers` answered 150 ms late, three runs:

    wait of 1 s for Start in        failed, as in CI (1176 ms)
    wait of 15 s for Start in       failed the same way (15075 ms)
    a wait for the field, then 1 s  passed

The field after both failures: value `""`, on, options `· unknown`, `claude · …`, `kilo · …`.

CI's page dump is cut off before the window, so the field's state in that very failure is not
known; the test line and the error are the same.

So this flake is not a case of BACKLOG.md's "Vitest tests time out at vitest's default 5 s
under load": no timeout cures it. That entry is real on its own, though: `web/vite.config.ts`
keeps vitest's 5 s for a test, and nothing changes Testing Library's 1 s for `waitFor` and
`findBy`, which failed tests at load averages from 8 to 238. The human chose to fix it here too
(question #4305): it is what the task asked to check, and it is two lines.

Options weighed for the test:

- A (taken): wait for the field to come on before the choice, as `ready` and the other tests
  do. Long-term cost: none; one line, in a part of the file the epic has not changed.
- B: a helper that picks a provider and waits for the field, used at every such line. It would
  make the mistake harder to repeat, but only this line lacks the wait, and the helper would
  change lines `epic/lad-154-models` rewrote around, for conflicts at its merge.
- C: raise the timeouts only. It does not cure this failure (the 15 s run above).
- D: keep the list of providers in the window while a repository is asked. The field would
  stop going to "checking…" at each choice and the race would go, but it changes the product
  for a test, and the reason to ask per project is that a project's secrets may log a CLI in.

Options weighed for the waits:

- A (taken): `testTimeout` of 30 s in `web/vite.config.ts` and `asyncUtilTimeout` of 10 s through
  Testing Library's `configure` in `web/src/testSetup.ts`, one place each for the whole suite. A
  green run is no slower, and a wait that never comes fails after 10 s, not 1 s.
- B: a timeout on each test that flaked. It is how the entries piled up: every next test needs
  its own.
- C: fewer vitest workers. It slows every run and does not help when other processes load the
  machine.

## What Changes

- The test waits for the field Provider to come on before it picks `claude`.
- vitest gives a test 30 s, and `waitFor` and `findBy` wait 10 s, in the whole suite.
- The twelve `{ timeout: 3000 }` of `Launch.test.tsx` and `ProjectRepos.test.tsx` go: 3 s was a
  longer wait than the default and would now be a shorter one.
- `docs/testing.md` says so.
- The entries "Vitest tests time out at vitest's default 5 s under load, one entry per test"
  and "Flaky vitest: Launch's taken name of a running session" leave BACKLOG.md, since their
  cause is fixed.

## Scope

- That one test in `web/src/Launch.test.tsx`, and the twelve explicit timeouts.
- `web/vite.config.ts`, `web/src/testSetup.ts`.
- `docs/testing.md`: the sentence on vitest in the Unit layer.
- Those two entries of BACKLOG.md.

## Out of scope

- `web/src/Launch.tsx`: the behaviour is right for a human (Why, option D).
- A shared helper for picking a provider: one line lacks the wait (Why, option B; AGENTS.md,
  Only what is used).
- "Launch vitest tests fail now and then under the load of a full run" in BACKLOG.md: it asks
  whether the window has a race of its own (`touched`), which waits do not answer.
- "Flaky: an OpenCode test of `LoginSheet.test.tsx`": its cause is not known.
- "`make check` fails on timeouts when the machine is under heavy load": mostly pytest's, and
  its note on `Launch.test.tsx:197` was a synchronous check, not a timeout.
- LAD-188, `Launch.test.tsx` of the field Model: a synchronous `getByRole` in a test of the epic.
- Making the Flows test that takes about 5 s shorter: under 30 s it no longer fails.
- `hookTimeout`: no entry shows a hook timing out.

## Impact

- Tests, their configuration, `docs/testing.md` and BACKLOG.md only. No behaviour rule changes,
  so there is no delta; archive with `--skip-specs`. `docs/design/ui.md` does not change: the
  screen does not.
- Version: nothing users see, so no CHANGELOG.md line and no version bump of its own (the patch
  rule at most).
- `epic/lad-154-models` rewrote much of `Launch.test.tsx` but kept this test's lines and left
  both configuration files alone: a trial merge of the line onto the epic's file had no
  conflict.
- Neutral core, one source of truth, no silent drops: `src/` does not change, and the waits get
  one place instead of twelve.
