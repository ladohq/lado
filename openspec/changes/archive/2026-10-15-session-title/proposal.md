Task: LAD-66

## Why

The human cannot tell sessions apart. A session's name is taken from its folder (`lado`,
`lado-2`, `lado-3` for three sessions of one repository), and nothing about what a
session is for can be written on it. The task asks for a way to rename a session.

Root cause: the session's name is its identifier, not a label. It is the primary key that
the session's rows in `lado.db` refer to, the tmux session's name, `LADO_SESSION` in every
agent's and `lado mcp`'s environment, the prefix of its branches (`lado/<session>/*`) and
worktree folders (`.lado/worktrees/<session>/`), the session page's address
(`/sessions/<session>`) and what the human types after `lado attach`, `lado stop`,
`lado answer`. It is a slug (`runtime.slug`: lowercase Latin letters, digits, `-`, `_`).
Changing it means changing all of these at once, and a running session's processes
cannot learn a new one.

## What Changes

Chosen with the human (mockup `task/lad-66/mockup-rename.html`, variant A): a session
gets an optional **title**, a label shown over its name; the name stays the identifier.

- **The title**: any text on one line, in any language, at most 80 characters, set at
  any time, for a running session and a stopped one alike. Spaces at its ends are
  trimmed; a title that is then empty or equal to the session's name is no title (stored
  as none), so a name is never shown twice. A title with a line break or another control
  character, or longer than 80 characters, is refused with the reason and nothing
  changes. It is kept across stop and resume and goes with `lado forget`. Two sessions
  may have the same title.
- **Where it shows** (the UI): the session list's row (the title in place of the name;
  the name first in the row's grey line), the collapsed list's icon (its letters and its
  label), the row's and the icon's card, the session's head (the title, the name small
  and grey after it), the browser tab's title, the session's line in Needs you, and the
  browser's notifications. A session without a title shows as today. The list's search
  finds a session by its title or its name.
- **Where it is set** (the UI): a pencil beside the title in the session's head, shown
  on hover and focus, and a double click on the title, edit it in place; **Rename…** in
  the list row's ⋯ menu edits it in place in the row. Enter or leaving the field saves,
  Esc cancels; an empty field clears the title.
- **The CLI**: `lado title <session>` prints the title (or that there is none);
  `lado title <session> TEXT` sets it; `lado title <session> --clear` clears it. Setting
  or clearing is refused inside an agent, as `lado answer` is. `lado ls` prints the title
  after the name.
- **The API**: `SessionInfo.title`; `PUT /api/sessions/{name}/title` sets or clears it
  through the core; `Limits.max_title`.
- Schema 28: `sessions.title`.
- Docs: `docs/design/ui.md` (Session head, the list row's menu, a section Session title),
  AGENTS.md (`state.py` schema 28, the CLI's `lado title`), CHANGELOG.md.
- A minor release (a CLI command, an API field and a schema migration): it goes into
  0.39.0, whose heading CHANGELOG.md already has.

## Scope

- `src/lado/state.py`: `sessions.title`, schema 28 (`MIGRATIONS[27]`), `Session.title`,
  `set_title`.
- `src/lado/runtime.py`: `MAX_TITLE`, `set_title` (the one rule of what a title is).
- `src/lado/cli.py`: `lado title`, the title in `lado ls`.
- `src/lado/server/`: `SessionInfo.title`, `Limits.max_title`, the route
  `PUT /api/sessions/{name}/title`; `web/openapi.json`, `web/src/api.gen.ts`.
- `web/src/`: the title in the list, the strip, the cards, the head, the tab title,
  Needs you and the notifications; the in-place editor; Rename… in the row's menu; the
  search.
- Tests: `tests/test_state.py`, `tests/test_runtime.py`, `tests/test_cli.py`,
  `tests/test_server_session.py`, `tests/agent_helpers.py`, vitest tests of the touched
  components, UI e2e tests in `tests/ui/test_session_head.py` and
  `tests/ui/test_session_list.py`.

## Out of scope

- **Renaming the identifier** (mockup variant B): only for a stopped session, it would
  rename branches, move the worktrees of open runs, change the session's address and
  break its links, and leave a session under two names after a failure half way.
  Refused with the human for the title's cost. `lado rename` stays free for it, should it
  ever be wanted.
- **A title at the start** (a field in the New session window, `lado start --title`):
  by the human's choice; the title is set right after the start.
- **A title set by an agent** (an MCP tool for the supervisor, e.g. from the task's
  name): by the human's choice; added when a kit needs it.
- **The title in `lado log`, `lado answer`'s prompts, the tmux popup's title, telemetry
  and the bug report**: the human types the name there, and the title is the human's
  free text, which telemetry and the bug report never send.
- **Unique titles**: a title is a label, the name tells sessions apart.

## Impact

- UI: the title wherever a session is named on screen; editing in the head and the list.
- CLI: a new command `lado title`; `lado ls` prints the title.
- API: a new field and a new route; `make web-types`.
- Schema: version 28 (`ALTER TABLE sessions ADD COLUMN title TEXT`), a migration as usual
  (`lado stop --all` first when a session runs; `lado update` backs `lado.db` up).
- Parallel work: a branch merged before this one that also bumps the schema makes this
  one renumber its step.
