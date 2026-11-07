Task: LAD-223

## Why

Symptom: every row of the session list says how many agents the session has, a number the human
never used. The card a row shows on hover is five lines of plain text: the folder, the kits, the
CLI and the permission mode run together with no labels, and it does not name the project.

Cause: the count came into the row with the run time (2026-10-11, feature/session-row-line), and
the card grew one line at a time out of a tooltip. Its text is `SessionTip`, built from
`SessionInfo` alone, which carries a project's id but not its title: the title comes with
`SessionAbout`, asked for the open session only.

Options weighed for the card (rendered in `mockup-session-card.html`):

- A (taken, the human's answer #4348): labelled rows. Each fact is found by its label, and a long
  list of kits only wraps. Long-term cost: the card is taller, so it needs a place of its own.
- B: blocks with chips. Lower, but kits, the CLI and the mode mix in unlabelled chips, and three or
  four kits make it grow anyway.

Options weighed for the project's name (the human's answer #4361):

- A (taken): the title, sent with `SessionInfo`. The card says what the head and Details say, by
  the rule of `projects` (the id only where there is no title). Long-term cost: a rename has to
  reach open windows, done by touching the project's sessions (`design.md`, D2).
- B: the id. Web only, but the card would name the project otherwise than the head.

Options weighed for the card's place (the human's answer #4385, finding F10 of the UI review):

- A (taken): right of the list, level with the row. The list stays in sight, at the price of a
  new placement in `Tooltip`.
- B: under the row, as now. No new code, but a card of about 214 px hides about four rows.

## What Changes

- A row's line loses the agents' count: `ran 10 d 6 h`, under a title `lad-189 · ran 2 d 2 h`. A
  row of a session in trouble with nothing waiting shows its run time too.
- `idle` stops naming the count wherever the mark's words go (the card, the head's dot, Details).
  `2 of 5 agents working` stays: only it says how many agents are busy.
- The card becomes labelled rows: Project, Ran, Folder, Kits, CLI, Mode, under the title and a
  state line with the row's mark. A session in trouble says what to do.
- The card has a fixed width of 360 px, stays inside the window and opens right of the list.
- `SessionInfo` gets `project_title`, and a project's rename reaches open windows.

## Scope

- The session list's rows, the strip's icons (they share the card), the mark's words, `Tooltip`'s
  placement, `SessionInfo`, `state.set_project_title`, `docs/design/ui.md`, CHANGELOG.md.
- The change adds a field to the server's API: a feature of 0.45.0, whose heading already bumps the
  minor. No schema migration, no MCP tool or CLI change.

## Out of scope

- The pointer on the card (finding F3, WCAG 1.4.13): the card stays a tooltip, closed when the
  pointer leaves. A deliberate exception, the human's answer #4385: it shows on focus, Esc closes
  it, the path is copied in Details, and a card that keeps the pointer changes `Tooltip` beyond a
  tweak.
- The agents' count in the card when idle (finding F8): the human's answer #4348 removed it.
- The team's list `Team · N agents` in the head: there the count is about the list itself.
- The branch and versions in the card: they need `SessionAbout`, a request per hover, or git in the
  change feed; Details has them.
- A card on a phone (finding F15): a row is a link, a tap opens it, and Details holds the facts.
- The card's own scrolling: it takes no pointer, so a window lower than the card cuts its end.

## Impact

- `web/src/Sessions.tsx`, `web/src/Tooltip.tsx`, `web/src/styles.css`, their tests.
- `src/lado/server/models.py`, `src/lado/state.py`, `web/openapi.json`, `web/src/api.gen.ts`.
- Specs: new `session-card`; `session-status-mark`, `session-head`, `session-title` modified.
