## 1. The mark and the check

- [x] 1.1 `state.py`: the column `read_reminded` (D1), `SCHEMA_VERSION = 40`, `MIGRATIONS[39]`
  (add it, set 1 on every existing row), the table in `SCHEMA`, `tests/agent_helpers.previous_schema`.
  Check: the migration test of `tests/test_state.py` from version 39; `make test`.
- [x] 1.2 `state.check_unread` (D2). Check: unit tests of each state (`pending`, `sent`,
  `delivered`, `read`), a line without a body, artifacts only, and no message returned twice.

## 2. The reminder

- [x] 2.1 `hooks.py`: `UNREAD_REMINDER` and its use at a clean `TURN_END` after the reply check
  and before `_idle` (D3). Check: unit tests of the hook: the one and several texts exactly, no
  reminder on an error turn, a batch confirmed by `continued` is checked, the hook's own
  hand-over is not.
- [x] 2.2 Integration with the fake agent (a new file
  `tests/integration/test_unread_reminder.py`): a worker ends its turn without `read_messages` → one
  reminder from `lado`, the worker reads, no second reminder; a turn ending on an error → none;
  a read message → none. Integration tests whose counts of messages change by the reminder are
  updated. Check: `uv run pytest -m integration -n auto <changed files>`.

## 3. Docs and CHANGELOG

- [x] 3.1 `docs/design/agents.md` (the check at a turn's end, next to the forgotten-reply
  check), `docs/design/modules.md` (`state.check_unread`, `hooks`).
- [x] 3.2 CHANGELOG.md: `## 0.46.3 (unreleased)` becomes `## 0.47.0 (unreleased)` (a schema
  migration); under Fixed: an agent that leaves a message's text unread gets one reminder to
  read it.

## 4. Checks

- [x] 4.1 `make lint`, `make test`, the integration files of 2.2 with `-m integration`,
  `openspec validate unread-message-reminder --strict`, `openspec validate --specs --strict` and
  the trial archive of the settings' Checks.
