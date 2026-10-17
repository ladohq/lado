## Context

What the web UI does on a small screen now (main at 0.40.0):

| Piece | Where | Today |
|---|---|---|
| App shell | `styles.css`, `@media (min-width: 901px)` | a wide window never scrolls, its regions do; a narrow one is a page the window scrolls |
| Rail | `Shell.tsx`, `prefs.storedRailCollapsed` | collapsed to 60 px of icons on a window narrower than 900 px |
| Session head | `Sessions.tsx` `HeadLine`, drawn into the top bar (`Shell.useTopBar`) | dot, title, Rename, run time, folder, git, kits, CLI, Copy link, Stop; wraps to three lines at 390 px |
| Session list | `Sessions.tsx` `Sessions`, `SessionStrip` | a strip of initials on a narrow window; the Sessions page says "Select a session" |
| Chat | `Chat.tsx`, `WaitingCard.tsx`, `Composer.tsx` | the feed scrolls by itself only in a wide window; the card's edge and its `NARROW` scroll-into-view are for the window that scrolls |
| Terminals | `Terminals.tsx` | a panel collapsed to a strip at first on a narrow window; Expand shows it over the page |
| Tooltip | `Tooltip.tsx` | shows on a mouse's hover or the keyboard's focus; touch never |
| Touch rules | `styles.css` `@media (hover: none)`, `SelectionBar.tsx` `TOUCH` | the copy buttons always shown, the selection bar below the selection |

Root cause: the narrow rules are a computer's narrow window, not a phone: the window
scrolls as a page, nothing is hidden, the head wraps.

## Options

1. **Tune the existing `max-width: 900px` rules.** Cost: CSS only. But a computer's narrow
   window changes too (the human's condition: the computer's design must not suffer), and
   CSS alone cannot move the head's facts into a sheet or the rail into a menu.
2. **Chosen: one phone layout, by pointer and size, in CSS and a few components.** Cost: a
   query and its hook, a menu, a compact head with a details sheet, CSS of the phone
   gathered in one block. A computer with a mouse never matches, so it is unchanged by
   construction.
3. **A separate mobile UI** (its own routes and pages). Cost: a second copy of each
   screen, drifting with every change. Turned down by the human.

Held against AGENTS.md's Design principles and ROADMAP:

- **Neutral core**: the UI only; no provider, server or API change.
- **One source of truth**: the phone's media query is written once, in `phone.ts`; CSS keys
  off the `data-phone` attribute the hook sets on `<html>` (D1), never a second copy of the
  query. The compact head and the sheet reuse the head's pieces (D3).
- **No silent drops**: what leaves the screen on a phone is reachable: the rail in the
  menu, the head's facts in the sheet, tooltips on a tap, the terminal over the screen.
- **Only what is used**: no setting, no new API; one attribute, one hook.
- ROADMAP stage 7 (the desktop app and its web UI); the coming task "a terminal on a
  phone" builds on D7.

## Decisions

### D1. One query in `phone.ts`, CSS by `data-phone`

`web/src/phone.ts` holds `PHONE_QUERY = "(pointer: coarse) and (max-width: 600px),
(pointer: coarse) and (max-height: 500px)"` and `SHORT_QUERY = "(max-height: 500px)"`,
and `usePhone(): "tall" | "short" | null` (matchMedia with change listeners). The Shell
sets `document.documentElement.dataset.phone` to `tall` or `short`, and removes it, from
the hook. All phone CSS is under `:root[data-phone]` (sideways under
`:root[data-phone="short"]`) in one section at the end of `styles.css`, "Phone layout".
**Why:** `pointer: coarse` keeps every computer out whatever its window; one place for the
query, and the CSS of the phone can be read and removed as one block.

### D2. The rail as a drawer

