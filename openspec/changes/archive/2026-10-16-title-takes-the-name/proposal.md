Task: LAD-84

## Why

When the human renames a session that has no title yet, the field opens empty with the
session's name grey in it (its placeholder). The human wants to take that name and add
to it, as Claude Code takes its grey suggestion on Tab; their own titles are made that
way (`lad-83 (Docker install)`, `lad-84 (имя сессии)`), typed out by hand today.

Root cause: the name is only the field's placeholder, which nothing can take, and Tab
does what it does in any field: the focus leaves it, and leaving the field saves it
(LAD-66), so an empty field is saved as no title and the field closes.

## What Changes

Chosen with the human (mockup `task/lad-84/mockup-title-tab.html`, variant A, A1–A6;
answers of 2026-10-16: all as recommended):

- **The name as a suggestion**: while the field is empty, the session's name shows grey
  in it, as today. While the text typed is the start of the name (`la` of `lad-84`), the
  rest of the name shows grey after it. Tab, or → with the caret at the end, takes the
  name: it becomes the field's text, the caret at its end, the focus stays in the field,
  nothing is saved. The human types on and saves with Enter, as before.
- **Tab is taken only for the suggestion**: with any other text, or with the name already
  typed whole, no grey shows, and Tab leaves the field and saves it, as today; Shift+Tab
  always does as today.
- **The hint under the field** names the key while the suggestion shows: `Tab takes the
  name · Enter to save · Esc to cancel` in the head, `lad-84 · Tab takes the name ·
  Enter to save · Esc to cancel` in a list row; otherwise the hints of today.
- **A session with a title**: the field holds the title, selected, as today; no
  suggestion shows (A5, the title selected).
- Docs: `docs/design/ui.md` (Session title, Where it is set), CHANGELOG.md.
- A minor-level feature (a change users see in the UI; no API, CLI, MCP or schema
  change); its CHANGELOG line goes under the open heading `## 0.40.0 (unreleased)`.

## Scope

- `web/src/TitleEdit.tsx` (the suggestion, Tab and →, the hint), the two callers in
  `web/src/Sessions.tsx` (their hints), `web/src/styles.css` (the grey rest of the name).
- Tests: `web/src/TitleEdit.test.tsx` (vitest), UI e2e in `tests/ui/test_session_head.py`
  and `tests/ui/test_session_list.py`.

## Out of scope

- **The task of an open flow run as the suggestion** (variant B): a run's task is free
  text the supervisor writes (`LAD-83` alone for lad-83, a long sentence with "The human
  asked…" for lad-84), so the suggestion would be unpredictable; LADO knows no tracker
  task's title (the tracker is a kit's).
- **Several suggestions to pick from** (↑/↓, a list under the field): with the name as
  the one suggestion there is nothing to pick.
- **The caret at the end for a session with a title** (A5's second line): the human
  chose to keep the title selected; → or End go to its end.
- **Touch devices without a keyboard**: no Tab or → there; the field works as today.
- **`lado title`**: the CLI takes the whole text at once; nothing to complete.

## Impact

- Web UI only: the title field; no API, CLI, MCP, schema or provider change.
