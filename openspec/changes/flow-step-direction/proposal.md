Task: LAD-62

## Why

The same outcome of the same move, `build → review ready`, shows green in one place of a
session's chat and orange in another (the task's screenshots: task/lad-59's `ready` green,
task/lad-58's second `ready` orange). The colour is meant to say whether a flow step goes
forward or back, but the chat decides it by its own rule (`goesBack` in
`web/src/Chat.tsx`): a move goes back when it stays in its state or enters a state the run
left earlier *in the loaded window*. After a reviewer's `review → build changes`, every
later `build → review ready` enters `review`, which the run left before, and turns orange;
loading earlier pages can turn a green move orange. The Flows tab decides the same thing
by another rule (`goesBack` in `web/src/Flows.tsx`): a step goes back when it leads to a
state the flow declares no later than the one it left, so there both `ready` are green.
Two rules for one fact: the root cause. And the colour's meaning is said nowhere on the
screen.

## What Changes

- **One rule, the Flows tab's** (`web/src/flowSteps.ts`, new): a step goes back when it
  leads to a state the run's flow declares no later than the state it left (staying in a
  state included); otherwise forward. Unknown (a run not loaded, a flow that cannot be
  read, a state not in the flow) is neither: the outcome's chip is neutral (the `--raised`
  ground, no icon, no tooltip). The chat and the Flows tab both call it; the chat's
  window rule goes. The chat takes each run's flow from the session's runs it already
  watches (`state.runs[session]`).
- **A step back keeps its orange and gains an icon**: a return arrow (`BackIcon`, new in
  `icons.tsx`) before the outcome, in the chat's `.run-outcome.back` and the Flows tab's
  `.feed-chip.back`. Forward stays green with no icon.
- **The UI's own tooltip on the outcome** (`Tooltip.tsx`, not a `title`), in the chat and
  in the Flows tab, from the run's flow alone:
  - forward: `Forward in the flow, to <to>`;
  - back: `Back: the work returns to <to>`, and a second line `Runs again: <to> › … ›
    <from>`: the shortest way through the flow's outcomes from the state the work returns
    to back to the state it was sent back from (both included; one state when it stays).
    No such way, no second line. Never the whole flow: a branched flow does not fit a
    line, a way between two states always does.
- docs/design/ui.md: Flow events (the chat) and Flows (a step's line) name the one rule,
  the icon and the tooltip, and the advice to kit authors: declare a flow's states in the
  order its work goes, branches before the state they join.
- CHANGELOG.md: a line under `## 0.39.0 (unreleased)`.

Approved mockup: `mockup-outcome-colour.html` (sections 1, 2 with 2a's second variant,
"Runs again", 3 and 4).

## Scope

The web UI's colour, icon and tooltip of a flow step's outcome in a session's chat and in
the Flows tab's run history. Nothing in the core, the API, the MCP tools or the schema.

## Out of scope

- A rule from the flow's graph alone (distance from the start, a depth-first search's back
  edges): in a cycle such as `build ⇄ review` the graph does not say which edge goes back,
  only the author's order does; a distance rule also colours `build → review` back in a
  flow where `review` is reached sooner by another branch.
- The whole flow in the tooltip (the first mockup's variant B): a branched flow cannot be
  drawn as one line, the human pointed out; the "Runs again" way replaces it.
- "Next: <who>" in the tooltip (variant C): the chat's next line says it already.
- A grey step back (option 2) and no colour at all (option 3): the human kept the orange
  and took the icon from option 2.
- Other wordings of the second line (`Again`, `To redo`, a loop with no word, one
  sentence): the human chose `Runs again`.
- The Flows tab's orange dot for the human's answer: not a step's direction, unchanged.
- The tooltip from the keyboard: the chips are no tab stops (a chat has many); the
  direction is in the chip's accessible name instead.

## Acceptance criteria

- AC-1: In the chat, after `build → review ready`, `review → build changes` and
  `build → review ready` of a run of a flow declaring `design, design_ok, build, review,
  …`, both `ready` are green and `changes` is orange with the return icon; loading earlier
  pages changes no colour.
- AC-2: A step that stays in its state (`review → review`) is orange with the icon, in the
  chat and in the Flows tab.
- AC-3: A step of a run whose flow cannot be read, or not loaded yet, has a neutral chip,
  no icon and no tooltip, in the chat; in the Flows tab as before (green, no way back).
- AC-4: Hovering a step's outcome shows the UI's tooltip after its delay: `Forward in the
  flow, to review`, or `Back: the work returns to build` with `Runs again: build ›
  review`; in the chat and in the Flows tab alike, in the light and the dark theme.
- AC-5: In a branched flow (a state with two outcomes to different branches that join
  later), the `Runs again` line is the shortest way from the state returned to to the
  state left, one line; with no way, only the first line.
- AC-6: The chat and the Flows tab colour every step alike, by one function.
- AC-7: docs/design/ui.md and CHANGELOG.md say so; vitest and UI e2e tests check AC-1 to
  AC-6 and pass, and the existing chat and Flows tests pass.

## Impact

- `web/src/flowSteps.ts` (new) and its test, `web/src/Chat.tsx`, `web/src/Flows.tsx`,
  `web/src/icons.tsx`, `web/src/styles.css`, `web/src/Chat.test.tsx`,
  `web/src/feedRows.test.ts`, `web/src/Flows.test.tsx`, `tests/ui/test_chat.py`,
  `tests/ui/test_flows_tab.py`, `docs/design/ui.md`, CHANGELOG.md.
- No API, schema or MCP change: a fix, the patch; the line goes under the unreleased
  `0.39.0` already open.

## Decisions for the record

- Scale tweak: a UI rule and its look, of known shape, in two components; review as a
  tweak.
- The rule lives in one module, `flowSteps.ts`, taking a run's `states` (`RunInfo.states`,
  in declared order, with each state's `outcomes`): one source for both tabs, and the
  API already gives all it needs, so no field is added.
- The declared order over the graph: see Out of scope; for every flow of the kits in use
  (sdlc, builder, lado-dev) the declared order is the order of work, and the start is the
  first state.
- "Runs again" by breadth-first search over `outcomes`, ties broken by the order the flow
  declares states and their outcomes, so the line is stable.
- Unknown is neutral in the chat rather than guessed by the old window rule: a second rule
  would be the bug again. The Flows tab keeps its own "no way back without the flow".
- The chip's accessible name says the direction (`<outcome>, a step back` / `<outcome>,
  a step forward`), since the icon is decorative (icons.tsx) and the tooltip is hover
  only there.
- Test layers: the rule and the way in vitest (`flowSteps.test.ts`, pure logic); the
  components' classes, icon and accessible names in vitest; the tooltip on hover and the
  colours in both themes in the UI e2e tests (a real browser and the fake agent's run).
