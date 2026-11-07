Task: LAD-228

## Why

In the window Remove <kit>? the line that names the running sessions using the kit has a red
border and no icon, against the notices rule (`docs/design/ui.md`, Look; capability `notices`).
It is the last box of its kind in the UI.

Cause: the line wears `.kit-danger` (`web/src/Kits.tsx:1099`, `web/src/styles.css:8885`), which is
not among the classes of the section "Notices" of `styles.css`. LAD-198 made that rule and LAD-224
moved the kit windows' other lines onto it, working from the design QA's report, which did not
name this class.

The task asked for an error notice. The human decided on a warning on 2026-11-07, with the
mock-up: nothing has failed when the line shows and Remove stays open, so it warns of a
consequence, as "New MCP server…" does in the update window. Red stays for a real refusal of
Remove, shown in the same window.

Options weighed for the code:

- A (taken): the line takes `.kit-warning` and `.kit-danger` goes. No new rule: the size, margin
  and wrapping `.kit-warning` already has are what the line needs, and a class less can drift.
- B: add `.kit-danger` to the warning selectors of "Notices". Keeps a class named danger that
  draws a warning, and a fourth selector list entry that says the same as `.kit-warning`.
- C: `<p class="problem share-warning">`, as Share does. `.problem` keeps line breaks, 14 px text
  and no wrapping of a long name: all to be undone for a 13 px line of the kit windows.

## What Changes

- In the window Remove <kit>? the line about the running sessions is a warning notice: amber
  ground, alert icon, no border, in both themes. Its words stay.

## Scope

- `web/src/Kits.tsx`, `web/src/styles.css`, `tests/ui/test_kits_page.py`, `docs/design/ui.md`,
  `BACKLOG.md` (the entry of this defect goes).

## Out of scope

- The line's words, lower case first letter included: the core writes them and `lado kits remove`
  prints the same (`runtime.KitUsers.running_line`); a change of the UI's look is no reason to
  change the CLI.
- The stopped sessions' line: it stays muted, as a resume needing the kit breaks nothing now.
- `role="alert"` on the line: it is part of what the window says at opening, not an event, and the
  kit windows' other warnings have none.

## Impact

- No server, API, schema, MCP or CLI change; no provider is touched.
- Version: a fix, under the open `## 0.45.0 (unreleased)`, no bump of its own.
- `CHANGELOG.md` stays as it is: its unreleased item "Errors and warnings look like what they
  are" already says the kit windows' warnings are notices, and this makes it wholly true.
