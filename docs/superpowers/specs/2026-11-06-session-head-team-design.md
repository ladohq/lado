# The team in a session's head

Task LAD-197. Decisions: `openspec/changes/session-head-team/design.md`. Rules:
that change's delta. This document is the sizes, states and words, from the design of run
`ui-design/lad-197-team-head`, with the human's changes of 2026-11-06. The mockup is the run
artifact `mockup-team-head.html`; the new CSS is that run's artifact `design-system`.

## Result

At 1440×900 the feed goes from y = 135, 671 px, to y = 88, 742 px: +71 px (the team row 25, its gap
10, the gap under the tabs 12, the composer's line 24). It does not depend on the agents, the runs or
the terminals. 1920×1080: 88, 922. 1280×800: 88, 642. 1024×768: 88, 610. 768×1024: 136, 818. 601×800:
136, 594. Phone 390×844 with a run: 176, 586 (+18, `to supervisor` only).

## What changes in the code

- `teamFit.ts`, new: `fitLabel`, `agentMarks`, `chooseLevel`.
- `Team.tsx`: the head's view of `Team`, `AgentAvatar`, the list, `AgentTip` with its new lines.
- `Sessions.tsx`: `HeadLine` renders the team before `.session-head-actions`; `PhoneHead` stays.
  `Activity` renders the team only on a phone (`usePhone`). `Yours | All` goes to `SessionTabs` as
  `children`, beside `Find`. The terminals' context reaches the head: `SessionHead` stands inside
  `TerminalPanel`, and a portal keeps context. `SessionView` already watches `agents` and `runs`.
- `Composer.tsx`: the wrapper `.composer-frame`; `to` only for an agent other than the supervisor;
  on a phone no empty line.
- `Terminals.tsx`: `StripAgent` shows `agentMarks`.

## The head, left to right

Session dot, project and `/`, title, status words, run time, branch, team (`margin-left: auto`),
actions, line, link. With a team `.session-head-actions` has `margin-left: 6px`, so 16 px from the
team to Stop with the bar's gap of 10. Without a team all is as today.

## Levels (`data-fit`, as the tabs have)

| Level | View | Moves on when |
|---|---|---|
| 0 | `Team`, branch, run time, whole names | the row or the title's limit does not fit |
| 1 | no word, branch or run time; `k` from the longest stem down to 4; chevron `All N agents`; gaps 6 and 4 px, chip padding 7 px, dot gap 5 px | at `k = 4` the row or the limit does not fit |
| 2 | avatars, chevron | the row does not fit |
| 3 | the first `v` avatars, `v` from N−1 to 0, button `+M` | last |

The title's limit: first 24 characters, or the whole title when shorter. Measured results: design.md,
D5. They replace the "verified results" of the designer's spec, its findings F13 included. At
level 3 the trial counts the button with its diamond even when nobody waits, so a status change needs
no new trial. At `v = 0` the button shows the Agents icon and the number, no plus.

## `fitLabel(name, k, names)`

1. Tail: `[-_.]<digits>` at the end, else empty. A stem of at most `k`: the whole name. Else
   `stem[0:k]…tail`.
2. Labels alike of names that were cut: the tail is the last word after `-`, `_` or `.`.
3. Still alike: `·2`, `·3` after the later one, as the sessions' badges.

The font is mono. `aria-label` always has the whole name.

## `agentMarks(names)`

Over the whole team.

1. First letter in capitals and the tail's number when it has under 3 digits (`D2`, `S`); otherwise
   the last 3 digits (`042`).
2. Marks alike: first letter and the first letter at which the group's stems part, `-`, `_`, `.` left
   out, then the number: `FL`, `FD`, `TA`, `TB`, `DS`, `DV`.
3. Still alike: a digit after the later one (`AB`, `AB2`).

## Components and states

| Component | Default | Hover | Focus | Pressed | 
|---|---|---|---|---|
| Chip | `.team-chip`, 24 px | `--raised` | ring by `:focus-visible` | terminal shown: frame `--action` |
| Avatar | `.strip-agent`, 24×24, 10.5 px, `avatar()` colour, status at its corner on an `outline` of 1.5 px `--panel` | as the strip's | ring with `outline-offset: 5px`, `z-index: 1` | ring 3 px `--action`, gap `--panel` |
| `.team-more` | 24 px, frame `--line`, `+M`, diamond when a hidden agent waits | `--raised` | ring | list open: `--raised`; terminal shown among the hidden: frame `--action` |
| `Yours`, `All` | 26 px, `--muted`, 12 px mono | `--ink` | ring | chosen: frame `--action`, `--panel`, `--ink`, 600 |
| List row | at least 32 px | `--raised` | ring | terminal shown: `--raised`, `aria-current` |

## The popup

The tooltip's behaviour stays. Lines: name (`.tip-agent`, mono 600); status in words and the time
from `since`; `role · provider`; `flow <run>`; `Click to open the terminal`. Waiting: the second line
in `--human`.

## The list

`role="dialog"`, name `Team`, 320 px, at most the window less 32 px, under the button at its right
edge, scrolling inside. Heading `Team · N agents`. Each run under a dashed line in its colour; its
name is a link to its page. Row: mark, whole name, status in words. Closing and focus as Details.

## Yours | All

Word `Messages`, 12 px mono, `--muted`, `aria-hidden`. Tooltips by the spec's words. Storage as
before. Measured: bar 1088 and 866 px level 0 with the word; 672 px level 0 without it (with one count
fewer it keeps the word, D7); column 528 and 502 px level 1; 601 px level 2.

## The composer

- Above a phone `.composer-meta` is `position: absolute; top: calc(100% + 1px)`, 14 px, one line;
  `.composer-to` at most 60 % wide, not cut before that; the hint is cut with "…".
- `to <agent>` comes only on an agent's page; that page scrolls, so its line stays in the flow.
- Below 560 px of column the existing rule hides the hint.
- The hint's words lose "to attach": `Enter to send · Shift+Enter for a new line · paste or drop files`.

## Widths

| Window | Head | Behaviour |
|---|---|---|
| Phone 390 | no team | the team row, 24 px chips, 35 px tabs, 36 px icon; no `to supervisor` |
| Tablet 768 | 708 px | level by the team and the title, Stop with no word, the link a dot; Yours \| All in the bar |
| Computer 1440 | 1380 px | 4 agents whole; 12 agents as avatars |

On touch a button has no tooltip, so levels 1 to 3 always have the list button.

## Accessibility

Tab order: Skip to chat, project, title, team, Stop, link. Targets 24×24 with 4 px between
(WCAG 2.5.8); a run's link 20×20 passes by the spacing exception. Contrast of marks on `--panel`:
`--done` 5.3:1 and 8.4:1, `--human` 5.0:1 and 8.2:1, `--muted` 6.1:1 and 6.6:1. Chosen frame
`--action` on `--raised` 5.0:1 and 6.0:1. Statuses read by shape and contrast, no pulse needed.

## Not shown in the mockup

The title's field beside the team; the branch at 1600 px except on 1920; the Agents tab. Design QA
checks them, and whether `Yours | All` reads with no word (critique F10).
