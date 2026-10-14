## 1. One rule

- [ ] 1.1 `web/src/flowSteps.ts` (new): `direction(states, from, to)` gives `"forward"`,
  `"back"` or `null` (a state not in `states`, or no states) by the declared order (a
  step back: `to` declared no later than `from`); `runsAgain(states, from, to)` gives the
  shortest way through `outcomes` from `to` to `from`, both included (`[to]` when equal),
  breadth-first, ties by declared order of states and outcomes, or `null` with no way.
  A comment names docs/design/ui.md (Flow events). Check: `flowSteps.test.ts` (1.2).
- [ ] 1.2 `web/src/flowSteps.test.ts`: the sdlc task flow (ready, changes, ready again:
  forward, back, forward; `review → review` back; `merge → build` back with `build ›
  review › merge_ok › merge`); the spec's branched flow (`review → fix`: `fix › review`;
  `review → build`: `build › review`; `fix → review` and `build → review` forward); no
  way (`null`); unknown state and empty states (`null`). Check: `make web`.

## 2. The chat and the Flows tab

- [ ] 2.1 `web/src/icons.tsx`: `BackIcon`, a return arrow on the 24-unit grid, drawn at
  12 px inside a chip (`.run-outcome .icon`, `.feed-chip .icon` in styles.css; the chip
  an `inline-flex` with a 3 px gap). Check: the mockup's section 1 and 4.
- [ ] 2.2 `web/src/Chat.tsx`: drop the window rule (`goesBack` and its use in `Rows`);
  `RunEvents` gets the session's runs (`state.runs[session]`, already watched) and
  `EventText` takes the step's direction from `flowSteps.direction` of its run's
  `states` (none while the runs are not loaded or the run has a `problem`): `forward`
  green, `back` orange with `BackIcon`, `null` neutral (`.run-outcome` alone); a forward
  or back outcome inside the UI's `Tooltip` (2.4); its accessible name `<outcome>, a step
  forward` / `<outcome>, a step back`. Check: `Chat.test.tsx`, `feedRows.test.ts` (3.1).
- [ ] 2.3 `web/src/Flows.tsx`: its `goesBack` replaced by `flowSteps.direction` (back
  when `"back"`, as before; no way back without the flow, as before); the back chip with
  `BackIcon`, the chip inside the same `Tooltip` (2.4), its accessible name as in 2.2;
  the dot's rule unchanged (orange for a way back or the human's answer). Check:
  `Flows.test.tsx` (3.1).
- [ ] 2.4 One component for the tooltip's text, shared by both (e.g. `StepTip` in
  `flowSteps.tsx` or beside `Tooltip`): `Forward in the flow, to <b>to</b>`, or `Back:
  the work returns to <b>to</b>` and, with a way, the line `Runs again: a › b` in the
  mono face, muted (`.tooltip-line + .tooltip-line` already mutes it). Check: the
  mockup's section 2a, variant 2.
- [ ] 2.5 `web/src/styles.css`: the chip's icon rules (2.1); comments of
  `.run-outcome.back` and `.feed-chip.back` name the icon; a `neutral` outcome keeps the
  `--raised` ground. Colours only through tokens. Check: `make web`.

## 3. Tests

- [ ] 3.1 vitest: `Chat.test.tsx` — the test that expected `changes` back because
  "design was left before" now gets the run's flow and checks forward, back and the
  second `ready` forward (AC-1); a run with a `problem` and a run not loaded give a
  neutral chip with no icon (AC-3); the icon and accessible names (2.2). `feedRows.test.ts`
  — the window rule's test goes with the rule. `Flows.test.tsx` — the existing "a way
  back is marked" test keeps passing, plus the icon and accessible name. Check: `make web`.
- [ ] 3.2 UI e2e, `tests/ui/test_chat.py`: a run of the fake agent moves forward, back
  (a stay in a state or an outcome to an earlier state) and forward again; both forward
  outcomes have the done colour, the back one the human colour and the icon; hovering
  each shows the tooltip with the texts of AC-4; a screenshot in the light and the dark
  theme. Check: `uv run pytest -m ui tests/ui/test_chat.py`.
- [ ] 3.3 UI e2e, `tests/ui/test_flows_tab.py`: the same run's history shows the icon on
  the back step, and hovering it shows the same tooltip (AC-4, AC-6); a screenshot.
  Check: `uv run pytest -m ui tests/ui/test_flows_tab.py`.
- [ ] 3.4 Regression: `make web`, `make lint`, `uv run pytest -m ui
  tests/ui/test_chat.py tests/ui/test_flows_tab.py tests/ui/test_gates.py
  tests/ui/test_live_updates.py` (AC-7).

## 4. Docs

- [ ] 4.1 `docs/design/ui.md`: Flow events — a move's direction by the flow's declared
  order (`flowSteps.direction`), the same in Flows; the window rule and "a move's colour
  may turn from green to orange" go; the return icon; the tooltip's two texts; neutral
  without the flow (LAD-62, 2026-10-14, mockup `mockup-outcome-colour.html`). Flows (a
  step's line): the icon and the tooltip. A sentence for kit authors: declare a flow's
  states in the order its work goes, branches before the state they join. Check: read
  through.
- [ ] 4.2 `CHANGELOG.md` under `## 0.39.0 (unreleased)`: a flow step's outcome is green
  forward and orange back by the flow's order in the chat as in the Flows tab (the same
  `ready` no longer turns orange after a review's changes); a step back has a return
  icon, and hovering an outcome says where the step goes and, for a step back, which
  states run again.
