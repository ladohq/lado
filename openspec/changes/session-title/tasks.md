Plan: `docs/superpowers/plans/2026-10-15-session-title.md` (each task's tests and steps).
Design doc: `docs/superpowers/specs/2026-10-15-session-title-design.md`.

## 1. The column and the state (D1)

- [ ] 1.1 `sessions.title`, `SESSIONS_TITLE`, schema 28 (`MIGRATIONS[27]`), `Session.title`,
  `state.set_title`; `tests/agent_helpers.schema_before`. Check: `uv run pytest
  tests/test_state.py -n auto` and the tests that use `previous_schema`.

## 2. The core rule (D2)

- [ ] 2.1 `runtime.MAX_TITLE`, `runtime.set_title` (trim, Cc, length, empty or the name is
  none, unknown session). Check: `uv run pytest tests/test_runtime.py -n auto -k title`.

## 3. CLI and API (D3, D6, D7)

- [ ] 3.1 `lado title <session> [TEXT] [--clear]`, the title in `lado ls`. Check: `uv run
  pytest tests/test_cli.py -n auto -k "title or ls"`.
- [ ] 3.2 `SessionInfo.title`, `Limits.max_title`, `PUT /api/sessions/{name}/title`;
  `make web-types`. Check: `uv run pytest tests/test_server_session.py -n auto`, `make web`.

## 4. The web UI (D4, D5)

- [ ] 4.1 `sessionLabel.ts`, `TitleEdit.tsx`, `setSessionTitle`, `PencilIcon`. Check:
  `cd web && npx vitest run sessionLabel TitleEdit`.
- [ ] 4.2 The title in the list (search too), the strip, the cards, the head with its
  pencil, the tab title, Needs you, the notifications; Rename… in the row's menu. Check:
  `make web`.
- [ ] 4.3 UI e2e: the pencil, the row's Rename… and Esc, a title set by `lado title` on an
  open page; screenshots as run artifacts. Check: `uv run pytest -m ui
  tests/ui/test_session_head.py tests/ui/test_session_list.py`.

## 5. Docs

- [ ] 5.1 `docs/design/ui.md` (Session title, the row's menu, Session head), AGENTS.md
  (schema 28, `lado title`, `runtime.set_title`), CHANGELOG.md (0.39.0).

## 6. Regression

- [ ] 6.1 `make lint`, `make test`, the changed UI e2e files with `-m ui`, `make web`,
  `openspec validate session-title --strict`, `openspec validate --specs --strict`; a
  migration of a copy of a real schema-27 `lado.db`, in the build report.
