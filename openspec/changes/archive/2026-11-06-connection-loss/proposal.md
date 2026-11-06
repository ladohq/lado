Task: LAD-195

## Why

Symptom (audit of LAD-189, finding F15): with the server away, Approve, Reject, Send and Stop
stay active, the only sign of it is a grey "reconnecting…" in the corner, and a click ends in a
raw `TypeError: Failed to fetch` under the buttons. The human cannot tell whether the approval
went through, and the line stays after the connection is back.

Cause: `api.ts` lets `fetch`'s rejection through, and every caller prints it with
`String(error)`, so "no answer" looks like any refusal. An action keeps nothing but that string
in its component, so nothing can look at the outcome later. The change feed's state (`link`)
reaches only the top bar; no button reads it. A resumed stream replays changes without a reset,
so a list that failed while the server was away stays failed, and a reload that fails replaces
what was loaded, which takes the open gates and with them the comments.

Options weighed:

- A: each place handles its own failure (the card, the gate's panel, the composer, Stop, Resume).
  No new module; five copies of one rule, and a gate shown in the chat, on Needs you and on its
  run's page would each know a different story.
- B (taken): one store of actions without an answer, keyed by what they act on, that holds how
  to look at the outcome and how to repeat the action, and settles them itself. The places only
  show it. It costs one module, and it is the only option in which an error survives a change of
  page and shows the same wherever the gate shows.
- C: an idempotency key on the server, which would settle Send for good. The human decided
  against it (task comment of 2026-11-05): the server does not change, and it can come back if
  duplicates appear.

## What Changes

- A status region that is always in the page reads the loss and the return out: today the region
  comes with the loss, which screen readers announce unreliably.
- The Live mark turns into an amber `reconnecting…` with an icon (the icon alone on a phone) 2 s
  after the feed is lost; a shorter drop shows nothing. When the connection is back, plain Live
  returns, with no green state.
- From that moment Approve, Reject, Cancel run and a gate's other buttons, Send answer, Send,
  Stop, Stop and forget and Resume are disabled. Fields stay active and keep what is in them.
  "Waiting for connection" stands beside a gate's buttons; the others say it in a tooltip.
- A request that got no answer shows under its buttons "Approval not confirmed" with a disabled
  Retry. Once LADO can read the
  state it settles the action: it reached the server (the error goes, the card goes by the live
  lists), or it did not ("Approval not delivered" with an active Retry). The connection coming back alone never clears the error.
- Send is settled by the feed: a message of the human with the same text and files after the
  click. Found: the error goes and an unchanged field is cleared. Not found: Retry.
- A Retry refused because the item is closed already counts as closed: `gate #N is closed
  already`, `question #N is stopped` and the like, `is stopped already`, `is already running`.
- No raw exception text anywhere in the UI: a request without an answer reads "No connection"; the exception itself goes to the browser's console.
- A reload that fails keeps what the page shows, and what failed while the server was away loads
  again when it is back.

## Scope

In: the web UI (`web/src/`), `docs/design/ui.md`, CHANGELOG.md. No API, schema, MCP or CLI change.

Out of scope:

- The strip "Connection to LADO lost" of spec §4 and the short phone strip of decision F44: the
  human dropped both (task comment of 2026-11-06). The head is on every page, so the mark does
  the job, and a strip would need a place on each page.
- "Connection restored." and the green mark of 3 s: dropped by the human too; Live coming back
  and the buttons waking say it.
- The browser's errors in `errors.jsonl`: only the server writes that journal and it is away at
  that moment; spec §4's "and the error journal" cannot be done, the human settled on the console.
- Any sentence beside an error's two words, and a "Checking…" state: the human chose the short texts
  (decision of 2026-11-06).
- A retry key for Send: decided against, see option C.
- A timeout on requests: a `fetch` on a dead network hangs until the browser ends it, and Stop
  and Resume may rightly take long; the button stays busy as it does today.
- Forget, Rename and the other writes outside spec §4's list: they are not locked. Their errors
  read as human text through the same `api.ts` rule.
- A stopped session's look (LAD-196), touch targets on an iPad (LAD-216).
- Keeping drafts across a change of tab: they live in their components, as today.

## Acceptance criteria

- AC-1: the server stops: 2 s later, not before, the mark reads `reconnecting…` on amber at 1440,
  and is an amber icon named `reconnecting…` at 390. No strip shows on any page.
- AC-2: a drop shorter than 2 s changes nothing on the screen.
- AC-3: the server is back: plain Live, no green state, and the buttons are active.
- AC-4: while lost: a gate's buttons in the chat, on Needs you and on a run's page, Send answer,
  Send, Stop, Stop and forget and Resume are disabled; Enter in the composer sends nothing; fields
  keep and take text.
- AC-5: "Waiting for connection" stands beside a gate's buttons; hovering Send, Send answer,
  Stop or Resume shows it in a tooltip.
- AC-6: a request without an answer for a gate, an answer to questions, Send, Stop and Resume
  shows its "<What> not confirmed" under the buttons with Retry disabled, and no raw text.
- AC-7: back, gate closed: the error and the card go, the answer is in the feed.
- AC-8: back, gate open: "Approval not delivered", Retry,
  Approve and Reject active. The same for the other actions with their words.
- AC-9: the error goes only by AC-7, a successful Retry or another decision on that item.
- AC-10: a gate's error shows the same in the chat, on Needs you and on its run's page, and
  survives going from one to the other.
- AC-11: Send answered but the answer lost: no duplicate, the error goes, the field is empty; had
  the human changed the text meanwhile, it stays.
- AC-12: Retry refused with `gate #N is closed already` or `question #N is stopped` counts as
  closed: no error shows.
- AC-13: a refusal with an answer (4xx with its text) shows as it does today.
- AC-14: no `TypeError` or `Failed to fetch` shows anywhere in the UI, in the top bar's tooltip
  and a page that failed to load included; the console has it.
- AC-15: a list that failed while lost loads when the connection is back; a failed reload leaves
  the feed, the card and its comment in place.
- AC-16: Stop and forget with its answer lost never forgets by itself.
- AC-17: the loss and the return are read out from a `role="status"` region that stands in the DOM
  all the time.
- AC-18: the light and the dark theme pass design QA against `mockup-connection.html`.

## Impact

`web/src/`: `api.ts`, `live.ts`, a new `attempts.ts`, `GateCard.tsx`, `WaitingCard.tsx`,
`waitingParts.tsx`, `Composer.tsx`, `SessionControl.tsx`, `Launch.tsx`, `Shell.tsx`, `icons.tsx`,
`styles.css`. `docs/design/ui.md`: The change feed, Session head, The waiting card, Composer,
Launch and session control, Phone layout. CHANGELOG.md: one item under `## 0.45.0 (unreleased)`.
A user-visible behaviour, so a minor by AGENTS.md's rule; 0.45.0 is already the open minor, so
no version moves. Every provider alike: nothing here is below the UI.
