## Context

A session's name is its identifier (proposal, Root cause). The UI names sessions in
`Sessions.tsx` (the list's `SessionGroup` rows, `StripIcon` with `initials`,
`SessionTip`, `HeadLine`'s `<h1>`, `useTitle(name)`), `NeedsYou.tsx` (`SessionWaits`)
and `Notifications.tsx` (`LADO · <session>`). `SessionInfo` (`server/models.py`,
`session_info`) is the session's form in REST and the change feed; every update of a
`sessions` row is journaled (`state.JOURNALED["sessions"]`), so the feed sends the session
again after any `UPDATE sessions`. The usage triggers on `sessions` count only inserts.

Options, with the human (mockup `task/lad-66/mockup-rename.html`):

1. **Chosen: a title over the name.** One nullable column, one core rule, a field in the
   API, an editor in the UI. Works at any time, touches nothing outside `lado.db`.
   Long-term cost: a session has two names, a label for the eye and an identifier for the
   CLI and links; mitigated by showing the name beside every title.
2. **Rename the identifier, stopped sessions only.** Updates the key in every table that
   refers to it (no `ON UPDATE CASCADE`: a table rebuild or a manual update of each),
   renames `lado/<old>/*` branches, moves `.lado/worktrees/<old>/` with `git worktree
   move` and updates the runs' stored paths, renames the loop's lock file; old links
   break. A failure half way leaves the session split between two names unless every git
   step can be undone. Refused for its cost and risk.
3. **Both** (a title now, a rename later): option 1 now leaves 2 open; `lado rename` is
   kept free for it.

Held against AGENTS.md's Design principles and ROADMAP: neutral core (no provider is
involved: the title lives in `lado.db` and the UI); one source of truth (one column, one
rule in `runtime.set_title`, the limit given to the UI by `Limits.max_title`, the UI's
label from `SessionInfo.title` only); no silent drops (a bad title is refused with its
reason, never cut or cleaned); only what is used (no title at start, no MCP tool, no
uniqueness). ROADMAP's Projects (Later) name a project, not a session, and Stage 7's
desktop app reads the same API.

## Decisions

### D1. `sessions.title`, schema 28

`ALTER TABLE sessions ADD COLUMN title TEXT` (NULL: no title), as `MIGRATIONS[27]`
(`SESSIONS_TITLE`, a constant used by `SCHEMA` too, as `AGENTS_READ_ONLY` is), and
`SCHEMA_VERSION = 28`; `tests/agent_helpers.schema_before` undoes it
(`ALTER TABLE sessions DROP COLUMN title`, SQLite 3.35+ as the earlier steps' undo). No
trigger changes: the journal's `sessions` triggers already record updates; the usage
triggers count inserts only.

### D2. One rule, `runtime.set_title(name, text) -> str | None`

`state.Session.title: str | None`. `runtime.set_title` trims `text` (`None` is a clear),
refuses a control character (`unicodedata.category(c) == "Cc"`: `a title is one line`)
and a length over `MAX_TITLE = 80` after the trim (`a title is at most 80 characters`),
turns an empty text or one equal to the name into None, and stores it with
`state.set_title(name, title)` (one `UPDATE sessions SET title = ? WHERE name = ?`;
0 rows is `NoSuchSession`). It returns the stored title. No check of the session's
status: a title is a label, set while it runs or not. Refusals are `LadoError`s, so the
CLI prints them and the API's `core` turns them into 400.

### D3. API: `PUT /api/sessions/{name}/title`

Body `TitleChange {title: str | None}`, under `Guard.changes`, `known(name, has_db)`
first (404 for an unknown session), then `core(runtime.set_title, name, title)`, and the
answer is the session's `SessionInfo` (`models.session_info(state.get_session(name))`),
so the editor shows what was stored at once, before the feed's item. `SessionInfo.title:
str | None`; `Limits.max_title: int` from `runtime.MAX_TITLE`. `make web-types`.

### D4. One label function in the UI

`web/src/sessionLabel.ts`: `label(session) = session.title ?? session.name`, and
`labelOf(name, sessions)` for places that hold only a name (Needs you, the notifications:
they look the session up in the live list, `useLive().sessions`, and fall back to the
name). Every place in Context goes through it; `initials` takes the label. Where a title
shows, the name is shown beside it as the spec says. `WaitingItem` is unchanged: the
live list is the one source of the label.

### D5. One editor, `TitleEdit.tsx`

A text field (`aria-label` "Session title", placeholder the name, the title as its value),
used by the head (in place of the `<h1>`) and the row (in place of the link's content).
Enter and blur save, Esc cancels; while the request runs the field is read-only; a text
longer than `Limits.max_title` (read with the composer's `GET /api/limits`) shows `<n>
characters, the limit is <limit>` under it and is not sent; the server's refusal shows
under it (`role="alert"`) and the field stays open with the text. A text equal to what
is stored (after the trim) sends nothing. After it closes the focus goes back to its
opener (`onClose` returns it). The head's pencil (`Rename session`, an `icon-button`
with a pencil icon in `icons.tsx`) follows the title; CSS shows it on `.session-head
h1:hover`, its own focus and `@media (hover: none)`; `onDoubleClick` on the `<h1>` opens
the editor too. `SessionRowMenu` gets an item `Rename…` first (a `MenuItem` whose
`onSelect` asks the row to edit; the row holds the editing state).

### D6. CLI: `lado title <session> [TEXT] [--clear]`

`cmd_title`: TEXT and `--clear` together exit 2 (argparse mutually exclusive group);
setting or clearing calls `_human_only("title")` first; reading prints the title, or
`<session> has no title`; setting prints `<session>: title "<title>"` or, when the rule
stored none, `<session> has no title`. It migrates as other commands do. `cmd_ls` prints
`f'{name} "{title}"  {repo}{alive}'` when there is a title, else the line as today.

### D7. Not carried elsewhere

`lado log`, `lado answer`, the gate popup's title, `lado attach` and the tmux names keep
the name: the human types it there. Telemetry and the bug report send no session name
today and get no title (free text of the human). The resume window's Name stays the
name.

### D8. Test layers

Unit for the rule, the state, the CLI and the API (in-process FastAPI client); vitest for
the label, the editor, the head, the row and its menu, Needs you and the notifications;
UI e2e (a browser and a real server) for the editing in the head and in the list and for
a title set by the core while the page is open (the feed). No integration test with the
fake agent: no agent, hook, tmux or MCP process takes part; the cross-process path
(a CLI process writes, the server's feed sends) is covered by the UI e2e test that sets
the title through `lado title` in a subprocess.
