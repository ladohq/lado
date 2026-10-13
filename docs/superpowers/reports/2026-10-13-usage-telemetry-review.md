# LAD-32 usage-telemetry: review report

Pull request #12 `feature/lad-32-usage-telemetry` → `main`. Scale: full change, review
depth: breadth. Head reviewed last: `24b47df`; the archive commit follows it. LADO's error
journal (`errors.jsonl`) and, only with the human's yes, anonymous usage statistics and
scrubbed errors sent by a detached sender (`telemetry.py`, `lado telemetry`, the consent
question of `lado start` and `lado ui`, the UI's statistics endpoints and panel, bounded
logs). No schema migration; `hooks.py`, `mcp_server.py` and `runtime.py` changed only in
catching errors and the `spawned` event's detail, no provider launch code.

## Rounds

- **Round 1** (`origin/main...f132838`): local breadth pass with the lenses Spec, Tests,
  Silent failures, Comments, Types, General and the architecture against AGENTS.md. Found
  F1, F2 (important), F3, F4 (minor).
- **Round 2** (`f132838..c945b15`): local precision pass. Found F5 (important) and a
  conflict with `main`, merged in `aeffc49`.
- **Round 3** (`c945b15..5888070`): local precision pass, and external round 1 by the
  Claude Code Action over the whole pull request (request 07:22:53 UTC, "Claude finished"
  07:24:07 UTC). Found F6, F7 (by a red CI), F8, and the external observations E1–E7.
- **Round 4** (`5888070..24b47df`): local precision pass and external round 2 over the
  delta (request 07:31:52 UTC, "Claude finished" 07:32:40 UTC). No new findings; the
  external reviewer agreed with every refutation and decline.

## Findings fixed

Each has a test that failed before its fix.

- F1 (important): the sender's deadline was swallowed by an `except Exception` while the
  report was built, and an agent CLI's `--version` took 30 s → `70c30ca`
  (`test_the_deadline_is_not_swallowed_while_the_report_is_counted`).
- F2 (important): `lado doctor`'s unexpected errors were not journaled → `70c30ca`
  (`test_unexpected_doctor_error_is_journaled_and_reraised`).
- F3 (minor): `lado update` kicked the sender after its installer → `70c30ca`
  (`test_update_starts_nothing_after_the_installer`).
- F4 (minor): an empty send rewrote `sent.json` → `70c30ca`
  (`test_an_empty_send_keeps_the_last_send_and_its_failure`).
- F5 (important): an agent CLI's `--version` in a daemon thread outlived the sender →
  `5888070` (`test_a_hanging_cli_s_version_is_ended_with_its_share`).
- F7 (important): `test_slow_agent_clis_take_only_their_share` depended on the agent CLIs
  installed (`KeyError: 'codex'` in CI) → `24b47df`.
- F8 (minor): a journal line with a non-string `at` raised `TypeError` in `_lado_errors` →
  `24b47df` (`test_a_journal_line_of_another_shape_is_not_counted`).

F5 and F7 came from the fix of F1.

## Declined (minor)

- F6: a `--version` started milliseconds after the `join` deadline could outlive the
  sender; the window is milliseconds against tens of milliseconds of work after `join`.
- E3: `off` during a POST already running: any switch's race; a try is bounded by 30 s.
- E4: `preview` creates the local `telemetry/id` (mode 600) while sending is off; it goes
  nowhere.
- E6: a crash between a 2xx and the write of `sent.json` may send twice: a duplicate
  rather than a loss (design D7).

## Refuted

- E1: the raw hook name comes from argv LADO writes itself.
- E2: the `spawned` detail is written only by `runtime._add_agent` with a registered
  provider.
- E7: `send()` runs only in the main thread, where `_deadline`'s SIGALRM works.

## Not verified (residual risk)

- No real send to PostHog (`eu.i.posthog.com` with the project token) ran; the tests post
  only to a local endpoint. E5, how PostHog treats a batch it rejects for good, belongs
  here.
- "The project discards the client's IP address" (`docs/telemetry.md`) is a setting of
  the PostHog project, for the human to check.
- `make check`, `make test-integration` as a whole and `make test-smoke` ran only in CI;
  `make test-live` did not run.

## Checks at `24b47df`

- `make lint`: exit 0. `make test`: 2678 passed.
- `tests/test_telemetry.py` with no agent CLI on PATH: 62 passed.
- At `5888070` (the delta since touches neither `web/` nor integration): the telemetry
  integration test 3 passed, UI tests `test_statistics` and `test_system_panel` 4 passed,
  `make web` 692 passed.
- CI on `24b47df`: green, `check (3.10)`, `check (3.13)`, `js`, `ui` and all 8 smoke
  cells (Linux and macOS).

## Found on the way

- A new UI flake, `test_gates::test_a_gate_with_a_recommendation_that_disagrees`, added to
  BACKLOG.md (`c945b15`) with new runs of known flakes.
