# First message at a session's start: design

Task: LAD-19. Change: `openspec/changes/first-message/`. Mockup: run artifact
`task/lad-19/mockup-first-message.html` (v2, variant C).

## Problem

A supervisor starts with nothing to do: the human waits for it, then types the first task
into the chat or the terminal. The core already queues a supervisor's first input before
it starts (a resume's messages, a supervisor-started session's brief); the human has no way
into that queue. Root cause: no option in `lado start`, no field in the New session window,
no parameter of `runtime.start_session` for the human's text.

## What the user sees after the change

**In the CLI**

```
lado start [<repo>|<git-url> [<folder>]] [--prompt TEXT | --prompt-file FILE|-] ...
```

1. `--prompt "Take LAD-19"` or `--prompt-file brief.md` (`-`: stdin) gives the
   supervisor a first message from the human. The output says `first message: queued for
   the supervisor`.
2. The text is read and checked first: empty, over 8000 characters, an unreadable file or
   both options are refused before any clone or start.
3. On a stopped session `lado start` resumes it, and the message comes after LADO's
   `session resumed: …`.

**In the New session window**

4. A folded row **First message to the supervisor (optional)** above Advanced, in New and
   Resume, for a folder and a clone alike; folded each time the window opens, so the
   window is one line taller than today.
5. Opened: a text field (4 lines, grows by dragging) and the note "sent to the supervisor
   as your message once it starts; its answer comes in the chat". Folded with text, the
   row shows the text's first line. Over 8000 characters the note says so and the start
   button is off. An empty field sends nothing.

**After the start**

6. The Activity chat shows the text as the human's message to the supervisor; the
   supervisor answers in the chat, as to any message of the human. `lado log` shows it from
   `human` to `supervisor` with the summary `the human's first message` and the text
   indented under it.
7. The text never reaches an agent CLI's command line: Kilo and OpenCode, which take their
   first lines on `--prompt`, get the fixed line `[from human] the human's first message
   (#<id>, <n> lines: call read_messages)`.

## Architecture

- `src/lado/runtime.py`: `check_prompt`, `FIRST_MESSAGE`, `start_session(prompt=...)`
  queues the message after LADO's own before-start messages.
- `src/lado/cli.py`: `--prompt` / `--prompt-file`, read and checked in `cmd_start` before
  `_start_clone` and `start_session`.
- `src/lado/server/models.py`, `app.py`: `Launch.prompt`, `Resume.prompt`.
- `web/src/Launch.tsx`, `styles.css`: the First message row.

## Choices and their long-term cost

See `design.md` Options: a `prompt` of `start_session` (chosen; one parameter, reused by
Projects later), sending it after the start with `write_as_human` (races the first hook,
costs Codex a turn, duplicated in CLI and UI), generalising `FirstInput` (mixes LADO's
brief with the human's text). Decisions D1–D8 in `design.md`.

## Tests by layer (AGENTS.md, Testing)

| Requirement | Layer | Where |
|---|---|---|
| A session starts with the human's first message (new, resume, order, failed start) | unit | `tests/test_runtime.py` |
| The first message is checked before anything changes | unit | `tests/test_runtime.py` |
| The human's text never goes on an agent's command line (OpenCode/Kilo argv, Codex no FIRST_INPUT) | unit | `tests/test_runtime.py`, `tests/test_codex.py` |
| lado start takes a first message (options, stdin, file errors, git URL before clone, resume, output line) | unit | `tests/test_cli.py` |
| API `prompt` of start and resume | unit | `tests/test_server_launch.py` |
| The window's row (folded, peek, sent, empty, limit, resume, clone) | vitest | `web/src/Launch.test.tsx` |
| The supervisor gets the message with its first hook, after LADO's on a resume (crosses tmux, hooks, `lado mcp`) | integration | `tests/integration/test_session_start.py` |
| Start with a first message from the window; the chat shows it | UI e2e | `tests/ui/test_launch.py` |

Regression: `make lint`, `make test`, `uv run pytest -m integration -n auto
tests/integration/test_session_start.py`, `uv run pytest -m ui tests/ui/test_launch.py`,
`make web`; CI runs the rest (`make check`, smoke).

## Docs

`docs/design/ui.md` (Launch and session control: the row, replacing "No first message"),
AGENTS.md (How agents talk: a supervisor's first input may be the human's first message;
Try it locally: `--prompt` / `--prompt-file`), README's start (one line), CHANGELOG.md
`## 0.37.0 (unreleased)`.
