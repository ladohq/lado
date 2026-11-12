Task: LAD-278

## Why

LADO 0.46.2 is a patch (fixes only), released at the human's choice through the release
candidate 0.46.2rc1 (docs/release.md, section 1). Before the RC's commit its release's checklist,
`docs/releases/0.46.2.md`, gets the section `## 0.46.2rc1` (docs/release.md, section 2, step 0,
and 4.7), in a pull request of its own that the human reads; `scripts/rc_check.py` prints that
section's items after the checks of every RC.

Facts the section rests on (checked on `da59cd18`, main):

- The last final is `v0.46.1`. `git log --first-parent v0.46.1..origin/main`: LAD-274 (#292)
  alone.
- `## 0.46.2 (unreleased)` holds one item under `### Fixed`, already in line with docs/release.md's
  rules for its items (a bold title, three lines, the user's words, no task key): it stays as it is.
- `SCHEMA_VERSION` is 39 at `v0.46.1` and on main: the schema does not move, so 4.4's `rollback`
  holds and the user's own way back on a test home is not needed; 4.2 and 4.6 hold as for every
  first RC of a cycle.
- Since `v0.46.1` nothing under `docker/` changed: 4.5's installers are not run.
- The exact lines the human sees: the hint `runtime.HUMAN_REPLY_HINT`, ` (reply with
  send_message(to="human") or ask_human)`, at the end of the human's line in the agent's terminal;
  the reminder `hooks.REPLY_REMINDER`, typed as `[from lado] …`; the chat's note `<agent> replied
  only in its terminal` (`web/src/Chat.tsx`).
- The live test `check_hello` (LAD-274) runs on every provider in `live.yml`, on the live models
  (claude-haiku-5.5 for Codex, Kilo and OpenCode since LAD-273), not on weak ones; the experiment
  of LAD-274 is the only evidence for weak models. So the hand checks take OpenCode and Kilo CLI on
  free weak models, and Claude Code for the strong model's chat (the human's answer #6340, 3).
- Going back: 0.46.2 stores the new reply state `reminded` in the column `reply_state` that 0.46.1
  reads; 0.46.1's API model takes only `replied` and `missing` (checked on `v0.46.1`: pydantic
  refuses `reminded`), and 0.46.1's `check_replies` never touches a message that has a state. A
  message stopped between its reminder and its verdict therefore breaks that session's chat on
  0.46.1. The window is the seconds of one turn; the human judged it not worth a fix: nobody is
  expected to go back to 0.46.1, and a new session is the way round (#6340, 2).

The human approved the scale and the draft's content (answer #6340).

## What Changes

### `docs/releases/0.46.2.md`, a new file

Its form is 4.7's. The text below is the file as approved; the developer writes it as it
stands and changes an exact line only where the code says otherwise (tasks 1.2):

````markdown
# LADO 0.46.2: the release's checks

The last final is 0.46.1. The database's schema stays at 39, so 4.4's `rollback` holds but
not the user's own way back on a test home; 4.2 and 4.6 hold as for every first RC of a
cycle. Those checks of every RC are not repeated here; this file holds what 0.46.2 itself
needs: how agents answer the human in the chat (the rule in their instructions, the hint on
the human's line, LADO's one reminder) on a weak model and on a strong one, and what going
back to 0.46.1 does to a message still waiting for its reminder's turn. Neither
`docker/install.sh`, `docker/install.ps1` nor the image's `Dockerfile` changed since
v0.46.1, so 4.5's installers are not run.

## 0.46.2rc1

The RC: tag `v0.46.2rc1`, commit `<filled in at the RC>`; `live.yml` on it is green (run
`<filled in at the RC>`). The exact lines below are the code's; where the code has no fixed
text, the line says what to look for.

### Before you start

- A Mac with your LADO 0.46.1; `uv`, `tmux`, `git`; Docker Desktop for 4.5 and 4.6.
- The CLIs on the Mac: Claude Code logged in (with the human's yes); OpenCode and Kilo CLI
  need no login for their free models.
- A test repository for three new sessions.

### Answers in the chat

On the RC, three new sessions of the built-in supervisor on the test repository: OpenCode
on one of its free weak models (e.g. Qwen3-Coder-Next or Nemotron), Kilo CLI on a free weak
model, and Claude Code on its default model. Write to each supervisor in the chat; watch the
chat and the supervisor's terminal.

- [ ] **A weak model answers "привет" in the chat.** In the OpenCode and the Kilo session, write «привет» and nothing on how to answer.
  - The supervisor's answer shows in the chat, by itself or after LADO's reminder; no note
    `supervisor replied only in its terminal` under your message.
  - Its terminal shows your line as `[from human] привет (reply with send_message(to="human")
    or ask_human)`.
- [ ] **An answer left in the terminal gets one reminder.** When a weak model answered in its terminal only (try two or three more short questions until it does).
  - Its terminal then gets one line `[from lado] your answer to the human's message #<id>
    went only to your terminal, which the human does not see. If it needs an answer, use
    send_message(to="human") or ask_human; else do nothing.`, and no second one for that
    message.
  - The note `supervisor replied only in its terminal` shows only when the turn after the
    reminder wrote nothing to you either.
- [ ] **A thanks needs no answer.** In each of the three sessions, after an answer, write «спасибо».
  - No reply, or one short line; no empty note («Greeting back to human»), no second copy of
    an earlier answer. The note under «спасибо» may say `replied only in its terminal`: that
    is the design.
- [ ] **A strong model talks as before.** In the Claude Code session: a question, then a task for a worker.
  - One answer per question, no duplicates; the worker's report is not retold to you in full;
    a question card it asks shows with its choices.

### Going back (4.4)

- [ ] **What 0.46.1 loses.** The schema does not move; on 0.46.1 your line has no hint and an answer left in the terminal gets no reminder.
  - A message whose reminder was sent but not yet decided when the session stopped stays so
    in `lado.db`, and 0.46.1 does not load that session's chat; a new session's chat loads.

### What covers the CHANGELOG's items

The one item of `## 0.46.2 (unreleased)` at the RC's commit, with what covers it. An
item with a check above is tried there.

Fixed:

1. Agents on weak models answer you in the chat: the rule, the hint and the reminder (unit
   `tests/test_runtime.py`, `tests/test_server_messages.py`; integration
   `tests/integration/test_human_messages.py`, `test_agents.py`, `test_fake_agent.py`; the
   browser `tests/ui/test_status_marks.py`, `tests/ui/test_chat.py`; vitest
   `web/src/Chat.test.tsx`; live `tests/live/test_live.py`'s hello on every provider, on the
   live models, not weak ones).
````

The two placeholders of the RC's paragraph (`<filled in at the RC>`) stay in this pull request:
the commit and `live.yml`'s run exist only after it is merged, and are filled in with the RC.

### `tests/test_rc_check.py`

The test over the repository's real checklists (`test_the_repositorys_own_checklists_have_no_warning`)
also checks `0.46.2rc1` against `docs/releases/0.46.2.md`: no warning line, the every-RC lines
first, and the RC's own items after them.

### After the merge: the RC (no file of this pull request)

On main with this pull request merged, as docs/release.md section 2, steps 1-4:
`uv version 0.46.2rc1`, a commit `Release candidate 0.46.2rc1` of `pyproject.toml` and `uv.lock`
alone pushed to main, CI and the smoke green on it, `gh workflow run live.yml` on that commit with
every cell green, then the tag `v0.46.2rc1` pushed; each push with the human's yes. The session's
lead does it with the human; the freeze starts with the RC.

## Scope

- `docs/releases/0.46.2.md` (new) and the real-file test of `tests/test_rc_check.py`.

## Out of scope

- CHANGELOG.md: its one item already follows docs/release.md's rules.
- The version bump, the RC's commit, `live.yml` and the tag: the session's lead does them with
  the human after the merge; the integrator never bumps the version or tags.
- `docs/release.md` and `scripts/rc_check.py`: no rule of the release changes, so the change has
  no delta.
- A fix of the way back for a `reminded` message (0.46.2 clearing it at a stop, or keeping it out
  of the column 0.46.1 reads): the human's decision #6340, 2; nobody is expected to go back to
  0.46.1, and a new session's chat loads. The checklist names it under Going back; no BACKLOG
  entry, as the human asked to give it no more attention.
- Codex by hand, and weak models in the container: the live test runs Codex; nothing in the image
  changed (#6340, 3 and 4).
- 4.5's installers and 4.4's user's own way back on a test home: nothing under `docker/` changed,
  and the schema does not move.
- Moving the task to review: this pull request is not the task's last; LAD-278 stays in progress
  until the final 0.46.2.

## Impact

- Docs and one unit test; no code, API, MCP, CLI or schema change. The release it prepares is a
  patch (0.46.2).
