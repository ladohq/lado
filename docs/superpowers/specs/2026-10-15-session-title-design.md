# Session title: design

Task: LAD-66 (Rename a session). Change: `openspec/changes/session-title/`. Mockup:
`task/lad-66/mockup-rename.html` (variant A, both entry points; agreed with the human
2026-10-15).

## Problem

Sessions of one folder are named `lado`, `lado-2`, `lado-3`: the name comes from the
folder (`runtime.slug`) and says nothing about the work. The human wants to rename a
session.

The name cannot simply change: it is the session's identifier, the primary key that
twelve tables of `lado.db` refer to, the tmux session's name, `LADO_SESSION` of every
agent and `lado mcp` process, the prefix of the session's branches and worktree folders,
the UI's address of the session, and the argument of every CLI command. A running
session's processes cannot learn a new one; a stopped one's rename would have to rename
branches and move worktrees, and break links.

## Options and their long-term cost

| | What | Cost now | Cost later |
|---|---|---|---|
| A (chosen) | a title, a label over the name | a column, a rule, an API field and route, an editor | two names per session; the name is always shown beside the title |
| B | rename the identifier of a stopped session | every table's key, git branches and worktrees, the runs' stored paths, the loop's lock; a rollback for each step | every new place that keeps the name must be renamed too; old links break |
| C | A now, B later if needed | as A | `lado rename` is kept free |

Held against AGENTS.md's Design principles: neutral core (no provider involved); one
source of truth (the column, `runtime.set_title`, `MAX_TITLE` given to the UI through
`Limits`, the UI's label from `SessionInfo.title` only); no silent drops (a bad title is
refused, never cut); only what is used (no title at start, no MCP tool, no uniqueness:
the human's choices). ROADMAP: Projects (Later) and the desktop app (Stage 7) read the
same API and need nothing else from this change.

## Behaviour

### The title

- Optional, any language, one line, at most 80 characters after trimming the ends.
- Empty after the trim, or equal to the session's name: no title (the human's remark:
  a title equal to the name would show the name twice; storing none keeps one source).
- A control character (Unicode Cc: line breaks, tabs, …) or more than 80 characters:
  refused with the reason, nothing changed. Not cleaned or cut.
- Set and cleared at any time, also while the session runs; it survives stop and
  resume; `lado forget` deletes it; a new session of the same name has none.
- Not unique.

### Where it shows (UI)

| Place | With a title | Without |
|---|---|---|
| list row | the title in bold; the grey line starts with the name: `lado-2 · 3 agents · 1h 12m` (`lado-2 · <the line>` for every kind of grey line) | as today |
| collapsed list's icon | its letters from the title (`initials`), its accessible name the title | as today |
| row's and icon's card | first line `<b>title</b> · lado-2 · <status> · …` | as today |
| session head | `<h1>` the title, then the name small and grey (`.session-name-id`, monospace 13 px, muted), then the pencil | `<h1>` the name, then the pencil |
| browser tab | `<title> · LADO` (with `(n)` before it as today when something waits) | the name |
| Needs you | the session's line: the title, then the name in grey | the name |
| notification | `LADO · <title>` | `LADO · <name>` |

The list's search keeps a session whose title or name holds the typed text (case
ignored). The session region's accessible name (`Session <name>`), the address and every
copy (Copy link) keep the name.

### Where it is set (UI)

- **Head**: a pencil button `Rename session` right after the title (and the name),
  visible while the pointer is over the title or the button, while the button has the
  focus, and always on a device without hover; a double click on the title does the same.
  The title turns into a text field of its width (at most a third of the bar, as the
  `<h1>`), holding the title (empty when none, the name as placeholder), the text
  selected; under it the note `Enter to save · Esc to cancel · empty shows the name`.
- **List**: the row's ⋯ menu: `Rename…`, `Copy link`, `Open in new tab`. Rename… turns
  the row's title into the same field (the row stops being a link while it edits), with
  the note `lado-2 · Enter to save · Esc to cancel`.
- Enter or leaving the field saves (`PUT /api/sessions/{name}/title`); Esc cancels. The
  same text as stored sends nothing. While it saves, the field is read-only. Over the
  limit: `<n> characters, the limit is 80` under the field, nothing sent. A refusal:
  the server's text under the field (`role="alert"`), the field stays open with the text.
  After it closes the focus goes back to the pencil or the ⋯.

### CLI

```
lado title <session>                 # prints the title, or "<session> has no title"
lado title <session> "Review"        # <session>: title "Review"
lado title <session> --clear         # <session> has no title
```

Setting and clearing are refused inside an agent (`lado title is for the human; agent
"<a>" cannot use it`); TEXT with `--clear` exits 2. `lado ls`:
`lado-2 "Rename sessions (LAD-66)"  /Users/kao/Projects/lado`.

### API

- `SessionInfo.title: string | null`, in REST and the feed.
- `PUT /api/sessions/{name}/title`, body `{"title": string | null}`, under
  `Guard.changes`: 200 with the session's `SessionInfo`; 400 with the core's reason;
  404 for an unknown session.
- `Limits.max_title: number` (80).

## Acceptance criteria

- AC-1: In a session's head, the pencil (or a double click on the title) edits the title
  in place; Enter saves it and the head, the list row, the tab title, Needs you and the
  notifications show it, with the name beside it where the spec says.
- AC-2: Rename… in a list row's ⋯ edits the title in place in the row, with the same keys.
- AC-3: An empty title, or one equal to the name after trimming, leaves the session
  without a title, and it shows as before the change.
- AC-4: A title works on running and stopped sessions, survives stop and resume, and goes
  with `lado forget`.
- AC-5: A title over 80 characters or with a line break is refused with its reason in the
  UI and the CLI, and nothing changes.
- AC-6: `lado title` reads, sets and clears a title; setting is refused inside an agent;
  `lado ls` shows the title after the name.
- AC-7: The list's search finds a session by its title and by its name.
- AC-8: Setting a title changes neither the session's address, nor its CLI name, nor its
  branches, worktrees or running agents.
- AC-9: A `lado.db` of schema 27 migrates to 28 and keeps its sessions, without titles.
- AC-10: A title set by `lado title` shows on an open page without a reload.

## Docs

- `docs/design/ui.md`: a new section **Session title (decided 2026-10-15, LAD-66)** after
  Session head, holding the tables above (where it shows, where it is set); in Launch and
  session control, the list row's menu holds `Rename…` first and the sentence "no Rename,
  Pin or colour until they do" becomes "no Pin or colour until they do"; in Session head,
  the head's first items are the status dot, the title (or the name), the name when there
  is a title, the pencil, the run time.
- AGENTS.md: `state.py`'s schema 28 (`sessions.title`), the CLI section's `lado title`
  and `lado ls`'s title, `runtime.set_title` as the one rule.
- CHANGELOG.md, under 0.39.0 (unreleased): "A session can have a title, shown in the UI
  over its name: set it with the pencil in the session's head, Rename… in the session
  list, or `lado title`; `lado ls` shows it."

## Release

A minor: a CLI command, an API field and route, a schema migration. It goes into 0.39.0
(unreleased already in CHANGELOG.md).
