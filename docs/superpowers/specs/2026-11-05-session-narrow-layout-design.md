# A session's page on narrow windows (LAD-193)

Change: `openspec/changes/session-narrow-layout/` (proposal with AC-1..AC-19, the new capability
`session-layout`, deltas of `phone-layout`, `chat-question-card`, `session-head` and `projects`,
`design.md` with D1-D14). This document is the human's view. Source of the look: LAD-189 spec §2,
frames g2-*; what the frames lack in `mockup-narrow-layout.html`.

## What a user gets

The chat is never squeezed. Above 900 px it keeps 420 px, and the columns around it fold by
themselves and come back when there is room. At 601 to 900 px a session's page stands still, as a
wide window does: the composer and an open gate are in sight at once. At 600 px and less the phone
layout works with a mouse too.

## Width by width, nothing stored

| Window | Rail | List | Terminals | Chat |
|---|---|---|---|---|
| 1600 and more | 216 | 260 | 40 %, up to 640 | the rest |
| 1440 | 60 | 260 | 448 | 672 |
| 1280 | 60 | 260 | 384 | 576 |
| 1101 | 60 | 260 | 360 | 421 |
| 1024 | 60 | 260 | strip 32 | 672 |
| 1024, terminals opened by the human | 60 | strip 48 | 366 | 550 |
| 601-900 | 60 | row of 48 over the session | strip 32 | the rest |
| 600 and less | Menu | Sessions page | over the screen | the screen |

## How a column folds

1. Terminals nobody opened fold first. Opened by the human, the list folds instead.
2. The one the human just opened stays; the other folds.
3. Still short: terminals narrow to 280 px, then fold. The rail never folds by itself.
4. Room back: the list, then the terminals, return to what the human chose.

The human's choices are stored as before and a fold for room is not, so a reload changes nothing.

## 601 to 900 px

Top to bottom: top bar, session strip, tabs, Team, feed, card, composer. The list and the terminals
open over the session and are not remembered here, so a wide window's choice stays. The card looks
as it did after LAD-194: its footer is in sight, expanded it fills the window under the top bar, and
there is no edge above it. Needs you and the other pages scroll as before.

## Decided with the human

Answer #3750 and the rule on `PHONE_QUERY`: proposal, What Changes. What is left out: proposal, Out
of scope.

## Left for the human

An iPad with its real keyboard, before the merge.
