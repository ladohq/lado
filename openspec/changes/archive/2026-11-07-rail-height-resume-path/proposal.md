Task: LAD-226

## Why

Two defects found by checking `main` at 506dd44d in the iPhone 17 and iPad Air 11" simulators
(iOS 26.4, Safari).

**The rail runs past the screen on a wide touch screen.** On an iPad held sideways (wider than
900 px) Report a bug and Settings lie under the screen's bottom edge and cannot be reached.

Cause, confirmed in the source and by the report's measure in WebKit (1180 px wide, visible
height 560: app 560, rail 688): `.rail { height: 100% }` inside `@media (min-width: 901px)`
(`web/src/styles.css:94`) loses to the later `.rail { height: 100vh }` (`:164`) of the same
specificity. The app follows the visible part (`--phone-height`), the rail stays `100vh`, which
in iPad Safari is more than that part. The rule of 601 to 900 px, keyed on `:has(.sessions)`, is
more specific and works. On a computer `100vh` equals the window, so nothing shows there. Of
the rules in that media block only `.rail` collides: the base `.main` and `.content` set
neither `min-height` nor `overflow`.

**The Resume window hides the end of a long folder.** On a 402 px phone the path in Where stops
at the field's edge with no ellipsis, and it cannot be read to the end.

Cause: the Resume window is the New session window in another mode, and Where stays its input,
disabled. An input clips its value, and a disabled one cannot be scrolled by a finger.

Options weighed for the rail:

- A (taken): raise the rule in the media block to `.app .rail`. One line; cost: one more rule
  that wins by specificity rather than by order, as the 601 to 900 px rule already does.
- B: move the base `.rail` above the media block. Removes the cause in the order of the file,
  but moves a rule in `styles.css`, where LAD-224 works now, for no gain to the user.
- C: size the base rule by `--phone-height`. Spreads the phone's variable to every width and
  to the pages of 601 to 900 px that scroll with the window, where `100vh` is right.

Options weighed for Where, decided by the human on 2026-11-06 with the mock-up:

- A (taken): in Resume mode Where is text that wraps. The whole path shows at any width with
  nothing to press; the window gets a line or two higher.
- B: an ellipsis, the whole path on a tap. The end of the path, its most useful part, stays
  hidden until a tap nothing invites; the UI's tooltip is drawn under a modal window and a
  disabled input takes no press, so both would have to change.

This replaces the task's check "the ellipsis shows": nothing is cut, so there is no ellipsis.

## What Changes

- In a window wider than 900 px the rail is as high as the app, so on a touch screen it ends
  with the visible part of the screen. A computer's window looks as it did.
- In the Resume window Where is the session's folder as text that wraps, whole. New session's
  Where stays the input it is, also while the window is busy.

## Scope

- `web/src/styles.css`, `web/src/Launch.tsx`, their tests, `docs/design/ui.md`, `CHANGELOG.md`.

## Out of scope

- Scrolling the rail when it is lower than its content, as with the on-screen keyboard open on
  an iPad held sideways: the keyboard can be closed, and a scroll would change low windows on a
  computer. Listed for the human at the design's question.
- An ellipsis in New session's Where: the human can scroll an input that is not disabled, and
  the defect is the Resume window's.
- The sizes of the rail's targets for a finger: LAD-216.
- Focus after the Resume window closes: LAD-224 (F46).

## Impact

- No server, API, schema, MCP or CLI change; no provider is touched.
- Version: a fix, under the open `## 0.45.0 (unreleased)`, no bump of its own.
- `web/src/styles.css` and the Resume window are also LAD-224's, not merged when this was
  written: a conflict in `styles.css` is expected.
