## Context

`WaitingCard.tsx` keeps `expanded` in its state. Folded, it renders the card `<section
class="waiting-card">` in place: in the chat between `.chat-feed` and `Composer`
(`Chat.tsx`), on Needs you in each `.waits-session` (`NeedsYou.tsx`). Expanded, it
renders the same section with `.expanded`, `role="dialog"` and `aria-modal`, wrapped in
`.waiting-overlay` (`position: fixed; inset: 0; z-index: 50`, `--scrim`) through
`createPortal(…, document.body)`. Esc (a `keydown` listener on `document`) and the
collapse button fold it.

`ArtifactPanel.tsx` is rendered by `SessionView` (`Sessions.tsx`) when the address has
`?view=<record>` (`paths.VIEW_PARAM`): `.panel-scrim` (fixed, z 30) and `.artifact-panel`
(fixed, z 31). Its own Esc listener on `document` deletes `view`, and the focus goes back
to its opener. `Attachments.useView(session)` opens a record: on that session's page it
sets `view`; elsewhere (Needs you) it navigates to the session's Activity tab with `view`.

So a chip in the expanded card sets `view`, the panel renders at z 31 under the card's z 50,
and Esc folds the card and closes the panel at once (both listeners run).

Options (mockup `mockup-expanded-card.html`): A, the card in the chat's whole area (chosen);
B, in the feed's place with the composer under it. Held against ROADMAP.md: the desktop
stage runs the same UI; nothing coming changes the waiting card. Design principles: one
source of truth (one card component, one panel component, one `view` parameter), only what
is used (no new option), neutral core (UI only, no provider).

## Decisions

- **D1. Expanded in place, by CSS on the host.** No portal and no `.waiting-overlay`: the
  section stays where it is and gets `.expanded`. The host hides its other children while
  it holds an expanded card: `.chat:has(> .waiting-card.expanded)` hides `.chat-feed` and
  `.composer`, and the card takes `flex: 1`, no `max-height`, no `max-width`, no centring
  margin; `.needs-you:has(.waiting-card.expanded)` hides every `.waits-session` without
  one and the `.waits-item` rows, and the expanded one's section fills the content's
  height (`.content` is a flex column there). Why: the panel and its scrim are fixed over
  the page, so they cover an in-page card with no z-index to keep in step; the page around
  stays as it is. `:has` is in every browser the UI supports (it is used already in
  `styles.css`).
- **D2. Not a dialog.** The expanded card drops `role="dialog"` and `aria-modal`: the page
  around stays usable, so it is no modal. It keeps its `aria-label` ("What waits for you in
  <session>"); the expand button gets `aria-expanded`. Opening still moves the focus to the
  shown tab, folding back to the expand button.
- **D3. Esc closes the topmost.** The card's Esc listener does nothing while the address has
  `view` (a panel is open, over any page): the panel's own listener closes it. The card
  reads it with `useSearchParams`. Why not `stopPropagation` in the panel: both listen on
  `document`, and their order is the order they were added.
- **D4. The panel over Needs you.** A new address parameter `paths.VIEW_SESSION_PARAM`
  (`session`). `useView(session)`: on that session's page as now; on Needs you (the route
  `/needs-you`) it sets `view` and `session` (a step of the history, as in a session);
  anywhere else it navigates to the session's Activity tab as now. `NeedsYou` renders
  `<ArtifactPanel session={…} record={…} />` when both are in the address. `ArtifactPanel`'s
  close deletes `view` and `session` both. Its Open latest uses `useView` and so stays on
  Needs you; Open in Artifacts tab is a link to the session's Artifacts tab as now.
- **D5. A narrow window.** At 900 px or less the page scrolls, so the chat has no height of
  its own: the expanded card gets `min-height` of the window's height less the top bar
  (`100dvh` less its height) and the page scrolls to it on expand (`scrollIntoView` of
  the card, block start, with a `scroll-margin-top` of the sticky top bar's height). On a wide window the chat's height bounds it.
