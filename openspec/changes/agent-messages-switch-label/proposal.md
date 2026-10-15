Task: LAD-77

## Why

A session's Activity tab has a switch "Show agent messages" at the end of the team's row
(`web/src/Sessions.tsx`, `Activity`). The human did not know what it is for and proposed
to remove it (the task's screenshot). What it does: off (the default), the chat shows the
messages with the human only (`with=human`); on, it also shows the messages agents send
each other (supervisor → analyst, a worker → supervisor, LADO's step messages to a
worker), which are addressed to someone else; it is remembered in the browser, and an
agent page's **All in Activity** turns it on.

The root cause is the label: every message in the chat is an agent's already, so "Show
agent messages" does not say what it adds, and nothing on the screen explains it.

The switch itself is wanted: LADO's supervisor does not relay reports to the human, so a
worker's report, a question between agents, a step message and a message between agents
that was not delivered are only in that traffic; it is the one place in the UI that shows
all of it (an agent's page shows its latest 10, `lado log` the rest outside the UI).

## What Changes

- The switch reads **Messages between agents** (approved mockup
  `mockup-agent-messages.html`, variant 1).
- It gets the UI's own tooltip (`Tooltip.tsx`, as the team's chips have), on hover and on
  the keyboard's focus: "Also show the messages agents send each other. Off: only your
  conversation with the agents."
- Everything else stays: off by default, the same browser memory (`lado.agentMessages`),
  the same windows of the chat, **All in Activity** on an agent's page turns it on.
- docs/design/ui.md (the Activity tab, the agent's page) and CHANGELOG.md say so.

## Scope

The switch's label and tooltip in a session's Activity tab of the web UI, and the texts
that name it (docs, tests).

## Out of scope

- Removing the switch (the human's first idea, variant 3): the traffic between agents
  would leave the UI but for an agent's page (its latest 10); the human chose to keep it
  once its use was explained.
- Two named states "With you | All messages" (variant 2): clearer, but a larger control
  for a setting that is seldom changed; the human chose variant 1.
- A count of hidden messages, or showing the switch only when there are messages between
  agents: not asked for, and a second rule to keep true.
- Changing what the switch shows, its default or its memory: the task is about
  understanding it, not its behaviour.

## Acceptance criteria

- AC-1: In a session's Activity tab the team's row ends with a checkbox named "Messages
  between agents"; no element of the UI reads "Show agent messages" any more.
- AC-2: Hovering the switch (after the UI's tooltip delay) or giving its checkbox the
  keyboard's focus shows the tooltip "Also show the messages agents send each other. Off:
  only your conversation with the agents."; it goes when the pointer leaves, the focus
  goes, or on Esc.
- AC-3: The switch works as before: off by default, on shows the messages between agents
  in the feed, the choice is kept after a reload, and **All in Activity** on an agent's
  page opens Activity with it on.
- AC-4: docs/design/ui.md and CHANGELOG.md name the new label; the vitest and UI e2e
  tests that name the switch pass with the new name, and a test checks the tooltip.

## Impact

- `web/src/Sessions.tsx` (`Activity`), `web/src/Sessions.test.tsx` or the test that
  renders Activity, `web/src/Chat.test.tsx`, `web/src/Agents.test.tsx`,
  `tests/ui/test_chat.py`, `tests/ui/test_layout.py`, `docs/design/ui.md`,
  CHANGELOG.md.
- No API, schema, MCP or CLI change: a patch-kind UI change, listed under the unreleased
  `0.40.0`.

## Decisions for the record

- Scale tweak: one label and one tooltip of a known shape, UI only; reviewed as a tweak.
- The label and the tooltip are English, as the rest of the UI is.
- The tooltip wraps the switch's `<label>` (the whole clickable area, so the pointer on
  the text shows it too); the keyboard's focus on the checkbox inside reaches it as a
  focus event of the label. If `Tooltip`'s focus check does not take the inner checkbox's
  focus as the keyboard's, the developer passes the focus through without changing how
  other tooltips behave.
- The preference key `lado.agentMessages` and the prop `agentMessages` keep their names:
  a renamed key would reset every human's choice, and the names are not shown.
- Tests: vitest for the label and the tooltip (hover and focus) next to the Activity
  tests; the UI e2e tests only rename the checkbox they look for, and `test_chat.py`
  hovers it once and saves a screenshot of the tooltip. No integration test: nothing
  crosses a process.
