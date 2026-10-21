## Context

The New session window (`web/src/Launch.tsx`) writes every note under its fields as a
`.field-note` span or div, with `ok`, `warn` or `bad` for a success, a warning and a
refusal. In `web/src/styles.css` all three are 12 px; `warn` only turns the text from
`--muted` to `--ink`, and `bad` adds a 3 px `--ink` stripe on its left. That is the root
cause: the levels differ by a shade of text, so a warning or a refusal reads as one more
hint. The classes are used in `Launch.tsx` only.

`web/src/tokens.css` is the one place of colours (`tokens.test.ts` fails on a colour
anywhere else and checks the contrast of named pairs). It has `--danger` (Stop, Forget)
but no ground for it, and its only warm colour is `--human`/`--human-ground`, which
`docs/design/ui.md` reserves for what waits for the human.

Mockup: run artifact `task/lad-120/mockup-launch-notes.html` (variant A).

## Goals / Non-Goals

Goals: a warning and a refusal are noticed at a glance in both themes, hints stay quiet,
the window gains no element, and the look is ready for step S3's refusal.

Non-goals: other screens' notes, the start's own refusal (`.problem`), new texts.

## Options

1. **Panels by CSS on the existing classes** (chosen): the three levels in
   `styles.css`, three new tokens. Long-term cost: none beyond three tokens; every
   `warn`/`bad` note, S3's included, gets the look by its class.
2. **A note component** (`<Note level=…>`) replacing the spans and divs: one place for
   the markup, but about thirty call sites change for no new behaviour, and the classes
   already are that one place.
3. **Bolder text only** (13 px, coloured text, no ground): lightest, but a coloured line
   among grey lines is what the human already found too easy to miss.

Held against AGENTS.md: no provider is involved (neutral core holds); the tokens stay the
one source of colours; nothing is dropped; no field or option is added. ROADMAP's coming
step S3 adds a refusal in this look without new styles.

## Decisions

- **D1. Levels by class, look by CSS only.** `.field-note.warn` and `.field-note.bad`
  become panels: `padding: 6px 10px`, `border-radius: 6px`, `border-left: 3px solid`,
  `font-size: 13px`, `line-height: 1.4`, `color: var(--ink)`; `warn` on `--warn-ground`
  with a `--warn` stripe, `bad` on `--danger-ground` with a `--danger` stripe. `.field-note`
  and `.field-note.ok` do not change.
- **D2. The refusal's icon is CSS, the warning's is its text.** `.field-note.bad` gets
  `position: relative; padding-left: 30px` and a `::before` `!` in a 15 px circle of
  `--danger` with `--on-danger` text, at `left: 9px; top: 7px`, so a refusal of several
  lines (problem, hint, command) keeps one icon at its first line. A pseudo-element is not
  in the text, so tests that read a note's text are unchanged. The warning keeps the `⚠`
  its text already has.
- **D3. Three tokens, amber not orange.** `--warn: light-dark(#8a5a00, #e0b04a)`,
  `--warn-ground: light-dark(#fdf5dc, #2f2814)`, `--danger-ground: light-dark(#fdeceb,
  #3a1d1b)`. Contrasts (computed): `--ink` on `--warn-ground` 16.3 / 12.2, on
  `--danger-ground` 15.5 / 12.7; `--muted` 5.6 / 5.6 and 5.4 / 5.9; `--warn` on its ground
  5.4 / 7.3; `--danger` on its ground 5.8 / 6.9 (light / dark). These pairs join
  `PAIRS` in `tokens.test.ts`. If a pair falls short in review, the ground gets lighter
  (darker in dark), never the text paler.
- **D4. The kits list's load error is a warning.** In `KitsField` the line for
  `listed.error` takes `field-note warn` (text unchanged, no `⚠` added: its text is the
  server's). It never blocked Start; the start refuses a kit that does not load and shows
  why. So every remaining `bad` note keeps Start off, which the e2e test proves for one
  refusal and the unit tests already prove per case (`ready`, `cloneReady`,
  `scratchReady`).
- **D5. The phone.** At 390 px the panels add about 12 px per note; the window already
  scrolls inside `max-height: calc(100vh - 32px)`, and in the mockup's 390×844 frame the
  window with the warning is about 830 px tall, Start at its end. The step's threshold
  holds only for a Start that was in view before: the developer opens the
  folder-outside state at 390×844 on `main` and on the branch (the e2e screenshots) and
  compares whether Start is in view without scrolling; when it was and no longer is,
  the panels' padding goes to `4px 8px`, and when that does not help, the human is asked.

## Risks / Trade-offs

- Amber next to the orange of "needs you" elsewhere in the UI: kept apart by hue
  (#8a5a00 / #fdf5dc against #b4530f / #fdf1e6) and by place (only the New session
  window).
- `.field-note.bad` on a span inside a flex column: `position: relative` with the icon's
  absolute position is safe for both the span and the div form.
