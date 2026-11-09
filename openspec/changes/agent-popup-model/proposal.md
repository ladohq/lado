Task: LAD-254

## Why

CHANGELOG 0.45.0 ("See which model each agent runs on") says the Team chip's tooltip shows
the agent's model. In 0.45.0rc1 the popup of an agent's avatar in the session's head and on
the terminals' strip (`AgentPopup`) reads its name, status, `role · provider`, flow and
`Click to open the terminal`, with no model (found by the manual check of 0.45.0rc1, the
session artifact `rc-report-0.45.0rc1`, item 1).

Cause: LAD-180 (`agent-model-visible`, 2026-11-01) added the model to the chip's tooltip
`AgentTip`. LAD-197 (`3caa928d`, 2026-11-06) moved the team into the session's head with a
new popup, `AgentPopup`, which did not carry the model over; `AgentTip` stayed only on a
terminal's tab and a phone's chip. Its five plain lines also run together: the human found
the popup hard to read once a model line is added.

Options weighed:

- A (taken, the human's choice): the popup in three parts: the name with its status dot and
  the status; under a line, labelled facts `Role`, `CLI`, `Model`, `Flow`; under a second
  line the click's hint, smaller. Long-term cost: a few CSS rules of its own, and tests
  that read the popup by its parts instead of its lines.
- B: name and status on one line, then `role · CLI · model`, flow, the hint under a line.
  Shorter, but again a line of words joined by dots.
- C: the head's avatar shows `AgentTip`: one line `name · role · provider · model`, and the
  popup loses its status and hint.

Effort and the sources of model and effort stay on the agent's page: the human's decision,
effort as a setting is later work of LAD-154 and the popup was never meant to show it. The
CHANGELOG item, which promises effort and sources in the tooltip and `lado ls`, is
corrected to what they show.

## What Changes

- `AgentPopup` (web/src/Team.tsx), the popup of the head's avatars and the terminals'
  strip, takes the layout of option A and names the agent's model: a configured model's
  saved name, else the name its CLI reported, else `CLI default` in muted ink.
- CHANGELOG.md, 0.45.0's "See which model each agent runs on": the agent's page shows
  model and effort and where they came from; the Team tooltip and `lado ls` name the model.
- docs/design/ui.md, Session head: the popup's new parts.

## Out of scope

- Effort and the sources' words in the popup: the human's decision; they are on the
  agent's page, and effort as a setting is later work of LAD-154.
- `AgentTip` (a terminal's tab, a phone's chip): it already names the model; a phone shows
  no tooltip on a touch.
- The server and the API: `AgentInfo.model` already carries everything the popup shows.

## Capabilities

### Modified Capabilities

- `session-head`: an agent's popup reads in three parts and names its model.
- `agent-model`: an agent's popup names its model, without effort or source.

## Impact

- web/src/Team.tsx (`AgentPopup`), web/src/styles.css, their vitest tests
  (Team.test.tsx, Layout.test.tsx, Terminals.test.tsx), tests/ui/test_layout.py.
- CHANGELOG.md (one item reworded), docs/design/ui.md.
- No schema, API, MCP or CLI change: a fix for 0.45.0rc2, a patch.
