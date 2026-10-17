Task: LAD-95

## Why

The human wants to use LADO from a phone's browser: follow a session, answer gates and
questions, write to the supervisor, read artifacts, stop a session. A survey of every
screen in Chromium with a phone's emulation (390×844 upright, 844×390 sideways; run
artifacts `task/lad-95/phone-now-*.png`) found that nothing scrolls sideways any more and
that Needs you, Flows, Artifacts, Kits, Settings, the New session window and the artifact
panel work, but a session's page is hard to use:

- upright, the session's head takes three lines (about 125 px), sticks to the top and with
  the session strip and the tabs takes some 40% of the screen; `live` is squeezed into a
  lone dot on a line of its own; the path is cut to its tail;
- the fourth tab (Artifacts) is past the right edge with no sign that it is there;
- the collapsed rail takes 60 px, 15% of the width;
- a flow event's line breaks into three or four lines and its text is cut with "…";
- the composer is at the very end of a long page: the feed and the gate's card must be
  scrolled past to write;
- sideways, the screen is 390 px high: the sticky head takes 76 px (20%), and one or two
  events of the feed fit;
- what only a tooltip says (the whole folder, a kit's version) cannot be reached: tooltips
  show on a mouse's hover only.

Root cause: the UI's narrow rules (`max-width: 900px`) were written for a narrow window of
a computer: the window scrolls as one page, the rail and the session's facts stay, the
head wraps. A phone needs fewer things on the screen at once, a feed that scrolls by
itself and the composer always at hand.

## What Changes

- **A phone layout that the UI picks by itself**: on a touch screen (`pointer: coarse`) no
  wider than 600 px or no higher than 500 px. A computer, with a mouse, never gets it,
  whatever its window's size; a tablet (wider and higher) neither. No switch.
- **The rail becomes a menu**: hidden; a Menu button (☰) at the top bar's left, with the
  Needs you count on it, opens the rail over the page from the left with its names.
- **One line of top bar**: Menu, then the page's title; on a session's page the status dot,
  the session's name (a button), the server's `live` mark as a dot, Stop.
- **The session's details in a sheet**: a tap on the name opens a sheet from the bottom with
  the status, run time, the whole folder, git, the kits with versions, the CLI with its
  version and mode, and Rename, Copy path, Copy link and All sessions.
- **Sessions**: the session strip is gone; the Sessions page is the list, full width.
- **The session's tabs fit**: without their icons all four show at 360 px.
- **The chat as on a computer**: the feed scrolls by itself, the waiting card (at most half
  the chat's height) and the composer stay at the bottom; the composer's keys hint is not
  shown on a touch screen.
- **A flow event's line** starts at the left edge and its text wraps under it instead of
  being cut.
- **Sideways**: the waiting card starts minimized; a tap on one of its tabs shows it over
  the chat; the Team row and the composer's "to" line are not shown.
- **Terminals**: no panel or strip; a team chip or Open terminal shows the agent's terminal
  over the whole screen, Close terminal puts it away.
- **Tooltips on a tap**: on a touch screen a tap on a hint (a kit's name, the CLI, git)
  shows its tooltip; a button's tooltip, which only names it, does not show.
- **The Kits tabs fit** a 360 px screen.
- Docs: `docs/design/ui.md` (a section "Phone layout"), CHANGELOG.md under 0.41.0 (a new
  minor: a UI feature). BACKLOG.md loses "The UI scrolls sideways on a phone-wide screen"
  (no longer true) and "An image in the artifact's tab is sized by `vh` while the tab is
  `dvh`" (fixed here, the phone's layout is `dvh`).

## Scope

- The web UI (`web/src/`): the phone's media query and its hook, the Shell (menu, drawer,
  top bar), the session head and its details sheet, the session list, the chat's layout,
  the waiting card, the terminal panel, the Tooltip, the Kits tabs, `index.html`'s
  viewport; vitest and UI e2e tests.
- `docs/design/ui.md`, CHANGELOG.md, BACKLOG.md.

## Out of scope

- **Typing into an agent's terminal from a phone** (a row of Esc, Tab, ⇧Tab, arrows,
  Ctrl+C; the agent's window resized to the phone's on Take control; the keyboard covering
  half the screen). The human's decision: a task of its own right after this one, with
  live tests. Here a terminal on a phone shows as it does today, over the whole screen.
- **Reaching LADO from the phone** (a QR code with the link, HTTPS, "add to home screen"):
  a separate task, the human's decision. `lado server --host 0.0.0.0` already listens on
  the network.
- **A separate mobile UI or a "phone mode" switch**: two copies of each screen drift apart
  with every change, and the size and the pointer tell a phone reliably. The human's
  decision.
- **A bottom navigation bar**: shown in the mockup, turned down by the human; it takes
  56 px of height always, 15% of a phone held sideways.
- **Polishing New session, Kits (beyond its tabs), Settings, Projects, Home** on a phone:
  they work; the human's goal is following and answering.
- **Tablets and a computer's narrow window**: unchanged, by the human's condition that the
  computer's design must not suffer.
- **Server, API, schema, CLI, providers**: nothing changes there.

## Acceptance criteria

- AC-1: On a computer (a mouse) at 1280×800, 800×900 and 390×844 every page looks and
  behaves as before: the rail, the session's head with its facts, the session strip, the
  terminal panel; no Menu button.
- AC-2: On a touch screen 390×844 the rail is hidden and the top bar is one line with a
  Menu button that shows the Needs you count; Menu opens the rail with its names over the
  page; choosing a section, a tap outside or Esc closes it.
- AC-3: On a session's page on a touch screen 390×844 the top bar holds Menu, the status
  dot, the session's name, the `live` dot and Stop, in one line no higher than 52 px; a tap
  on the name opens the details sheet with the whole folder, git, kits with versions, the
  CLI with its version and mode, and Rename, Copy path, Copy link, All sessions.
- AC-4: On a touch screen 390×844 the session strip is not shown, the Sessions page shows
  the session list across the screen, and its row opens the session.
- AC-5: On a touch screen 360×780 the four tabs Activity, Agents, Flows, Artifacts are all
  within the screen.
- AC-6: On a touch screen 390×844 with a gate and a question waiting, the feed scrolls by
  itself, the waiting card is at most half the chat's height and the composer is at the
  screen's bottom without scrolling the page; the keys hint is not shown.
- AC-7: On a touch screen 390×844 a flow event's whole text shows, wrapped, and its line
  starts at the feed's left edge.
- AC-8: On a touch screen 844×390 the top bar is one line, the waiting card is minimized,
  the composer is at the bottom; a tap on a card's tab shows the card over the chat and
  Esc or its fold button minimizes it again.
- AC-9: On a touch screen 390×844 no terminal panel or strip shows; a team chip opens the
  agent's terminal over the whole screen and Close terminal goes back to the chat.
- AC-10: On a touch screen a tap on a kit's name in the details sheet shows its tooltip
  with the version; a tap on a button shows no tooltip.
- AC-11: On a touch screen 360×780 the Kits page's three tabs are within the screen.
- AC-12: No page scrolls sideways on a touch screen of 360, 390 or 430 px upright or
  844×390 sideways.
- AC-13: The UI e2e suite that ran before this change passes unchanged.
