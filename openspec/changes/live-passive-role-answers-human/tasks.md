## 1. The role

- [ ] 1.1 `PASSIVE_SUPERVISOR` in `tests/live/test_live.py`: reply ACK; use no tool but
  `send_message` to the human: no command tools, no `send_message` to an agent, no git
  commands, no file edits; no word on how to answer the human (AC-1). Update the comment
  above it (read-only, may answer the human only) and `check_hello`'s docstring if it names
  the role (check: `uv run pytest -m live --collect-only -q tests/live/test_live.py`)

## 2. Docs and regression

- [ ] 2.1 `docs/testing.md`, the paragraph "The passive supervisor of the live kit is
  read-only…": it may answer the human with `send_message` and nothing else (AC-3)
- [ ] 2.2 Regression (AC-2, AC-4): `make lint`, `make test`, the collect-only run above,
  `openspec validate live-passive-role-answers-human --strict`; the build report says the live
  cells are written, not run, and that the first `live.yml` run on main after the merge must be
  watched for the codex cell
