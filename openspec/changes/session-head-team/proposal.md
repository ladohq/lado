Task: LAD-197

## Why

Symptom (audit of LAD-189, findings F5, F25): under the head of a session lie about 150 px of
service rows. At 1440×900 the feed starts at y = 135 and gets 671 px. `to supervisor` repeats the
field's placeholder, and the keys hint stands there all the time. The icon "Messages between
agents" and its state are hard to read.

Cause: the team was added as a row of the Activity tab (feature/activity-team), the toggle went to
its end (LAD-77), and the composer's line stayed in the flow. Each is a row of its own in a page
whose height is what the human reads in. LAD-192 made the head one line of 48 px, with free room at
its right that no row uses, and the head lies over all columns: its width depends on the window and
never on the terminals.

Options weighed:

- A: the team in the tab bar when it fits, else its own row (LAD-189 spec §6). Small; but the bar is
  as wide as the chat column, so with terminals open or 5 agents the row stays and the feed gets
  +38 px only, and the rule of LAD-77 cannot hold at 484 px. The human rejected it.
- B (taken, the human's design of 2026-11-06, artifacts of run `ui-design/lad-197-team-head`): the
  team in the head on every tab, in levels. +71 px whatever the team and the terminals, and its
  status shows on every tab. It costs a level trial, a list for what does not fit and new marks.
- C: one Team button in the head with a list. The least code, the most height; but statuses and the
  one click to a terminal, which only this place gives, are gone.

## What Changes

- Above a phone the team moves from the Activity tab to the head, on every tab, at the right before
  Stop. It gives way in four levels, one level for all agents: whole names, shortened names,
  avatars, avatars with `+N`.
- A level with names holds only while the title shows its first 24 characters. So a wide window
  does not cut the title to keep long rows of names.
- From level 1 a button opens the team's list, with every agent by its whole name.
- An agent's popup gets a new content; marks such as `D2` and a ring at the status mark apply in the
  head and on the terminal strip.
- The toggle becomes `Yours | All` at the end of the tab bar on Activity; a phone keeps its icon.
- The keys hint shows only in an empty field with the focus, in the page's bottom padding, so
  nothing moves; `to <agent>` shows only for an agent other than the supervisor.
- The feed starts at y = 88 and gets 742 px at 1440×900 (+71 px); the targets 90 and 744 of LAD-189
  are replaced by these.

The change bumps the minor: it is a feature users see, and goes under `## 0.45.0 (unreleased)`. No
API, schema, MCP or CLI change.

## Out of scope

- The Team row on a phone, its 24 px chips and 35 px tabs: the human's decision in LAD-193; a phone
  changes only by `to supervisor`.
- Losing the link to the server (LAD-195): it runs in parallel and touches `Composer.tsx` and
  `Sessions.tsx` elsewhere; whoever merges second takes main.
- A stopped session, where the team does not show (LAD-196): the head shows what `agents` gives.
- A row mixing names and avatars: decided against by the human (a row reads worse, one level for all).
- The limit of 24 characters at avatar levels: agents hidden behind `+N` cost more than a few
  letters of a title.
- Moving `Yours | All` on a phone: there is no room.
- The word `Messages` on every width: it goes before the tabs give anything up (critique F10).

## Impact

- `web/src/`: `teamFit.ts` (new), `Team.tsx`, `Sessions.tsx`, `Composer.tsx`, `Terminals.tsx`,
  `prefs.ts`, `styles.css`, their vitest files.
- `tests/ui/`: tests that look for the group `Team` on a computer, new `test_team_head.py`.
- `docs/design/ui.md`, `CHANGELOG.md`.
- Specs: `session-head`, `session-layout`, `activity-agent-messages`, `phone-layout`,
  `chat-question-card`.
