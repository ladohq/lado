## Context

Spec: LAD-189 spec §1 and frames g1-* (run artifact `mockup-session-head.html`); the human's
rule is to build it as written and to ask where it differs from the code. The four
differences are settled in the proposal. Root cause and options: proposal, Why. Against
AGENTS.md: the change is above `providers/` and names no CLI (neutral core); the facts have
one component (one source of truth); a kit's problem and an untested CLI keep their marks in
Details (no silent drops); no option or field is added (only what is used).

## Decisions

**D1. One content, two frames.** `SessionDetails.tsx` gets `SessionFacts`: state line, facts
and actions. `SessionDetails` stays the phone's modal `<dialog>` around it, with × and the
title field in the sheet; `DetailsPopover` is a `div role="dialog"` around it. `onRename` is
the one difference: the sheet edits in its head, the popover hands over to the line.
`GitFact` loses its Copy, which moves to the grid's third column. Rejected: a second
component for the popover, which is how a phone and a computer would come to differ.

**D2. The popover is placed like Stop's.** `useBelow` under the title's button, `useDismiss`
with a box that holds the button and the popover, so a second click toggles. It stays inside
the top bar's stacking context (z-index 10), so it lies over the terminals. Not a native
`popover` or `showModal`: the spec wants no trap, and the UI has one way already.

**D3. `useDismiss` hands the event to `close`.** The head's `close` focuses the title unless
the press was on `a, button, input, textarea, select, [contenteditable]`. A second click
focuses the title itself, as Safari does not focus a clicked button. Other users of
`useDismiss` ignore the argument.

**D4. Rename goes through `useTitleEdit`,** its focus target now the title's button. In the
head `.title-edit`'s hint lies absolutely under the line; otherwise the field would make the
bar higher. Field font 18 px, as the title.

**D5. Skip to chat is drawn by the page into a second slot.** The Shell knows nothing of
sessions (docs/design/ui.md), so it gets a slot as its first child, as `useTopBar`, and
`SessionHead` portals the link there; other pages have none. On Activity it focuses
`.chat-feed` (`tabIndex={-1}`); on another tab it navigates with `state: {focusChat: true}`
and `Chat` focuses on mount. Shown on a phone too: a keyboard can be there.

**D6. Heights.** `--head-h` goes into `styles.css`'s `:root` beside `--ring-room`. `.topbar`
takes `min-height: var(--head-h)` on every page, not only a session's: 52 to 48 px on each
step between the Sessions page and a session would jump. `:root[data-phone]` keeps its 52 and
44 px. The `52px` of the two `calc(100vh - 52px)` blocks and `scroll-margin-top` become the
variable. Removed: `.session-meta`, `.session-rename`, `.session-name-id` in the head, and
the wrapping half of the `max-width: 1100px` block.

**D7. Shrinking.** By `flex-shrink` weights, largest first: `h1` (`min-width: 8ch`), the
project (`max-width: 16ch; min-width: 4ch`), the words and the run time (`min-width: 0`).
Actions, line and link are `flex: none`. A stopped session's long run time (`stopped 2 d ago · ran 4 h`) is why the time must be able to
cut. The title keeps its `title` attribute, as the h1 has it now.

**D8. The branch** is CSS (`@media (min-width: 1600px)`), from `about.repos[0].branch`, at
most 24ch with "…" so that a long branch cannot break AC-1. The spec gives no cap; the line's
rule needs one. Its `Tooltip` has no `tabIndex`: no fifth stop.

**D9. Stop's word** is a span in `SessionActions`, for the action `stop` only, hidden by CSS at
900 px and less and on a phone; `aria-label` stays. Resume and Forget stay icons (LAD-196).

**D10. The status dot** takes a prop for its stop: `PhoneHead` keeps `tabIndex={0}` for the
tap's tooltip, `HeadLine` drops it. Its `role="img"` and name stay.

**D11. The link's tooltip** is chosen by `max-width: 1100px` in `LiveButton`, on every page,
as it does not know the page; only for `live` with no update. The host is then no longer in
the tooltip on a narrow window; the system panel has it.

**D12. Phone sizes** (spec §9): Menu and `.session-head-actions .icon-button` 44×44; a stopped
session's two actions leave the title less room, which it takes with "…".

**D13. No API change.** `SessionAbout` has every fact; `make web-types` stays clean. The
breadcrumb comes from `about.project`, as the spec says, so it appears when the about comes,
and is absent when the about fails, like the other facts.

## Test layers

UI only, nothing crosses processes, so no integration test: vitest for logic and DOM, UI e2e
for what needs a browser (measured heights, real focus, media queries). The plan names them
per requirement.

## Risks

- Facts need one click more. Accepted by the human; the branch stays at 1600 px and more.
- LAD-193 and LAD-195 touch the same bar: this change leaves `LinkState` and `PHONE_QUERY`.
- The dark theme has no frame: the design QA after the build checks it.
