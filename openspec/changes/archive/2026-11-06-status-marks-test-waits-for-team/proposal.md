Task: LAD-215

## Why

Symptom: `tests/ui/test_status_marks.py::test_busy_and_background_are_green_and_pulse_and_background_is_half_filled`
fails now and then with `ValueError: not enough values to unpack (expected 2, got 0)` at
`supervisor, w1 = team.get_by_role("button").all()`, and passes alone. BACKLOG.md has held it
since 2026-10-10 with four repeats; the last failure was a developer's local run on LAD-193,
2026-11-06, with no link to that change.

Cause: a race in the test, not a defect of LADO. Playwright's `Locator.all()` does not wait:
it counts the matches once, at that moment, and returns `nth(i)` for each. The line before it
clicks Collapse terminals, which says nothing about the team: the toolbar exists, or is about
to, and its chips come only when the session's agents have loaded (`HeadTeam` renders nothing
before that, `web/src/Team.tsx`). Under load the agents load after the click, the count is 0
and the unpacking fails. Alone they load first.

The product is not at fault: a head without a team until the agents load is its design.

Options weighed:

- A (taken): wait for the two buttons first,
  `expect(team.get_by_role("button")).to_have_count(2)`, and keep the line with `.all()`. One
  line; the test states its premise, two chips, and a third button fails it with a clear
  message instead of a `ValueError`. Long-term cost: none beyond the line.
- B: drop `.all()` and name each chip, `team.get_by_role("button", name="supervisor, working")`.
  Closes the race as well, but the two `expect(...).to_have_accessible_name` lines then assert
  what the locators already say, and a wrong status reads as a timeout on a missing button
  rather than as a wrong name. Long-term cost: a less telling failure.
- C: A for each of the sixteen `.all()` calls of `tests/ui/`, or a rule that forbids an
  unwaited one. None but this one is known to have failed, so a guard would serve no known
  failure (AGENTS.md, "Only what is used").

## What Changes

- `tests/ui/test_status_marks.py`: the test waits for the two Team buttons before it reads them.
- `BACKLOG.md`: the entry "UI e2e test of the status marks reads the Team buttons before they
  render" goes, as this change closes it.
- Neither a minor nor a patch of its own: tests only, users see nothing, so no CHANGELOG.md
  line, no API, schema, MCP, CLI or UI change, no mockup; docs/design/ui.md stays as it is.

## Scope

- `tests/ui/test_status_marks.py`, `BACKLOG.md`. Nothing in `src/` or `web/`.

## Out of scope

- `tests/ui/test_chat.py:84` (`ship, port = card.get_by_role("listitem").all()`) and
  `tests/ui/test_kits_page.py:217` (`tag, newer = line.locator(".kit-version").all()`), the
  other two unpackings of `.all()`: an earlier wait stands before each (the card's tabs, the
  card's measured box) and neither has failed; a change there would have no failure to prove
  it, and the task does not name them.
- The rest of the test: every later read goes through `supervisor` and `w1`, which `.all()`
  gives as `nth(i)` locators, resolved anew on each use, so a later render does not stale them.
- A rerun plugin or a longer timeout: they hide the race rather than close it.

## Acceptance criteria

- AC-1: `test_busy_and_background_are_green_and_pulse_and_background_is_half_filled` waits with
  `expect(team.get_by_role("button")).to_have_count(2)` before `.all()`; the rest of the test
  is unchanged.
- AC-2: The race is shown by hand once: with the old test and the response of the session's
  `GET …/agents` held back by `page.route`, the test fails with the `ValueError`; with the fix
  and the same delay it passes. The build report quotes both; the probe is not committed.
- AC-3: With the fix, the test passes 20 times in a row alone (`uv run pytest -m ui -n0
  tests/ui/test_status_marks.py`), and 5 times in a row with the whole file under `-n auto`.
- AC-4: BACKLOG.md no longer holds the entry; the entries around it and the section "`make
  check` fails on timeouts when the machine is under heavy load", which Review traps of
  `.lado/sdlc.md` name, stay.
- AC-5: `make lint` passes and CI is green.

## Impact

- `tests/ui/test_status_marks.py` and `BACKLOG.md` only.
- No delta (`skip_specs` in `.openspec.yaml`): no behaviour rule changes; archived with
  `--skip-specs`.

## Decisions for the record

- Scale tweak: a test-only change of known shape, the fix named by the task; review by
  precision.
- Root cause is the test reading the buttons without a wait; fixed in the test.
- `to_have_count(2)` over a wait for the first chip: the unpacking needs exactly two, and one
  chip may stand while the other is still to come.
- The fit of the head (`useTeamFit`) tries its levels synchronously inside one task, so no
  other button count lasts long enough to satisfy the wait wrongly; were it to, `nth(i)` reads
  the settled chips and the accessible-name checks that follow hold the result.
- Test layer: UI e2e (`make test-ui`), the test itself; no new test.
