# Flake races: design

Task: LAD-44. Change: `openspec/changes/flake-races/` (proposal, deltas `server-stop`,
`turn-end-hand-over`, `gate-history-order`, `design.md` D1-D8).

## Problem

At the 0.37.0 release, CI went red on nine tests that passed on a rerun. Earlier attempts
treated them as slow-runner timeouts. Each one has a precise cause instead. Four of the
causes are races in LADO itself, which a user can meet without any test. The CI failures
should be treated as their signal, not as noise.

## Causes and fixes

| # | Symptom | Cause | Where it is fixed |
|---|---|---|---|
| 1 | uninstall: UI server still alive | `server_run.stop` returns when the lock is free, while the process still lives; its exit kick can recreate `LADO_HOME` | LADO: stop waits for the process (D1); `lado server` does not kick at its exit (D2) |
| 2 | turn-end output arrives `typed` (3 tests) | idle and the hand-over are two transactions; the session loop types the queue in between | LADO: one transaction (D3) |
| 3 | gates test: "not in viewport" | a gate is 1 ms older than its `gate_open` event, so the chat shows it above the event; the test's "You" filter matches "waits for you" | LADO: one time for both rows (D4); test: exact actor locator (D6) |
| 4 | stop test: 30 s timeout | the fake agent's stdin EOF/EIO comes before SIGHUP; its `hung_up` mark is never written | fake agent: one session end on any path (D5) |
| 5 | terminal socket: input lost | `done` output frame taken as proof that the input was written | test waits for `written` (D6) |
| 6 | Launch.test:216, ArtifactTab image | checks run one render before an effect sets the state | tests wait for the state; title reset (D6) |
| 7 | chat question card: "no recommendation" | the test recommends before LADO's request; the request resets it | test waits for the request to be handled (D6) |
| 8 | Codex smoke macOS: no model API | count taken with no wait; Codex posts ~1 s later | smoke waits up to 120 s (D6) |
| 9 | gates "disagrees" | fixed by LAD-38 | none |

## What the user sees

- `lado server stop`, `lado update` and `lado uninstall` go on only after the old UI
  server's process has ended. A server that hangs at exit is reported, not ignored. After
  `lado uninstall`, no `~/.lado` comes back.
- A Claude Code or Codex agent gets the messages queued during its turn in its turn-end
  hook's output whenever its CLI takes that output, never pasted into its window by a
  race.
- In a session's chat, a gate's line always follows the run's move that opened it.

## Holding it against the roadmap and the principles

- **Neutral core**: D3 sits in `hooks`/`runtime`/`state`, so it works the same for all
  four providers. Only providers with `deliver_on_turn_end` gain the hook-output channel
  back. For the others the channel was `typed` already.
- **No silent drops**: the paste in D3 dropped nothing, but it delivered by a channel
  LADO did not choose. D1 turns a silent early return into a wait or an error.
- **One source of truth**: D4 takes the event's time from the gate's own row and does not
  keep a second clock.
- **Only what is used**: there is no new state, API, option or schema. The test-only
  gaps (causes 5-8) are closed in the tests.
- **Tested end to end**: D1 gets an integration test with a real `lado ui`. The
  integration tests of D3 keep their strict channel checks, now without the race.

## Version

Patch (fixes only). No API, MCP, CLI option or schema change.

## Proof

Each race is first reproduced by hand with a delay injected where its cause says, and
fails every time. Then each fixed test runs 20 times in a loop. Then 5 full CI runs in a
row are green on the last commit, and the Codex macOS smoke is green 20 times.
