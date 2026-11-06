Task: LAD-198

## Why

Symptom (audit of LAD-189, spec §7, findings F13, F20-F24, F26, F27): the human's working session has
115 artifacts, and in a column under 720 px each is a card of 140-180 px, so four fit on a screen.
The type shows as a MIME type beside a filter that names it in words. The artifact panel says the
title up to three times and links to the tab it is on. An empty Artifacts or Flows tab does not say
where its content comes from. A run's row does not say what the run is about, and an opened event
repeats four of its five facts. Stop shows a red button that is off. Notices wear a stripe.

Cause: each of these screens was built when a session held a handful of items, and each answers the
question of its day. The narrow Artifacts view is the wide table's cells stacked by CSS, with no
layout of its own. The viewer's head and body do not know each other's text. The panel does not know
which tab it lies over. The notices grew one by one, each with its own stripe.

Options weighed for the main finding, F20:

- A: tighten the cards by CSS: the same stacked cells, less padding. The least code, but a table
  shown as blocks has no list semantics, and its tooltip and its words cannot depend on the width.
- B (taken): a list of its own under 720 px, chosen by the measured width, and groups by scope from
  100 artifacts at any width. It adds a second row component, and both read one set of helpers.
- C: paging or a virtual list. It keeps 115 rows flat, so the human still scrolls past finished runs,
  and it fights the browser's search and the row's focus return.

Options for the kits' flows in the empty Flows tab, F22:

- A (taken): `flows` on `SessionKitInfo`, the answer the session's Details already reads. One field,
  from the kit as the next agent takes it.
- B: join the session's kit names with `/api/kits/installed` in the browser. No API change, but a
  second way to find a session's kit, which can disagree with `kits.find`.
- C: the same text without the list. No API change, but the line would not say what can run.

## What Changes

- **F20.** A column under 720 px shows a two-line list, 48 px a row: "name · title", then "type in a
  word · author · time · size". The latest change moves to a tooltip and the panel. From 100
  artifacts the list and the wide table go in groups by scope, which fold.
- **F21.** The viewer drops a title equal to the Markdown's first H1. The scope pill says "session"
  or "step <name>". On the Artifacts tab the panel's link to the artifact's page says Full page. On
  a phone the panel's bar holds Download, Copy link and "⋯" with labelled items.
- **F22.** Empty Artifacts and Flows tabs get a heading and a line that explains them.
- **F23.** A run's card and row show the first line of its task under its name.
- **F24.** An opened event shows "Step took N" as one line, then the note. The facts column goes.
- **F26.** Take control's backdrop uses `--scrim`, as the spec asks; it used `--shadow`.
- **F27.** With open runs the Stop popover has no Stop and forget, and says why below its buttons.
- **F13.** Notices lose their stripe for a ground and an icon. The selected row's stripe stays.

Checked and left as they are: F6 (the strip's badges in `Sessions.tsx`) matches the spec. F26's dialog
is modal and covers the whole page, the terminal too; only the colour differed.

The change goes under `## 0.45.0 (unreleased)`, whose minor is already bumped: no further bump. It
adds one field to an API answer. No schema, MCP or CLI change.

## Out of scope

- LAD-216 (an iPad's touch targets) and LAD-190 (the side panel): tasks of their own.
- The strip of folded terminals in F26: LAD-189 spec §2, not group 7.
- The wide table's Type column keeps its MIME type: the spec changes the narrow column only, and the
  critique says the wide table reads well.
- Wrapping of the type filter in a narrow column: the critique names it, the spec does not ask for it.
- "⋯" in a panel on a computer: the spec says phone. A narrow panel keeps its icons (LAD-43).
- The system share sheet on a phone: it needs https, and LADO on a home network is often plain http.
  "Share" of the critique is its 🔗, which is Copy link.
- Virtual scrolling: 115 rows in groups need none.
- Quotes, the gate's note, the recommendation band, the open gate and the waiting card's tab keep
  their left edge: they are not notices.

## Acceptance criteria

- AC-1. In a column under 720 px each artifact is a row about 48 px high: the name in mono 13 600 and
  the title on one line, then the type in a word, the author, the time and the size in 12 px
  `--muted`. No card remains at any width.
- AC-2. Hovering a row or focusing its link shows the latest change; a row without one shows no
  tooltip. A click or Enter opens the panel, and closing it returns the focus to the link.
- AC-3. A session with 100 artifacts or more shows groups by scope at any width; with 99 it does not.
  A filter neither adds nor removes the grouping, and picking one scope shows a flat list.
- AC-4. Session's and open runs' groups start open, ended runs' folded; the newest group comes first.
  That default holds on entering the tab or when a group first appears: a run that ends folds
  nothing meanwhile, and a group with the focus never folds by itself.
  The human's fold is kept per session across a reload. While the search has text, every group
  with a match is open and its fold is off.
- AC-5. A group's heading is a button with `aria-expanded` and `aria-controls`, in the Tab order,
  working with Enter and Space, and naming the scope and its count.
- AC-6. A Markdown record whose first H1 equals the title shows no title line, in the panel and on
  the artifact's page; a different H1 or none keeps it.
- AC-7. The pill says "session" or "step <name>".
- AC-8. On the Artifacts tab the panel's link says Full page, elsewhere Open in Artifacts tab; both
  go to the artifact's page. Expand does not change.
- AC-9. In a window of 600 px or less the panel's bar shows Download, Copy link, "⋯" and ×. "⋯" opens
  Open in new tab (not for `other`) and the link to the page, with labels, by keyboard too.
- AC-10. An empty Artifacts tab shows its heading and line. A session with no run shows "No flow runs
  yet" with the kits' flows, or the line for no flows. A session with ended runs keeps its groups.
- AC-11. A run's card and row show the first line of its task, 13 px `--muted`, cut with "…".
- AC-12. An opened event shows "Step took N" on one line, then the note, with no Who, From, Outcome
  or To.
- AC-13. Take control's backdrop computes to `--scrim` and covers the terminal.
- AC-14. With open runs the Stop popover has no Stop and forget and shows the new line below its
  buttons. Without open runs it works as before.
- AC-15. Every notice listed in `design.md`, D14, has no left stripe, and has its ground and icon, in
  both themes. The session list's selected row keeps its stripe.
- AC-16. All of it holds at 390, 768, 1024 and 1440 px, in the light and the dark theme, with no
  horizontal scroll of the page.

## Impact

- `web/src/`: `ArtifactsTable.tsx`, `ArtifactView.tsx`, `ArtifactPanel.tsx`, `artifacts.ts`,
  `prefs.ts`, `Flows.tsx`, `SessionControl.tsx`, `styles.css`, their tests.
- `src/lado/server/models.py`, `launch.py`: `SessionKitInfo.flows`; `web/openapi.json`,
  `web/src/api.gen.ts` by `make web-types`.
- `tests/test_server_session.py`, `tests/ui/`.
- `docs/design/ui.md` (Artifacts, Flows, Stop, New session, the Take control part), `CHANGELOG.md`.