The same `<nav class="rail">` with `data-open` while the menu is open; in the phone layout
it is `position: fixed`, 260 px, over a scrim button ("Close menu") that dims the page.
The Shell's top bar gets a Menu button (`MenuIcon`, new) only when `usePhone()` is not
null; the badge reuses the Needs you count the rail already has. Esc, the scrim and a
route change close it; focus moves to the first item on open and back to Menu on close.
The stored collapsed state (`lado.rail`) is neither read nor written on a phone: the drawer
always shows the names. **Why:** one component and one list of sections (`SECTIONS`).

### D3. The compact head and `SessionDetails`

`HeadLine` renders, on a phone, the dot, the title as a button (`aria-haspopup="dialog"`),
and Stop (`SessionControl`'s button, unchanged); the change feed's mark is the Shell's.
The button opens `SessionDetails` (new, in `Sessions.tsx` or its own file): a modal
`<dialog>` at the bottom, `aria-label` the session's title, holding the folder with Copy
path (`Copy.tsx`), `GitFact`, the kits with `KitTip`, the CLI with `CliTip` (the same
`useAbout`), Rename (`TitleEdit`), Copy link and a link All sessions. **Why:** the head's
pieces are reused, so what the sheet says cannot drift from the computer's head.

### D4. The app window on a phone

`:root[data-phone]` gets the rules of `@media (min-width: 901px)` (html and body do not
scroll, `.app` is `100dvh`, `.content` scrolls), with the rail out of the grid (`.app`
one column). The chat's own flex layout then keeps the feed scrolling and the card and
composer at the bottom, as on a computer. `WaitingCard`'s `NARROW` scroll-into-view and
the card's edge stay off on a phone (the card's height is CSS: `max-height: 50%`).
`index.html`'s viewport gets `interactive-widget=resizes-content`, so Chrome on Android
shrinks the layout above the keyboard; Safari scrolls the focused field into view by
itself. The composer's textarea is 16 px on a phone: Safari zooms into a smaller field.
**Why:** the layout that works on a computer's wide window is reused, not rewritten.

### D5. The sideways card: minimized by the layout, not remembered

In `short`, `WaitingCard` treats itself as minimized unless the human opened it there, a
state of the component that is not written to `lado.waitingMinimized.<session>`; a tab or
the line shows it expanded (the existing expanded mode), and folding it goes back to
minimized. Turning upright drops that state. **Why:** the human's remembered choice is for
the chat of any screen; a layout's fold must not overwrite it.

### D6. Sessions on a phone

`Sessions` on a phone renders the list without the splitter and without the strip; on
`/sessions` it is the content, on `/sessions/<name>` it is not rendered. `lado.sessionsList`
(the list's collapsed state and width) is not written on a phone. **Why:** the menu and
the sheet's All sessions reach the list; the strip's initials do not name sessions.

### D7. Terminals over the screen

On a phone `TerminalPanel` renders no column and no strip; `useOpenTerminal` opens the
panel already expanded, and the expand button reads Close terminal, which closes the
panel (the sockets close as when the panel folds today); `lado.terminals` is not written on a phone. **Why:** the expanded mode is
there and tested; the coming task adds typing on top.

### D8. Tooltips on a tap

`Tooltip` shows on `pointerup` with `pointerType === "touch"` when its trigger is not a
`button`, `a` or `[role=button]`, and hides on the next `pointerdown` outside it; mouse
and keyboard behaviour is unchanged. **Why:** the hints (kits, CLI, git) are the only
place of versions and modes; buttons have visible icons and accessible names.

### D9. Tests

UI e2e in `tests/ui/test_phone.py` with a context of its own
(`browser.new_context(viewport=…, is_mobile=True, has_touch=True)`): upright 390×844 and
360×780, sideways 844×390, for the scenarios of the delta, with screenshots; a guard test
with a mouse at 1280×800, 800×900 and 390×844 that the rail, the head's facts, the strip
and the terminal strip are there and no Menu is. vitest for `usePhone` (a fake
`matchMedia`), the Shell's menu, `SessionDetails`, the Tooltip's tap. The UI e2e suite
before this change must pass unchanged (AC-13). **Why:** the layout needs a browser; the
logic of the hook and the components does not.
