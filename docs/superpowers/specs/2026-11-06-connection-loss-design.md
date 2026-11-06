# A lost connection and actions without an answer (LAD-195)

Change: `openspec/changes/connection-loss/` (proposal with AC-1..AC-17, the new capability
`connection-loss`, a delta of `phone-layout`, `design.md` with D1-D12). This document is the
human's view. Source of the look: `mockup-connection.html` of run task/lad-195, which replaces
LAD-189's frames g4-* where they differ.

## What a user gets

One question gets a straight answer: did my decision go through? While the connection is away
the buttons wait instead of failing. If it goes at the moment of a click, LADO says it cannot
confirm the action, looks by itself once it can, and either the card goes or the error says the
action did not arrive, with Retry. Nothing else asks for attention: no strip, no green state.

## States

| State | Mark | Buttons that write | Under the buttons |
|---|---|---|---|
| Live, or lost for less than 2 s | live | active | nothing |
| Lost | amber `reconnecting…` (phone: icon) | disabled, the reason beside a gate's, a tooltip on the rest | nothing |
| Lost, a click got no answer | the same | disabled | "Couldn't confirm your approval was sent. …", Retry disabled |
| Back, LADO is looking | live | that item's disabled | the same, for a moment |
| Back, it reached the server | live | the card goes | nothing |
| Back, it did not | live | active | "LADO did not receive your approval. The gate is still open.", Retry active |

## Words

| Action | `<what>` | Ending when it did not arrive |
|---|---|---|
| Approve | your approval | The gate is still open. |
| Reject | your rejection | The gate is still open. |
| Continue, Cancel run, a choice | your answer | The gate is still open. |
| Send answer | your answer | The question is still open. |
| Send | your message | It is still in the field. |
| Stop, Stop and forget | your stop request | The session is still running. |
| Resume | your resume request | The session is still stopped. |

Both messages start the same way: "Couldn't confirm <what> was sent. LADO will check when the
connection is back." and "LADO did not receive <what>." A request with no answer anywhere else
reads "LADO cannot be reached".

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
console only. An edited field is not cleared. Stop and forget never forgets on its own.

## docs/design/ui.md

The change feed: `lost`, the mark, reads that recover. Session head and Phone layout: the mark's
state. The waiting card, Composer, Launch and session control: the lock, the block, Retry. A new
section "A lost connection" holds the rule and the words; the others point to it.
