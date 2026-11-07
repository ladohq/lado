# A stopped session's page (LAD-196)

Change: `openspec/changes/stopped-session-bar/` (proposal with AC-1..AC-10, the new capability
`stopped-session`, deltas of `activity-agent-messages` and `session-layout`, `design.md` with
D1-D10). This document is the human's view. Source of the look: LAD-189 spec §5, frames g5-1440 and
g5-term in `lad-189-mockup.html`; for 768, 390, sideways and Resume in the head, run artifact
`mockup-stopped-session.html`; run artifact `ui-review/lad-196-mockup/critique`.

## What a user gets

    ● Old stopped work ▾   stopped 3 min ago · ran <1 min            [bin] | ● live
    Activity  Agents  Flows  Artifacts

                     Nothing was said in this session.

    | This session is stopped                          [▷ Resume session] |
    | Its branches, runs and history are kept                             |

The page says what the session is and leads on with one button. On tabs with no bar the head has
`[▷ Resume] [bin]`. The terminals stand folded; opened, they say that the agent is not running.
After Resume the composer, the human's terminals and the draft are back.

## Width by width

| Window | Bar | Head on Flows, Artifacts, Agents | Team |
|---|---|---|---|
| above 900 | one row | `▷ Resume`, bin | none |
| 601-900 | one row | `▷ Resume`, bin | none |
| phone upright | text, then the button at full width, 44 px | `▷ Resume`, bin, 44 px | no word Team; toggle with its words |
| phone sideways | one row, button 44 px | as upright | row hidden, as for any session |

## Words, exactly

| Where | Text |
|---|---|
| Bar, first line, 14 px, weight 600 | `This session is stopped` |
| Bar, second line, 13 px, `--muted` | `Its branches, runs and history are kept` |
| Bar's button, `.primary` | `Resume session` |
| Head's button, 14 px, weight 500 | `Resume`, accessible name `Resume…` |
| Empty feed, All | `Nothing was said in this session.` |
| Empty feed, Yours | `No messages with you. Messages between agents are hidden.` |
| Terminal, mono 13 | `Agent not running — resume the session to start it` |
| Phone's toggle | `Messages between agents` |

Tooltip of a disabled Resume: `Waiting for connection`.

## Where the frames do not hold

- The strip of g5-1440 shows an avatar and the tab `Agents 1`. A stop deletes the agents: the strip
  has the show button and its caption, and the tab has no count.
- `Viewing` stays above the terminal's text, as in g5-term.

## Colours and sizes

Tokens only, none new: `--panel`, `--line`, `--muted`, `--ink`, `--action`, `--on-action`,
`--term-ground`, `--term-ink`. The bar: at least 52 px, radius 8, as wide as the composer's frame
(860 px at most).

## After the build

The second ui-review checks the build at a running URL against g5-*, this mockup and the dark theme.
