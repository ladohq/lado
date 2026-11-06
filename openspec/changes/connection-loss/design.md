## Context

Spec: LAD-189 spec §4 (task LAD-195), as the human changed it: no strip, F44 withdrawn, no green
state, the texts and rules of the task comment of 2026-11-06, the Send rule of 2026-11-05, and the
run artifact `mockup-connection.html`, which replaces frames g4-* where they differ. Root cause
and options: proposal, Why. Against AGENTS.md: nothing here is below the UI, so it works with
every provider (neutral core); the outcome is read from the server's lists, the store keeps no
copy of a gate (one source of truth); an action with no answer is never dropped silently, which
is the task itself; no API, field or option is added (only what is used). ROADMAP.md's coming
stages leave this alone: Stage 7's desktop app talks to the same server, and D2 and D3 serve it as
they are.

## Decisions

**D1. A request with no answer is a kind of its own.** `api.ts` wraps each `fetch` (`get`, `post`,
content, upload, `probeStream`) so that a rejection becomes `Unreached`, an `ApiError` of status 0
with the text `No connection`, after `console.error` of the original. Every
`String(error)` of the UI then prints that text with no change at the callers. An `AbortError`
passes through untouched: the artifact views abort on purpose. Rejected: a helper at each of the
twenty callers. The text has no final stop. `uploadFiles` builds its own sentence, so on `Unreached` it writes the
reason in lower case and adds the stop: `<file> was not uploaded: no connection.`

**D2. `lost` in the store.** `LiveState.lost` turns true `LOST_AFTER_MS = 2000` after `link` becomes
`down` and false the moment it opens. One timer in `Live`, so the mark and every button change
together. `refused` never counts as lost. While `link` is `down` and `lost` is false the mark still
reads live: `LinkState` reads `lost`, not `link`. Spec gave the delay to the strip only; the human
extended it (2026-11-06). A click in those 2 s fails and takes D3's path, which is safe.

**D3. One store of attempts.** New `web/src/attempts.ts`: `Attempts`, held by `Live`, its map in
`LiveState.attempts`, read by `useAttempt(key)`. An attempt is `{ what, state, repeat, look, closed, reached }`: `state` is `unknown`, `missed` or `{ refused: string }`; `repeat()` sends
the action again from what was pressed, so it needs no panel; `look()` answers `reached` or
`missed`; `closed(text)` says a refusal means closed (D6); `reached()` is the owner's work at the
end (D5). A failed action calls `attempts.failed(key, attempt)` on `Unreached` only. Keys:
`gate:<session>:<id>`, `questions:<session>:<agent>`, `send:<session>:<to>`, `stop:<session>`,
`resume:<session>`. The store, not the panels, so a gate's error survives a change of page and
shows the same on Needs you and in Flows (AC-10), and the look runs with no panel mounted. Rejected:
per-component state (proposal, option A). A new press on the same key replaces the attempt.

