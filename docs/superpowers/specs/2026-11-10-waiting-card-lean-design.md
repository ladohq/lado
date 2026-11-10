# The waiting card, 0.44's look with fewer words (LAD-266)

Change: `openspec/changes/waiting-card-lean/` (proposal with AC-1..AC-13, deltas of
`chat-question-card`, `lead-recommendation`, `phone-layout` and `flows-overview`, `design.md`
with D1-D16). This document is the human's view. Source of the look: the session artifacts of
gate-ui, run `ui-design/gate-card-lean-3`: `spec` (the build's rules, §1-§13), `design-system`
(tokens and CSS), `mockup.html` (each section 0.44 beside the proposal), `brief`, `critique`;
background: `ui-review/gate-card-audit/critique`. The spec, the design system and the mockup are
attached to LAD-266 too.

## What a user gets

In the chat, a gate:

    ┌ ship/x 1 ┐ S supervisor 4                                          — ⤢
    ┃ Build it as planned?                                  (filled head)  ┃
    ┃ the plan is reviewed                                                 ┃
    ┃ Review of the plan … (scrolls, fades at its lower edge)              ┃
    ┃ [The review] [The plan]                                              ┃
    ┠──────────────────────────────── ⋯ ──────────────────────────────────┨
    ┃ ┌ S supervisor recommends Approve                            13:20 ┐ ┃
    ┃ │ The review found no blocker; the plan is small … (4 lines, fade)  │ ┃
    ┃ └──────────────────────────────────────────────────────────────────┘ ┃
    ┃ [Comment for the next step (optional)                             ]  ┃
    ┃ [Approve] [Reject]                                                   ┃

The question stands in a filled head on one line and never scrolls; a cut question ends in "…"
and shows whole in a tooltip (pointer, keyboard focus, a tap). Only the report scrolls, and a fade says
when more is below. The recommendation, the comment and the buttons are always in sight. The
recommendation shows 4 lines of its text (a phone: 2), which scroll on their own; the grip ⋯
gives it more room or less. A recommendation against the step's report has an amber frame and ⚠.
No recommendation, nothing. Documents are chips with their titles. The tab names the run, and its
tooltip names the step and who wrote the report.

An agent's questions: each numbered, parted by a thin line, with their pills, Other… and Skip; a
question without choices shows its field "Your answer" at once; one Send for all.

On Needs you and on a run's page in Flows the same card shows whole: nothing scrolls inside it,
nothing fades, no grip; the page scrolls.

## Place by place

| Place | Report | Recommendation | Grip ⋯ | Footer |
|---|---|---|---|---|
| chat, above 900 px | scrolls, fade | 4 lines, scrolls, fade | yes, with a recommendation | in sight |
| chat, 601-900 px | as above | as above | as above | in sight with the composer |
| chat, phone | as above | 2 lines | yes, a 24 px touch | in sight; a field in focus folds what is around it, as in 0.45 |
| expanded card | as above, more room | as set | yes | in sight |
| Needs you | whole | whole | no | under the report |
| Flows, a run | whole, "Waits for you · N min" in the head | whole | no | under the report |

## Words

New or changed: "supervisor recommends **<option>**", "Your answer", "Comment (optional)" (600 px
or less), the tab's tooltip "step <state>" / "report by <agent>". Only for a screen reader:
"Resize the recommendation", "…, disagrees with the step's report", "…, disagrees with <agent>".

Gone: "Supervisor's recommendation" as a heading, the pill "disagrees with …", "It reads", "The
supervisor gave no recommendation" (in the card; `lado answer` keeps it), "more"/"less", "↓ more",
the meta "ship/x · check · gate #n" beside the question, "Gate #n · run · state" on a run's page,
a chip's size, the tooltips of both grips, "Skip question" (Skip is a pill again), and on a
computer the composer's line "Answering question #n above · Write to supervisor instead".

Gone too: the whole question repeated first in the report when its line is cut.

Unchanged: the loop limit's "loop limit reached at …: what next?", Continue, Cancel run; "Send
<n> answers to <agent>", "<k> of <n> answered", "Choose an answer first", "Skip", "Other…"; the
feed's lines; the document panel; minimize, expand and the card's edge; the phone's keyboard.

## Tokens

`--human-head` (#f8e0c9 / #46321f), the head's ground; `--count-ink` (#3d4350 / #c9ced8), a tab's
count. The rest are 0.44's.

## Mock-ups

`ui-design/gate-card-lean-3/mockup.html` (sections 1-10: a gate agreed and against, the document,
the supervisor's questions, a worker's question, the loop limit, Needs you, Flows, a phone, dark).
