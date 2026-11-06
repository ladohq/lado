## Context

Spec: LAD-189 spec §5, frames g5-1440 and g5-term of `lad-189-mockup.html`; the human's decisions of
2026-11-06 (answers #4044, #4051, recorded in LAD-196); run artifact `mockup-stopped-session.html`
for what the frames lack (768, 390, sideways, Resume in the head); run artifact
`ui-review/lad-196-mockup/critique`. Root cause and options: proposal, Why. Each size and word:
`docs/superpowers/specs/2026-11-06-stopped-session-bar-design.md`.

Against AGENTS.md: the change lies in the web UI and names no CLI, so it works with every provider
(neutral core). `session.status` stays the one source of "stopped", and Resume stays one action (one
source of truth). A quote kept in the hidden composer is kept, not dropped (no silent drops, D3). No
field, option or API is added (only what is used). ROADMAP.md's coming stages touch nothing here:
the desktop app and ACP keep the same page.

## Decisions

**D1. One Resume action.** `useResume(session)` in `SessionControl.tsx` returns the action, which
opens the Launch window in Resume mode, and `lost`. The head's button and the bar's use it. The
request and its check of the outcome (LAD-195, `resumeAttempt`) stay in the window. Rejected: a
request from the bar, which would need a second outcome check.

**D2. The head by tab.** `actionsOf(session, onActivity)` gives a stopped session `["forget"]` on
Activity and `["resume", "forget"]` elsewhere. `onActivity` comes down from `SessionHead`, which has the tab. Resume in a
stopped session carries `.session-resume-word`, a class of its own, since `.session-action-word`
hides at 900 px and on a phone. `tmux_gone` keeps its icons. The accessible name stays `Resume…`.

**D3. The composer stays mounted.** The bar shows and the composer is hidden through its `folded`
prop, which already hides the form, takes no files and waits with a quote. So a draft, its files and
a quote survive a stop and show after Resume. Composer's `stopped` prop goes: nothing else sets it.
Rejected: unmounting, which loses the draft when a session stops while the human types. Known cost:
Quote in a stopped session shows nothing until Resume; before, it went into a disabled field.

**D4. Files dropped on a stopped chat.** `stopFiles` applies while the composer is hidden for either
reason, so a dropped file is not opened by the browser.

**D5. The feed's text.** `emptyText(stopped, agentMessages)` in `Chat.tsx` is one small pure rule.
The filter is known without a request. Rejected: asking the server whether hidden messages exist.

**D6. `role="status"` on the bar's text.** Spec §9 names the bar. The button stays outside the live
region, so a change of its state is not read out as news.

**D7. The fold is a view of the stored choice.** `stoppedPanel(panel, opened)` in `columns.ts`
replaces `panel` for `fitColumns`: collapsed unless the human opened it here, then `chosen`.
`useSessionColumns` gets the stopped session's name from `Sessions` and keeps `openedIn`, the
session whose terminals were opened, in memory. In a stopped session `open` and `fold` set only that;
`open` sets `last` in memory, and `last` is read back from storage when the session is no longer
stopped. A dragged width is the human's choice and is stored as ever. Rejected: a write and a
restore of `prefs`, which a reload in between would lose.

**D8. No socket for a stopped session.** `TerminalPanel` takes `stopped`, and each tab renders
`StoppedTerminal` instead of `AgentTerminal`: the bar `Viewing` and the text. After Resume the real
terminal mounts and opens its socket; an agent not ready yet takes the existing path of a socket
closed for good, which reopens when the agent changes. A stop ends control and Expand. Rejected:
mapping the 4404 reason, which keeps a failing socket and a string match.

**D9. Team.** A stop deletes the session's agents (`state._stop_session`), so `HeadTeam` renders
nothing already: no code. The status `stopped` in `Team.tsx` belongs to an agent that ended in a
running session and stays. Only `Activity` on a phone changes: `Team` is left out and the toggle
shows its words, 44 px high, with `aria-pressed` and its name as they are. Sideways the row is hidden
as for any session.

**D10. The bar on a phone.** The column rule hangs on `:root[data-phone="tall"]`; `short` keeps the
row with a 44 px button (ui-review, F4), about 62 px instead of 117.

## Risks

- A test or a doc that expects `Resume…` in the head on Activity: `tests/ui/test_launch.py`,
  `test_connection.py`, `test_session_head.py`, `web/src/Launch.test.tsx`, `connection.test.tsx`
  press it there. The plan lists them.
- LAD-218 may touch the head and the tabs in parallel: whoever merges second takes main in.
