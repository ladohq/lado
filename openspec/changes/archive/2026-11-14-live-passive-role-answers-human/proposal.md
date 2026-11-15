Task: LAD-285

## Why

The live cell of Codex failed on main right after the merge of LAD-260 (run 43637520903,
commit ee62ae3f, model anthropic/claude-haiku-5.5):
`tests/live/test_live.py::test_worker_does_a_task_reports_and_gets_a_message[codex]`,
`assert 'missing' == 'replied'` in `check_hello`. The rerun of the failed cell failed the same
way (attempt 2); attempt 3 passed. The run of 2026-11-12 also went green only on its second
attempt. Claude, Kilo and OpenCode passed every time.

The evidence of attempt 2 (artifact `live-codex`: LADO's log, the supervisor's screen and its
Codex rollout) shows the whole exchange: the supervisor got
`[from human] hello (reply with send_message(to="human") or ask_human)` and answered `ACK` in
its terminal only; LADO queued its one reminder ("your answer to the human's message #9 went
only to your terminal…"), and the supervisor answered `ACK` in its terminal again; the
message ended `missing`. LADO behaved as the reply-check spec says. No reminder of an unread
text (LAD-234) was queued: the test reads the report for the supervisor, so the suspected
double reminder at the turn's end did not happen. This is not a regression of LAD-234.

The cause is in the test. The role of the live kit's passive supervisor
(`PASSIVE_SUPERVISOR`) says "When a message arrives, reply with the single word ACK. Never use
any tool: no spawn_worker, finish_worker or send_message", while `check_hello`, added by
LAD-274 on 2026-11-11, expects the same supervisor to answer the human with `send_message`.
The model gets two contradictory orders; through Codex claude-haiku-5.5 follows the role more
often than through the other CLIs, so the cell is red at random.

## What Changes

- The passive supervisor's role allows one tool use: `send_message` to the human. Everything
  else stays forbidden (no command tools, no `send_message` to an agent, no git commands, no
  file edits); the role still says to reply ACK. The role still says nothing about how to
  answer a message from the human, so `check_hello` still tests LADO's hint and its one
  reminder, as LAD-274 meant.
- The comment above the role and `docs/testing.md` (the paragraph on the live kit's passive
  supervisor) say it may answer the human and nothing else.

## Scope

In: `tests/live/test_live.py` (the role's text, its comment, `check_hello`'s docstring if it
needs a word) and `docs/testing.md`.

## Out of scope

- Saying "hello" to the worker w1 instead (the human's decision on #6815): w1's task says "Do
  nothing else", the same contradiction in a milder form, and the supervisor's case would
  lose its live check.
- Accepting the random reds as they are: the live cells must be trustworthy before RC 0.47.0.
- Any change of LADO's hint or reminder texts: they worked as specified; with the
  contradiction gone, a model that still answers only in its terminal is a fair signal about
  the model, not a defect of the test.
- A retry inside the test or a longer wait: the verdict was `missing`, not a timeout.
- The red attempt 1 of the 2026-11-12 run: its log was not retrievable here (gh returned the
  later attempt's log); the same contradiction explains it, nothing indicates another cause.

## Acceptance

- AC-1: the passive supervisor's role allows `send_message` to the human and forbids every
  other tool use, git command and file edit; it says nothing about how to answer the human.
- AC-2: `check_supervisor_tools` and `check_supervisor_kept_still` and every other assertion
  of the live tests stay as they are and pass with the new role (the supervisor stays
  read-only).
- AC-3: `docs/testing.md` describes the passive supervisor as it now is.
- AC-4: the live tests collect (`uv run pytest -m live --collect-only -q tests/live/test_live.py`),
  `make lint` and `make test` pass; the live cells are "written, not run" before the merge
  (the key of the environment `live` is open only to main and tags), and the first run of
  `live.yml` on main after the merge is to be watched for the codex cell.

## Impact

- Tests and docs only: no change under `src/`, no CHANGELOG.md line (users see nothing), no
  version bump of its own; no delta spec, archived with `--skip-specs`.
