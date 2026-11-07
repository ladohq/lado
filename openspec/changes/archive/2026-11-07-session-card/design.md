# Design: session-card

The approved look is the artifact `mockup-session-card.html`, variant "labelled rows"; the review is
`ui-review/lad-223/critique`. Above the provider layer nothing changes: this is the web UI and one
field of the server's API, the same for every provider.

## Decisions

**D1. `project_title` beside `project` in `SessionInfo`.** `project_title: str | None = None`,
filled in `models.session_info` through `state.get_project`. `project` stays the id: it is what the
links use, and turning it into `ProjectRef` would change the field every client reads. The comment
over `project` changes with it. The title stays one fact in `projects`; `SessionInfo` only reads it.

**D2. A rename touches the project's sessions.** `state.set_project_title` also runs
`UPDATE sessions SET project = project WHERE project = ?`, in the same connection. The journal's
trigger on `sessions` has no condition, so each session goes out in the feed, in the form of its
REST model, with the new title. Rejected: journaling `projects` (a schema migration and a new kind
in the feed, for a value only the card reads) and a derived value (a pass every 3 seconds for a
rare event).

**D3. `work` loses the count when idle.** `work(session)` returns `idle` for no busy agent, and
`sessionMark`, the card and Details follow by the one rule; no second wording. `about` loses its
fallback to the count, so `SessionRow` takes `RanAbout` unless something waits.

**D4. The run time is split once.** `ranText` keeps its output for the head. The row writes `ran`
before it as `SessionTip` does today (`session.running_since`). The card needs the stopped words
and the duration apart: one helper beside `ranText` gives both, and `ranText` is built from it.

**D5. `Tooltip` gets a `side="right"` prop**, passed by `StripIcon` and `SessionRow` only. Beside the
trigger: `left` is the trigger's right plus `GAP`; `top` centres the card on the trigger, kept within
`MARGIN` of the window; `--arrow-y` keeps the arrow on the trigger's middle, off the corners by
`ARROW_END`. Without room on the right it goes under or over. In both modes "over" is taken only
when the room over is larger than the room under: today it is taken whenever under does not fit,
which pushes a tall card past the top. The other 40 tooltips are short and keep their place. The
place is reckoned once on show, as today: a card that grows while open may overlap its row, a rare
case, accepted.

**D6. Width and height in CSS.** `.tooltip:has(.session-tip)`: `width: min(360px, 100vw - 16px)`,
`max-width` the same. `.session-tip`: `max-height: calc(100vh - 16px - 12px)`, the 12 px being the
tooltip's padding and border, and `overflow: hidden`: on `.tooltip` itself it would cut off the
arrow, which stands outside the card. The arrow's rule for `data-side="right"` stands beside the
other two.

**D7. Kits are cut in `SessionTip`,** at a constant `KITS_SHOWN = 6`: nine names with a long path made
a card of 422 px. The whole list is in Details.

**D8. The row's mark in the card is hidden from a screen reader,** as the word stands next to it.
The mark in the row keeps `role="img"` and its name: it is now the only sign of work there.

## Test layers

| Requirement | Layer | Test |
|---|---|---|
| A row's line names no agents' count | unit (vitest) | `web/src/Layout.test.tsx`: the four scenarios |
| Labelled facts, state line, how to go on, kits cut | unit (vitest) | `web/src/Layout.test.tsx`: card lines per state, `cardLines` rewritten for labels |
| The mark's words | unit (vitest) | `web/src/Layout.test.tsx`, the tables at the words of `idle` |
| Project by title | unit (pytest) + unit (vitest) | `tests/test_server_*.py` on `session_info`; the card with and without a title |
| A new title reaches the list | unit (pytest) | `tests/test_feed.py`: `set_project_title` journals each session, its item has the title. One SQLite file, no process boundary beyond the journal's own tests |
| Beside the list, in the window | UI e2e + unit (vitest) | `tests/ui/test_layout.py`: geometry at 1440×900, the last row, 590 px (rows) and 640 px (the strip: the list is folded there); `web/src/Tooltip` placement with mocked rects |
| One width, bounded height | UI e2e | `tests/ui/test_layout.py`: two cards of equal width, a window lower than the card |
| The card stays a tooltip | unit (vitest) | the pointer leaves, the card goes (the existing test extended) |

Regression run: the settings' Checks for `web/` and the server's API: `make lint`, `make test`,
`make web`, `uv run pytest -m ui tests/ui/test_layout.py`, and the openspec checks.

## At the archive

`session-card` is a new capability, so `openspec archive` writes a placeholder Purpose that
`openspec validate --specs --strict` refuses. Replace it in the archive's commit with:

> What the session list's rows say and how the session's card reads: labelled facts of a session on
> hover or focus of its row or strip icon, beside the list and inside the window.
