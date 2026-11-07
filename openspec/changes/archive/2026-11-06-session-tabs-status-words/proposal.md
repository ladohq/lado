Task: LAD-218

## Why

Symptom (design QA of LAD-197, findings F1 to F4): in a window of 1100 to 1140 px the Artifacts
tab is cut right after the session opens, which LAD-197 brought: before it all four tabs stood
whole. In a column of 420 px Tab leaves the focused tab under the button ›. The Agents tab says
`busy`, `waiting` and `background` where the agent's popup says `working`, `waits for you` and
`in the background`. The team's list button has no tooltip beside neighbours that have one.

Cause of F2, measured on main with 12 agents and 14 artifacts. The finding says the session list
appears; it does not, it is open at 260 px at every one of these widths. From 1100 px the
terminals nobody opened fit beside the list (`fitColumns`, 360 px), so the chat falls from 747 to
420 px. There the tabs without icons and counts need 318 px and `Yours | All`, moved into the bar
by LAD-197, leaves them 276 px. The tabs' levels have nothing left to give but the scroll.

Cause of F1: the row keeps only the tab shown in view, by its own edges, and nothing follows the
focus. Cause of F3: the Agents tab prints the server's status as it is; the words of the popup
are private to `Team.tsx`. Cause of F4: `TeamList` has an `aria-label` and no `Tooltip`.

Options weighed for F2:

- A (taken, the human's answer #4034): on the last level before the scroll `Yours | All` folds
  into the phone's icon. Measured by putting the icon in the built page: at 1100 px the tabs get
  348 px, all four stand whole and › goes. It cures every column of 420 px, terminals opened by
  hand too, and leaves `fitColumns` alone. Long-term cost: one more tabs' level, and a window of
  1100 to 1140 px shows the icon instead of the words, with no counts (they lack 50 px).
- B: open the terminals nobody opened only from 1160 px. The chat is 748 px at 1100 px, but the
  step only moves (807 to 480 px at 1160), the terminals are shut on these windows, a column of
  420 px with terminals opened by hand stays cut, and a second least width enters LAD-193's rule.
- C: fold the session list instead. The chat is 595 px with the terminals open, but the list goes
  by itself, the reverse of LAD-193's order: terminals nobody opened fold first.

## What Changes

- The tabs give way in one more level: after the counts, a tool that has a short form takes it,
  and only then the tabs scroll. `Yours | All` folds into the phone's icon, with its tooltip.
- A tab that gets the focus, like the tab shown, stands clear of the fade and of › and ‹.
- One vocabulary of an agent's status: the popup's words on the Agents tab, on an agent's page
  (`waits for you · 6 min · spawned 16:02`), in the update's list of what to restart, in the
  accessible name of a terminal's tab and of a phone's chip.
- The team's list button shows its name as a tooltip, not while its list is open. That name
  reads `2 wait for you` for more than one agent, since everyone sees it now.

Scale: hotfix: four small defects with clear symptoms, no new module, no API change. Review:
precision. Version: fixes to what 0.45.0 brings, so no bump: the lines go under
`## 0.45.0 (unreleased)`.

## Acceptance criteria

- AC-1 At 1100, 1120 and 1140 px with nothing stored, on Activity with 12 agents and 14 artifacts,
  all four tabs stand whole, › is absent, and the icon stands at the bar's end with no
  `Yours | All`.
- AC-2 The icon chooses the messages as the radios do, shows the choice by `aria-pressed`, has the
  phone's tooltips, and the choice is the same when the bar widens and the radios come back.
- AC-3 At 1160 px and wider `Yours | All` shows as before; the word `Messages` still goes first,
  then icons, then counts.
- AC-4 In a column of 420 px with terminals opened by hand the tabs behave as at 1100 px.
- AC-5 The focus on a radio or on the icon survives the bar's level changing: it stays on the
  control, or moves to the other form of it.
- AC-6 With a bar too narrow for the tabs beside the icon, Tab brings each tab whole into view,
  clear of the fade, › and ‹; the tab shown is kept so too.
- AC-7 The Agents tab's rows, an agent's page, the popup and the team's list use the same six
  words, and so does the update's list of what to restart.
- AC-8 Pointer or keyboard on the chevron shows `All 12 agents`, on `+N` `<N> more agents`, with
  `, 1 waits for you` or `, 2 wait for you`, the same text as the accessible name; with the list
  open no tooltip shows.
- AC-9 `make web`, `make test`, `make lint` and the changed UI tests pass; CHANGELOG.md and
  docs/design/ui.md change in the same pull request.

## Out of scope

- F5 to F9 and the small notes of the QA report: the task leaves them until someone complains.
- Counts beside the icon at 1100 to 1260 px: they would need the icon to come before the counts,
  which trades the words for a number on windows that fit them today.
- The rule of the columns (`fitColumns`): option A needs no change, see Why.
- Team's levels (`useTeamFit`): another bar with its own rule; the head does not move.
- `lado ls`, `list_agents` and other CLI and MCP output: there a status is a value, not a label.
- `session-status-mark`'s words of a session: they tell of a session, not of an agent.

## Impact

- `web/src/Sessions.tsx`, `Team.tsx`, `Agents.tsx`, `Terminals.tsx`, `SystemPanel.tsx`,
  `styles.css`; tests in vitest and `tests/ui/`.
- `docs/design/ui.md`: the tabs' levels, Messages between agents, the Agents tab, the team's list
  button. CHANGELOG.md.
- Specs: deltas of `session-layout`, `activity-agent-messages`, `session-head`.
- No API, schema, MCP or CLI change. Neutral core: no provider is involved.
- LAD-196 (a stopped session) changes the head's team too: whoever merges second pulls main.
