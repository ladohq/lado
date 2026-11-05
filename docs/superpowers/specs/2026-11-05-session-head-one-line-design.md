# Session head in one line (LAD-192)

Change: `openspec/changes/session-head-one-line/` (proposal with AC-1..AC-13, the new
capability `session-head`, deltas of `session-title`, `phone-layout` and `projects`,
`design.md` with D1-D13). This document is the human's view. Source of the look: LAD-189
spec §1, frames g1-* in `mockup-session-head.html`; the phone's sheet in
`mockup-phone-details.html`, right-hand frame.

## What a user gets

Above 600 px the head is one line of 48 px at any width:

    ● LADO / Session UI review ▾   1 min   [main]              [■ Stop] | ● live

`main` shows at 1600 px and more. The folder, git, kits, CLI, Rename and Copy link are in
Details, which a click on the title opens under it. On a phone the head stays as it was with
44 px buttons, and its sheet has the same content as Details.

The keyboard gets `Skip to chat` first, then four stops in the head instead of about twelve.

## Width by width

| Window | Project | Stop | Link | Branch |
|---|---|---|---|---|
| 601-900 | yes | icon | dot, tooltip | no |
| 901-1100 | yes | icon and word | dot, tooltip | no |
| 1101-1599 | yes | icon and word | dot and `live` | no |
| 1600 and more | yes | icon and word | dot and `live` | yes |

## Decided with the human

Spec rule: build as written, ask where it differs from the code. Answer #3389, 2026-11-05,
each as recommended: the words of a broken session stay in the line; a click outside on a
field, button or link keeps the focus there; on a computer the status dot is no Tab stop; the
phone's sheet shares the popover's content. Earlier in the task: the record of 2026-10-08 is
cancelled, the double click goes, the branch stays in the line only at 1600 px and more.

## Changes to docs/design/ui.md

- Session head: rewritten for the line and Details; the 2026-10-08 record says it was
  reversed by LAD-192, with the reason (LAD-125's fact and the wrapped line).
- Session title: the table's head row and the "Head" bullet: Rename in Details, no pencil, no
  double click, the focus on the title; the name in Details.
- Phone layout: the sheet's content, the 44 px buttons.
- Look: `--head-h`. The Structure section's "about 90 px" line stays true to the new height.

The spec's §11 also names The waiting card, Terminal panel and `PHONE_QUERY`: their tasks
(LAD-193, LAD-194) update them.

## Checks

See the plan. After the build the design QA (ui-review) checks the frames g1-* and the dark
theme, which the mock-up does not show.