**D4. When LADO looks.** At once when the attempt is made, on each `open` of the feed, and every
`RETRY_MS` while `link` is `open` and attempts stay `unknown`. A look that ends in `Unreached`
leaves it `unknown`. Reading through REST rather than waiting for the feed: a resumed stream has
no end-of-replay marker, so no moment says the lists are current. `look` by kind: gate, `getGates`,
reached when it has an answer or is gone; questions, `getWaiting`, reached when none of them is
there (a stopped session's questions are stopped, so absent is right); Send, D5; Stop, `getSessions`,
reached when stopped or gone; Resume, reached when `running` or `loop_down`, the attempt dropped
when the session is gone.

**D5. Send's look.** `Live.lastMessage(session)` gives the highest id among the session's watched
windows; the composer takes it before the upload. Both composers stand under a window that holds
every human message of their kind. `look` is `getMessages(session, { after })`, then a message with
`from` human, `to` the target, `(body || summary) === text.trim()` (the server keeps the whole
text in `body` unless the summary is exactly it) and the same attachment names. Ids, not the time
of the click: the phone's clock is not the server's, and spec's "after the click" means this.
`reached` clears the field by `setText((now) => (now === sent ? "" : now))` and releases the files
sent. With no window loaded the cursor is 0, a false match only for a Send before the page loaded.

**D6. What counts as closed.** The refusals are status 400 with the core's text, so
`attempts.ts` matches them, and `web/src/closedRefusals.cases.json` pins both sides as
`messageFilter.cases.json` does: vitest runs the patterns, and a pytest makes the refusals through
`runs`, `state.reply_to_questions`, `runtime.stop_session` and the resume path and checks each text
against the table. A change of wording then fails a test instead of showing an error. Only a Retry
reads them: a first click keeps today's refusal, as spec says.

**D7. The block.** `ActionProblem` in `waitingParts.tsx`: `--danger-ground`, the alert icon, bold
first sentence, Retry at the right; `role="alert"`; on a narrow row it wraps under the text. Used
under the buttons of `GatePanel` (both shapes), `AgentPanel`, the composer, the Stop popover and
the Launch window's Resume. `.field-problem` stays for refusals. While an item's attempt is
`unknown` its buttons stay disabled also with the connection back, for the moment of the look. In
a stopped session Retry follows the buttons: disabled, with `STOPPED_NOTE`.

**D8. Disabled with a tooltip.** React sends no `mouseenter` to a disabled button, so `Tooltip`
cannot sit on it: a small `Waits` wrapper puts the button in a `span` that carries the tooltip while
lost, and the button gets `pointer-events: none` then. `disabled` stays real, as spec says; the
keyboard loses the stop, and D13's region announces the loss. Disabled look: opacity
.45 and `cursor: not-allowed` on the span's button, added for `.primary`, `.quiet`, `.danger`,
`.send` and `.icon-button`, without changing how other disabled buttons look.

**D9. The mark.** `LinkState` while lost: `.link.reconnecting` with `NoNetworkIcon`, `--warn-ground`,
`--warn` 600, the word; the `::before` dot goes. The reason leaves the line for
the tooltip, and only a reason the server answered: `diagnose` sets `problem` to null for
`Unreached`. `.reconnecting-why` goes. On a phone the word is hidden as `.link-word` is and the
target stays 44×33. Live's own button is untouched; spec's first three rows are what it does today.

**D10. Reads keep what they have.** `loadList`, `loadWaiting`, `reloadWindow` and `load` keep the
loaded value when the new load fails and one exists; the error shows only when there is nothing
to show. Without this a failed reload empties `gates` and `WaitingCard` prunes the comments. On
`onopen` after a loss, `Live` loads again each list, window, `waiting` and `sessions` that holds an
error; a resumed stream sends no reset, so nothing else would.

**D11. Stop and Resume.** Both stay in their places: `StopPopover`, under its buttons, and the Launch
window's Resume, under its buttons. `reached` closes the popover; for Resume it closes the window
and opens the session's page, with no `Started` to show. Stop and forget's stop takes the attempt of
Stop, so Retry and the look know nothing of the forget (AC-16). A lost answer of its forget step
is a plain `No connection` in today's `busy="stopped"` state. New session's Start is not
locked: it is not in spec's list.

**D12. Facts spec has otherwise.** On a network error the browser itself reconnects the
`EventSource`; `RETRY_MS` paces only a stream the server closed. No visible difference, and no
button either way. A session stopped while the server was away leaves its gate open with the
buttons off by `stopped`: the error says the truth and waits for a resume.

**D13. One region for the ear.** `LinkState` renders a `.visually-hidden` `role="status"` span
before everything else and before its `refused` return, so it stands from the first paint. Its
text is the mark's word (`live`, `connecting…`, `reconnecting…`), no new text; refused, it is
empty, as the page's alert says why and "live" would be false. `role="status"` leaves
`.link-word` and `.link.reconnecting`: those elements swap at the loss, and a live region that
enters the DOM with its text is announced unreliably. `get_by_role("status")` of the tests finds
the region, with the same text.

**D14. The words.** The human's short texts: `<What> not confirmed`, `<What> not delivered`, nothing
beside them. `what` is the attempt's capitalised noun, and both strings are built from it. There is
no "Checking…": `unknown` shows "not confirmed" until the look ends.

## Risks

- A `fetch` on a dead network can hang for long before it rejects; the button says busy meanwhile.
  Out of scope (proposal).
- A Stop that takes long may look `missed` for a moment while the server still works; Retry then
  meets `is stopped already`, which D6 takes as closed.
