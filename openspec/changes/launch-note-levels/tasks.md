## 1. Tokens

- [ ] 1.1 `web/src/tokens.css`: `--warn`, `--warn-ground`, `--danger-ground` with D3's
  values and a comment each (what they are for; amber is not the orange of "needs you").
- [ ] 1.2 `web/src/tokens.test.ts`: the pairs `ink`/`warn-ground`, `ink`/`danger-ground`,
  `muted`/`warn-ground`, `muted`/`danger-ground`, `warn`/`warn-ground`,
  `danger`/`danger-ground` in `PAIRS` (4.5:1 in both themes). Check: `make web`.

## 2. The three levels

- [ ] 2.1 `web/src/styles.css`: `.field-note.warn` and `.field-note.bad` as panels (D1),
  the refusal's `::before` icon (D2); `.field-note` and `.field-note.ok` untouched.
- [ ] 2.2 `web/src/Launch.tsx`: the kits list's load error (`listed.error` in
  `KitsField`) takes `field-note warn` (D4); no other markup or text changes.
- [ ] 2.3 `web/src/Launch.test.tsx` (unit, vitest): `/api/kits` answering an error with
  kits chosen shows its text with the class `field-note warn` and Start on. Check:
  `make web`.

## 3. UI e2e (`tests/ui/test_launch.py`, `-m ui`)

- [ ] 3.1 Extend the container test of the warning: the warning's computed
  `background-color` and `border-left-color` differ from those of a hint of the same
  window ("the only one installed" or another `.field-note` without a level); Start on.
- [ ] 3.2 A refusal: Where names a folder outside any git repository; the refusal's
  computed background differs from a hint's and from the warning's colour; Start session
  is disabled.
- [ ] 3.3 Screenshots for the reviewer, each state in the light and the dark theme
  (`page.emulate_media(color_scheme=…)`): hint and ok, warning, refusal; and the warning
  at 390×844. Check `-m ui` on the changed file.
- [ ] 3.4 Phone threshold (D5): compare the 390×844 screenshot with one from `main`;
  record in `build-report` whether Start was and is in view.

## 4. Documents

- [ ] 4.1 `docs/design/ui.md`, New session window: the rule of the three levels (hint and
  ok quiet text; warning an amber panel; refusal a red panel with `!`; Start off while a
  refusal shows; a note that does not block the start is not a refusal), with the
  mockup's name `task/lad-120/mockup-launch-notes.html`, decided 2026-10-21, LAD-120; the
  sentence on `field-note warn` for the outside-workspace warning stays true. In Look,
  the tokens' list names the new ones.
- [ ] 4.2 CHANGELOG.md, `## 0.42.1 (unreleased)` → Improved: one line, e.g. "**Warnings
  and refusals in the New session window stand out.** They show as amber and red panels;
  hints stay quiet."
- [ ] 4.3 Checks: `make lint`, `make test`, `make web`, `uv run pytest -m ui
  tests/ui/test_launch.py`, `openspec validate launch-note-levels --strict`.
