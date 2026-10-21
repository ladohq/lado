Task: LAD-120

## Why

Every note under the fields of the New session window is the same small grey line
(`.field-note`, 12 px, `--muted`): a warning differs from a hint only by the colour of its
text, and a refusal only by a thin stripe on its left. The human said (2026-10-21, the
epic LAD-116, step S1b): the notes read poorly, small and grey, users do not take them
seriously; and the window must not get heavier either. Step S3 of the epic will add a
refusal of its own ("this folder belongs to a project"), which needs a look that is
noticed.

## What Changes

- **Three levels of the window's notes**, by look only (`web/src/styles.css`):
  - a hint (`.field-note`) and a success (`.field-note.ok`) stay as they are: 12 px,
    muted, and the action's blue for a success;
  - a warning (`.field-note.warn`) is a panel: a light amber ground, a 3 px amber stripe
    on its left, a 6 px radius, text 13 px in `--ink`; its icon is the `⚠` its text
    already starts with;
  - a refusal (`.field-note.bad`) is the same panel on a light red ground with a red
    stripe and a red round `!` drawn by CSS before its text (not part of the text).
  The panels keep their content: a refusal with a hint holds its muted sentence, its
  command and Copy as before.
- **New colour tokens** in `web/src/tokens.css`, light and dark: `--warn` (the stripe of a
  warning), `--warn-ground` and `--danger-ground`; the refusal's stripe and icon use the
  existing `--danger`. Amber is not the orange of what waits for the human, which stays
  only that.
- **The kits list's load error** (`/api/kits` failed) moves from a refusal to a warning:
  Start stays on with it today, since the kits chosen still go to the start and the start
  itself refuses a kit that does not load. Its text does not change.
- **Start is off while a refusal shows**: already true for every other refusal of the
  window; a UI e2e test now proves it.
- `docs/design/ui.md`: the rule of the three levels for the New session window's notes.
- CHANGELOG.md: one line under Improved.

## Scope

`web/src/styles.css`, `web/src/tokens.css`, `web/src/tokens.test.ts`, `web/src/Launch.tsx`
(the kits list's error class only), `web/src/Launch.test.tsx`, `tests/ui/test_launch.py`,
`docs/design/ui.md`, CHANGELOG.md, the new capability `launch-notes`.

## Out of scope

- New elements, banners, pop-ups or a new layout of the window: the human asked for a
  window no heavier than now; the panels are the notes' own boxes.
- Notes outside the New session window: `.field-note` is used only in `Launch.tsx`;
  `.field-problem` (composer, gate card, title edit, notifications) and `.problem` (the
  start's own refusal after Start, `.launch-refused`) are other classes and other screens.
- Texts of the notes: unchanged (step S1, LAD-117, renamed them).
- The refusal "this folder belongs to a project": step S3 adds it, in this look.
- Turning other quiet notes into warnings (a name taken by a running session, "checking…"):
  their level is not this step's question.

## Impact

- Users see warnings and refusals of the New session window as coloured panels; hints
  are as before. Behaviour is unchanged but for the kits list's load error, which now
  looks like the warning it is.
- No API, schema or CLI change. Version: patch.
