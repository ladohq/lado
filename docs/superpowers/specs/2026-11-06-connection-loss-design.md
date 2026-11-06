# A lost connection and actions without an answer (LAD-195)

Change: `openspec/changes/connection-loss/` (proposal with AC-1..AC-18, the new capability
`connection-loss`, a delta of `phone-layout`, `design.md` with D1-D14). This document is the
human's view. Source of the look: `mockup-connection.html` of run task/lad-195, which replaces
LAD-189's frames g4-* where they differ.

## What a user gets

One question gets a straight answer: did my decision go through? While the connection is away
the buttons wait instead of failing. If it goes at the moment of a click, LADO says it cannot
confirm the action, looks by itself once it can, and either the card goes or the error says it was
not delivered, with Retry. Nothing else asks for attention: no strip, no green state.

## States

| State | Mark | Buttons that write | Under the buttons |
|---|---|---|---|
| Live, or lost for less than 2 s | live | active | nothing |
| Lost | amber `reconnecting…` (phone: icon) | disabled, the reason beside a gate's, a tooltip on the rest | nothing |
| Lost, a click got no answer | the same | disabled | "Approval not confirmed", Retry disabled |
| Back, LADO is looking | live | that item's disabled | the same, for a moment |
| Back, it reached the server | live | the card goes | nothing |
| Back, it did not | live | active | "Approval not delivered", Retry active |

## Words

| Action | Outcome unknown | Not delivered |
|---|---|---|
| Approve | Approval not confirmed | Approval not delivered |
| Reject | Rejection not confirmed | Rejection not delivered |
| Continue, Cancel run, a choice, Send answer | Answer not confirmed | Answer not delivered |
| Send | Message not confirmed | Message not delivered |
| Stop, Stop and forget | Stop not confirmed | Stop not delivered |
| Resume | Resume not confirmed | Resume not delivered |

Nothing else stands beside them, and there is no "Checking…". A locked button says "Waiting for
connection". A request with no answer anywhere else reads "No connection"; a file, "<file> was not
uploaded: no connection." The mark keeps `reconnecting…`.

## How the outcome is found

| Action | Read | Reached when |
|---|---|---|
| A gate's button | the session's gates | the gate has an answer or is gone |
| Send answer | what waits | none of the questions sent is there |
| Send | the messages after the click | one from the human to that agent, same text and files |
| Stop | the sessions | stopped or gone |
| Resume | the sessions | running |

## What the human decided against spec

No strip anywhere, F44 withdrawn. No "Connection restored." and no green mark. Tooltips, not a line,
at Send. The mark changes after 2 s together with the buttons. The raw exception goes to the
console only. Short error texts with nothing beside them. An edited field is not cleared. Stop and forget never forgets on its own.

## For the ear

One status region always stands in the top bar, read out and not shown. Its words are the mark's, so
the loss and the return are heard even though the mark's element is swapped.

## docs/design/ui.md

The change feed: `lost`, the mark, reads that recover. Session head and Phone layout: the mark's
state. The waiting card, Composer, Launch and session control: the lock, the block, Retry. A new
section "A lost connection" holds the rule and the words; the others point to it.
