Task: LAD-77

## Why

A session's Activity tab has a switch "Show agent messages" at the end of the team's row
(`web/src/Sessions.tsx`, `Activity`). The human did not know what it is for and proposed
to remove it (the task's screenshot). What it does: off (the default), the chat shows the
messages with the human only (`with=human`); on, it also shows the messages agents send
each other (supervisor → analyst, a worker → supervisor, LADO's step messages to a
worker), which are addressed to someone else; it is remembered in the browser, and an
agent page's **All in Activity** turns it on.

Two causes:

- The label: every message in the chat is an agent's already, so "Show agent messages"
  does not say what it adds, and nothing on the screen explains it.
- Its size: the checkbox with its label takes about 186 px of the team's row (with the
  row's gap), so in a narrow chat column (the terminal panel open: 484 px) the agents'
  chips and the runs' frames wrap to a second line (the human's reason for rejecting the
  first design).

The switch itself is wanted: LADO's supervisor does not relay reports to the human, so a
worker's report, a question between agents, a step message and a message between agents
that was not delivered are only in that traffic; it is the one place in the UI that shows
all of it (an agent's page shows its latest 10, `lado log` the rest outside the UI).

## What Changes

- The checkbox and its label become one icon button at the end of the team's row
  (approved mockup `mockup-placement.html`, variant Б): a new icon, two speech bubbles,
  in the UI's icon style; its accessible name **Messages between agents**; pressed while
  the messages between agents are shown (`aria-pressed`). Unpressed it is quiet (no
  border, muted, as the tabs' tool buttons); pressed it has the action colour's border
  and icon, as a pressed team chip has. About 26 px wide instead of about 170 px.
- It gets the UI's own tooltip (`Tooltip.tsx`), on hover and on the keyboard's focus, two
  lines: off, "Messages between agents: hidden" / "Click to also show what agents write
  to each other."; on, "Messages between agents: shown" / "Click to show only your
  conversation with the agents."
- Everything else stays: off by default, the same browser memory (`lado.agentMessages`),
  the same windows of the chat, **All in Activity** on an agent's page turns it on.
- docs/design/ui.md (the Activity tab, the agent's page) and CHANGELOG.md say so.

## Scope

The switch's form, label and tooltip in a session's Activity tab of the web UI, one new
icon, and the texts that name it (docs, tests).

## Out of scope

- Removing the switch (the human's first idea): the traffic between agents would leave
  the UI but for an agent's page (its latest 10); the human chose to keep it once its use
  was explained.
- The icon at the right end of the session's tab bar, where Flows has its search
  (placement variant А): the team's row would be the agents' alone, but in a 484 px
  column the tab bar has no room for it (it goes 26 px past the edge and the bar
  scrolls); the human chose the team's row.
- A small checkbox in the composer's "to supervisor" line (placement variant В): that
  line is about whom the human writes to, the switch is about the feed.
- Two named states "With you | All messages": a larger control for a setting seldom
  changed.
- A count of hidden messages, or showing the switch only when there are messages between
  agents: not asked for, and a second rule to keep true.
- Changing what the switch shows, its default or its memory.
- The tab bar's overflow in a narrow column (Flows' search past the edge today): not this
  task.

## Acceptance criteria

- AC-1: In a session's Activity tab the team's row ends with an icon button named
  "Messages between agents", `aria-pressed` false by default; no element of the UI reads
  "Show agent messages" any more.
- AC-2: Hovering the button (after the UI's tooltip delay) or giving it the keyboard's
  focus shows the tooltip of its state (off: "Messages between agents: hidden" / "Click
  to also show what agents write to each other."; on: "Messages between agents: shown" /
  "Click to show only your conversation with the agents."); it goes when the pointer
  leaves, the focus goes, or on Esc.
- AC-3: A click toggles it and works as the switch did: pressed shows the messages
  between agents in the feed, the choice is kept after a reload, and **All in Activity**
  on an agent's page opens Activity with it pressed.
- AC-4: In a chat column of 484 px (the terminal panel open) with three agents, the
  chips and the button stand on one line.
- AC-5: docs/design/ui.md and CHANGELOG.md describe the button; the vitest and UI e2e
  tests that named the switch pass with the button, and tests check the tooltip and the
  one line.

## Impact

- `web/src/Sessions.tsx` (`Activity`), `web/src/icons.tsx`, `web/src/styles.css`,
  `web/src/Chat.test.tsx`, `web/src/Agents.test.tsx` (and the vitest file that renders
  Activity), `tests/ui/test_chat.py`, `tests/ui/test_layout.py`, `docs/design/ui.md`,
  CHANGELOG.md.
- No API, schema, MCP or CLI change: a patch-kind UI change, listed under the unreleased
  `0.40.0`.

## Decisions for the record

- Scale tweak: one control of a known shape (an icon toggle with a tooltip), UI only;
  reviewed as a tweak.
- The texts are English, as the rest of the UI is.
- A `<button aria-pressed>` rather than a hidden checkbox: it is a toggle without a
  visible label, takes the keyboard's focus itself (so `Tooltip` works as on the chips),
  and the pressed look is the team chip's own. Its name stays "Messages between agents"
  in both states; the state is `aria-pressed`, and the tooltip's first line says it in
  words.
- The icon is new (`BetweenIcon` in `icons.tsx`, two speech bubbles, 24-unit grid, 1.6
  stroke), as the mockup draws it; no existing icon means "between agents".
- Its styles are a class of its own next to `.team-row` (the quiet unpressed state as
  `.tab-find .icon-button`, the pressed one as `.team-chip[aria-pressed="true"]`), 26 px
  square to sit with the 24 px chips; `.switch` stays for its other users
  (`SessionControl.tsx`, `Terminals.tsx`).
- The preference key `lado.agentMessages` and the prop `agentMessages` keep their names:
  a renamed key would reset every human's choice, and the names are not shown.
- Tests: vitest for the button, its pressed state and the tooltip's two texts (hover,
  focus, Esc), next to the existing Activity cases, which move from the checkbox to the
  button; the UI e2e layer for what needs a layout (one line in the 484 px column with
  the terminal open, `test_layout.py`) and a screenshot of the tooltip and of the pressed
  button, light and dark (`test_chat.py`). No integration test: nothing crosses a
  process.
