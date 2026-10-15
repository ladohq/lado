# Session title Implementation Plan

**Goal:** A session can have a title, a label shown in the UI over its name, set in place
in the session's head and the session list, or with `lado title`.

**Architecture:** One nullable column `sessions.title` (schema 28), one core rule
`runtime.set_title`, exposed as `SessionInfo.title`, `PUT /api/sessions/{name}/title`,
`Limits.max_title` and the CLI `lado title`. The UI names a session through one label
function and edits the title with one component, `TitleEdit`, in the head and the row.

**Tech Stack:** Python 3.10+, SQLite, FastAPI, React + TypeScript (Vite, vitest),
pytest, Playwright (UI e2e).

**Spec:** `openspec/changes/session-title/` (proposal, `specs/session-title/spec.md`,
`design.md`) and `docs/superpowers/specs/2026-10-15-session-title-design.md`.

## Global Constraints

- `MAX_TITLE = 80` characters, counted after trimming; refused, never cut.
- A control character is Unicode category `Cc`; refused with `a title is one line`.
- Over the limit: `a title is at most 80 characters`.
- Empty after trim, or equal to the session's name: stored as NULL.
- The session's name, address, tmux, branches and worktrees never change.
- UI texts in English: `Rename session` (pencil), `Rename…` (menu), `Session title`
  (field's label), `Enter to save · Esc to cancel · empty shows the name`,
  `<n> characters, the limit is <limit>`.
- CLI texts: `<session>: title "<title>"`, `<session> has no title`; inside an agent
  `_human_only("title")`'s text.
- Schema 28: `ALTER TABLE sessions ADD COLUMN title TEXT`.
- Commit messages: a plain sentence ending in `(LAD-66)`.

## Review Focus

- A title of exactly 80 characters after trimming, with spaces around it: accepted
  (pin in Task 2's tests).
- A title in Cyrillic or with emoji: stored and shown as typed; 80 counts Python
  characters (code points), the UI's check counts the same way (`[...text].length`, not
  `text.length`, which counts UTF-16 units) — pin in Task 2 and Task 4.
- A title set while the editor of another browser is open: the open editor keeps its
  text until it closes, then the row shows the stored title (Task 5's vitest).
- Blur after Esc must not save (Esc cancels, the blur that follows the close sends
  nothing) — Task 4's vitest.
- A refused save keeps the field open; the next Enter tries again with the new text —
  Task 4's vitest.

---

### Task 1: The column and the state

**Files:**
- Modify: `src/lado/state.py` (`SCHEMA`'s `sessions`, `SESSIONS_TITLE`, `MIGRATIONS[27]`,
  `SCHEMA_VERSION = 28`, `Session.title`, `_session`, `set_title`)
- Modify: `tests/agent_helpers.py` (`schema_before`: assert `MIGRATIONS[27] ==
  [state.SESSIONS_TITLE]`, undo with `ALTER TABLE sessions DROP COLUMN title`)
- Test: `tests/test_state.py`

**Interfaces:**
- Produces: `state.Session.title: str | None = None` (last field, after `created_at`);
  `state.set_title(name: str, title: str | None) -> bool` (False when no such session).

- [ ] **Step 1: Write the failing tests** in `tests/test_state.py`:

```python
def test_a_session_has_no_title_until_one_is_set():
    state.add_session(state.Session("s", "/r", None, "claude"))
    assert state.get_session("s").title is None
    assert state.set_title("s", "Review")
    assert state.get_session("s").title == "Review"
    assert state.set_title("s", None)
    assert state.get_session("s").title is None


def test_set_title_of_an_unknown_session_is_false():
    assert not state.set_title("nope", "x")


def test_a_title_survives_stop_and_resume_and_goes_with_forget(): ...  # add, set_title, stop_session, resume (state's resume path), check title; delete_session, add again: None


def test_setting_a_title_is_journaled_as_a_session_update(): ...  # the changes table gets ('sessions', 's', '', 'update')
```

- [ ] **Step 2:** `uv run pytest tests/test_state.py -n0 -k title` — FAIL.
- [ ] **Step 3:** Implement: `SESSIONS_TITLE = "ALTER TABLE sessions ADD COLUMN title
  TEXT"`; the `sessions` table in `SCHEMA` gets `title TEXT` (a fresh database is made at
  the current version); `MIGRATIONS[27] = [SESSIONS_TITLE]`; `Session.title`; `_session`
  reads `row["title"]`; `set_title` is one `UPDATE sessions SET title = ? WHERE name = ?`
  returning `rowcount == 1`. Update `schema_before`.
- [ ] **Step 4:** `uv run pytest tests/test_state.py tests/test_migrations*.py -n auto`
  and every test that uses `previous_schema` (`grep -rl previous_schema tests`) — PASS.
- [ ] **Step 5:** Commit `Sessions keep an optional title, schema 28 (LAD-66)`.

### Task 2: The core rule

**Files:**
- Modify: `src/lado/runtime.py` (`MAX_TITLE`, `set_title`)
- Test: `tests/test_runtime.py`

**Interfaces:**
- Consumes: `state.set_title`.
- Produces: `runtime.MAX_TITLE: int = 80`; `runtime.set_title(name: str, text: str |
  None) -> str | None` (the stored title); raises `NoSuchSession` and `LadoError`.

- [ ] **Step 1: Failing tests:**

```python
@pytest.mark.parametrize(
    "text, stored",
    [
        ("Review", "Review"),
        ("  Ревью kit-sdlc  ", "Ревью kit-sdlc"),
        ("   ", None),
        ("", None),
        (None, None),
        ("s", None),
        ("  s ", None),
        ("x" * 80, "x" * 80),
        ("  " + "я" * 80 + " ", "я" * 80),
        ("🚀 launch", "🚀 launch"),
    ],
)
def test_set_title_stores_what_the_rule_says(text, stored): ...  # session "s"


@pytest.mark.parametrize(
    "text, reason",
    [
        ("x" * 81, "a title is at most 80 characters"),
        ("a\nb", "a title is one line"),
        ("a\tb", "a title is one line"),
        ("a\x00b", "a title is one line"),
    ],
)
def test_set_title_refuses_and_changes_nothing(text, reason): ...  # title stays "Old"


def test_set_title_of_an_unknown_session_is_refused(): ...  # NoSuchSession


def test_set_title_works_on_a_stopped_session(): ...
```

- [ ] **Step 2:** `uv run pytest tests/test_runtime.py -n0 -k title` — FAIL.
- [ ] **Step 3:** Implement:

```python
MAX_TITLE = 80  # characters of a session's title, after trimming


def set_title(name: str, text: str | None) -> str | None:
    """Set or clear the session's title, a label for the human over its name (which stays
    its identifier). Trimmed; empty or equal to the name is no title. Returns what is
    stored."""
    title = (text or "").strip()
    if any(unicodedata.category(char) == "Cc" for char in title):
        raise LadoError("a title is one line")
    if len(title) > MAX_TITLE:
        raise LadoError(f"a title is at most {MAX_TITLE} characters")
    stored = title if title and title != name else None
    if not state.set_title(name, stored):
        raise NoSuchSession(...)  # as the other callers build it
    return stored
```

- [ ] **Step 4:** Tests PASS.
- [ ] **Step 5:** Commit `The core sets a session's title by one rule (LAD-66)`.

### Task 3: CLI and API

**Files:**
- Modify: `src/lado/cli.py` (`title` parser, `cmd_title`, `cmd_ls`)
- Modify: `src/lado/server/models.py` (`SessionInfo.title`, `session_info`, `Limits.max_title`,
  `TitleChange`)
- Modify: `src/lado/server/app.py` (`limits`, the route)
- Modify: `web/openapi.json`, `web/src/api.gen.ts` (`make web-types`)
- Test: `tests/test_cli.py`, `tests/test_server_session.py`, the test of `/api/limits`

**Interfaces:**
- Consumes: `runtime.set_title`, `runtime.MAX_TITLE`.
- Produces: `SessionInfo.title: str | None`; `Limits.max_title: int`;
  `PUT /api/sessions/{name}/title` with `TitleChange {title: str | None}` → `SessionInfo`.

- [ ] **Step 1: Failing tests** — CLI:
  `test_title_sets_reads_and_clears` (prints `s: title "Review"`, `Review`, `s has no title`),
  `test_title_with_text_and_clear_exits_2`, `test_title_is_refused_inside_an_agent`
  (monkeypatch `LADO_AGENT=w1`; reading still works), `test_title_of_an_unknown_session`,
  `test_ls_shows_the_title_after_the_name` (`s "Review"  <repo>` and a session without a
  title unchanged). API: `test_put_title_sets_it_and_answers_the_session`,
  `test_put_title_null_clears_it`, `test_put_title_refused_is_400_with_the_reason`,
  `test_put_title_of_an_unknown_session_is_404`, `test_put_title_needs_the_origin`
  (`Guard.changes`: a foreign Origin is refused), `test_sessions_carry_their_title`,
  `test_limits_name_the_title_limit`.
- [ ] **Step 2:** `uv run pytest tests/test_cli.py tests/test_server_session.py -n auto -k
  "title or limits"` — FAIL.
- [ ] **Step 3:** Implement as `design.md` D3 and D6 say; `cmd_title` is registered so
  that it migrates as other commands (not in the no-migrate list).
- [ ] **Step 4:** Tests PASS; `make web-types`; `make web` (stale-types check) PASS.
- [ ] **Step 5:** Commit `lado title and the API set a session's title (LAD-66)`.

### Task 4: The label and the editor (web)

**Files:**
- Create: `web/src/sessionLabel.ts`, `web/src/sessionLabel.test.ts`
- Create: `web/src/TitleEdit.tsx`, `web/src/TitleEdit.test.tsx`
- Modify: `web/src/api.ts` (`setSessionTitle(name, title) => Promise<SessionInfo>`),
  `web/src/icons.tsx` (`PencilIcon`), `web/src/fakes.ts` (sessions with `title`)

**Interfaces:**
- Produces: `label(session: SessionInfo): string`; `labelOf(name: string, loaded:
  Loaded): string`; `titleLength(text: string): number` (`[...text.trim()].length`);
  `<TitleEdit session={SessionInfo} onClose={() => void} />` (Enter/blur save, Esc cancel).

- [ ] **Step 1: Failing vitest tests:** label with and without title; `labelOf` falls back
  to the name for a session not in the list; TitleEdit: Enter saves the trimmed text and
  calls `onClose`; Esc sends nothing and the blur after it sends nothing; the same text
  as stored sends nothing; 81 characters (and 81 Cyrillic letters, 80 emoji count as 80)
  shows `81 characters, the limit is 80` and Enter sends nothing; a 400 shows its text in
  `role="alert"` and keeps the field open, a second Enter sends again; an empty field
  sends `null`.
- [ ] **Step 2:** `cd web && npx vitest run sessionLabel TitleEdit` — FAIL.
- [ ] **Step 3:** Implement (`design.md` D4, D5); the limit from `getLimits()`.
- [ ] **Step 4:** PASS.
- [ ] **Step 5:** Commit `The web UI names a session by its title and edits it in place (LAD-66)`.

### Task 5: The title on every screen

**Files:**
- Modify: `web/src/Sessions.tsx` (search by title or name; row: label + name in the grey
  line; `StripIcon` and `initials`; `SessionTip`; `HeadLine`: `<h1>` label, `.session-name-id`,
  the pencil, double click, `TitleEdit` in place; `useTitle(label)`),
  `web/src/SessionRowMenu.tsx` (`Rename…` first; the row holds the editing state),
  `web/src/NeedsYou.tsx`, `web/src/Notifications.tsx`, `web/src/styles.css`
  (`.session-name-id`, the pencil's visibility rule, the field in the head and the row)
- Test: `web/src/Layout.test.tsx`, `web/src/NeedsYou.test.tsx`, a notifications test,
  `web/src/Menu.test.tsx` if the row menu is tested there

- [ ] **Step 1: Failing vitest tests:** a titled session's row, head, tab title, card,
  strip icon, Needs you line and notification show the title with the name as the spec
  says; an untitled one renders as before (existing tests stay green unchanged); search
  `rename` and `lado-2` both keep the titled row; Rename… opens the field in the row and
  Esc returns the focus to ⋯; the pencil opens it in the head and Enter returns the focus
  to the pencil; a feed update of the title while the field is open keeps the typed text,
  and the row shows the stored title after Esc.
- [ ] **Step 2:** `cd web && npx vitest run` — the new tests FAIL.
- [ ] **Step 3:** Implement to the mockup `task/lad-66/mockup-rename.html` (A1–A4).
- [ ] **Step 4:** `make web` PASS.
- [ ] **Step 5:** Commit `The session list, head, Needs you and notifications show the title (LAD-66)`.

### Task 6: UI end to end

**Files:**
- Modify: `tests/ui/test_session_head.py`, `tests/ui/test_session_list.py`

- [ ] **Step 1:** Tests:
  `test_the_pencil_renames_the_session_in_place` (pencil → type → Enter: head, row and
  `page.title()` show it; the URL is unchanged; screenshot with `shot`),
  `test_rename_from_the_row_menu_and_esc` (Rename… → type → Esc: nothing changed; then
  Rename… → empty → Enter on a titled session: the name shows again; screenshot),
  `test_a_title_set_by_the_cli_shows_without_a_reload` (`subprocess.run(["lado", "title",
  session, "Review"])` with the test's environment, as the module runs other commands;
  the row and head show `Review`).
- [ ] **Step 2:** `uv run pytest -m ui tests/ui/test_session_head.py
  tests/ui/test_session_list.py` — PASS (the screenshots in `<temp dir>/lado-ui-shots/`
  go into the build report as run artifacts).
- [ ] **Step 3:** Commit `UI e2e tests of renaming a session (LAD-66)`.

### Task 7: Docs

- [ ] `docs/design/ui.md`, AGENTS.md and CHANGELOG.md as the design doc's Docs section
  says. Commit `Docs of the session title (LAD-66)`.

### Task 8: Regression

- [ ] `make lint`; `make test`; `uv run pytest -m ui tests/ui/test_session_head.py
  tests/ui/test_session_list.py tests/ui/test_needs_you.py tests/ui/test_sessions_strip.py`;
  `make web`; `openspec validate session-title --strict`; `openspec validate --specs
  --strict`; by hand, a copy of a real schema-27 `lado.db` migrated with `lado ls`
  (its sessions there, no titles), recorded in the build report.

## Requirements → tests

| Requirement | Tests (layer) |
|---|---|
| A session has an optional title over its name | `test_state.py` title tests (unit), `test_runtime.py` `set_title` tests (unit), the migration via `schema_before` (unit) |
| The UI shows a session by its title, with its name beside it | `sessionLabel.test.ts`, `Layout.test.tsx`, `NeedsYou.test.tsx`, notifications (vitest); `test_a_title_set_by_the_cli_shows_without_a_reload` (UI e2e) |
| The human sets the title in place, in the head and in the list | `TitleEdit.test.tsx`, `Layout.test.tsx` (vitest); `test_the_pencil_renames_the_session_in_place`, `test_rename_from_the_row_menu_and_esc` (UI e2e) |
| `lado title` reads and sets a session's title | `test_cli.py` title and ls tests (unit) |
