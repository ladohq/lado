## 1. The failing tests

- [x] 1.1 `tests/test_state.py` (unit): requirement "A question a stop closes says the
  session stopped": `stop_session`, `stop_for_container`, `give_up_resume`, `fail_resume` set
  `stopped`; `delete_agent` and `agent_ended` keep `closed`. Run: `uv run pytest -n0
  tests/test_state.py -k stopped`.
- [x] 1.2 `tests/test_runtime.py` (unit): the requirement's reply scenario, and requirement
  "The resumed supervisor gets the questions a stop closed" (text and order of the notice,
  attachments) and "A stopped question is told once" (listed again after a dropped notice and
  a failed resume).
- [x] 1.3 `tests/test_runtime.py`, `tests/test_cli.py`, `tests/test_server_launch.py` (unit):
  requirement "A stop says how many open questions it closes": `stop-preview`, `lado stop`.
- [x] 1.4 `web/src/Chat.test.tsx` and `web/src/Launch.test.tsx` (vitest): the card's two texts,
  the popover's line for 0, 1 and 2. Run: `make web`.
- [x] 1.5 `tests/integration/test_human_messages.py` (integration, crosses processes): the
  fake agent asks, `lado stop`, resume; the new supervisor's `read_messages` holds the
  question, and the chat API says `stopped`. Also with the server's container stop
  (`LADO_CONTAINER=1`). Run: `uv run pytest -m integration -n0 <file>`.
- [x] 1.6 `tests/ui/test_chat.py` (UI e2e): after a stop the card reads "Closed: the session
  stopped"; `tests/ui/test_launch.py`: the popover's line. Run: `uv run pytest -m ui <files>`.

## 2. The change

- [x] 2.1 `state.py`: `QUESTION_STOPPED`, `_close_questions` takes the state, `_stop_session`
  counts and writes it; `open_questions`; the listing and marking of design D3. Check: 1.1.
- [x] 2.2 `runs.py`, `runtime.py`: the notice in `runs.resume`, the shared lines of
  `ask_recommendation`, `Stopped.questions`, `StopPreview.questions`. Check: 1.2, 1.3.
- [x] 2.3 `cli.py`, `server/app.py`, `server/models.py`: `lado stop`'s line, `stop-preview`,
  `question_state`, the comment on `answered_by`; `make web-types`. Check: 1.3.
- [x] 2.4 `web/src/Question.tsx`, `SessionControl.tsx`, to `mockup-stopped-question.html`.
  Check: 1.4, 1.6.

## 3. Docs and the record

- [x] 3.1 `docs/design/ui.md` (A question's closed card; Stop), `docs/design/agents.md`
  (questions closed by a stop, the resume's notice), `docs/cli.md` (`lado stop`). Check: read
  against the delta.
- [x] 3.2 CHANGELOG.md under `0.45.0 (unreleased)`, Fixed. Check: docs/release.md's rules.
- [x] 3.3 BACKLOG.md, in a commit of its own: `lado server stop` by hand in the container
  stops every session of its `LADO_HOME`.
- [ ] 3.4 Regression: the settings' **Checks** for the changed files; `openspec validate
  stopped-question-notice --strict` and `openspec validate --specs --strict`.
