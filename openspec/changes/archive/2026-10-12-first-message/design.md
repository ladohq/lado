## Context

A supervisor's first input is its queue at its first hook (AGENTS.md, How agents talk):
`runtime.start_session` queues messages for it with `state.queue_message(...,
before_start=True)` before it is stored: a resume's `session resumed: …` and step
messages (`runs.resume`), and a supervisor-started session's brief (`FirstInput`, only
with `resume=False`). The human's messages go through `runtime.write_as_human` (the UI's
composer), which needs a running session. `lado start` (`cli.cmd_start`, `_start_clone`)
has no option for a message; the UI's `POST /api/sessions` (`models.Launch`) and
`POST /api/sessions/{name}/resume` (`models.Resume`) none either, and docs/design/ui.md
says "No first message".

Root cause: the queue before the start exists; the human has no way into it.

## Options

1. **A `prompt` of `start_session`, queued as the human's message before the start**
   (chosen). One parameter, one check, the existing before-start queue; the CLI and the
   server pass the text. Long-term cost: one more parameter of `start_session`; Projects
   (ROADMAP, Later) send the same `prompt` with their `where`.
2. **Send it after the start with `write_as_human`** (the UI posts a message once the
   start answers; the CLI calls it after `start_session`). No core change, but the message
   races the supervisor's first hook (it may be typed in a second hand-over instead of with
   the first input), a Codex supervisor costs a `FIRST_INPUT` turn first, and the CLI and
   UI each carry the step. Rejected.
3. **Generalise `FirstInput`** (a sender, no records) and allow it on a resume. One type
   for two meanings: `FirstInput` carries copied artifacts and LADO's text, and its
   resume ban protects the brief's one-approval rule. Rejected: a plain `prompt` keeps
   the two apart.

Held against ROADMAP.md: Projects (Later) start sessions with their own `where` and reuse
the window's row and `prompt`; the desktop app (Stage 7) runs the same server and window.
Design principles: *Neutral core*: the queue is the provider-neutral channel; every
provider gets it as any first input (Claude Code typed, Kilo and OpenCode on `--prompt`
with the fixed summary, Codex as its first `[PROMPT]`, which also spares its
`FIRST_INPUT`); *One source of truth*: one check (`runtime.check_prompt`) and one limit
(`runtime.MAX_MESSAGE`, the UI's `Limits.max_message`); *No silent drops*: a bad text is
refused before anything starts, a failed start drops it with the queue as today and says
so as today; *Only what is used*: text only, no files, no templates.

## Decisions

- **D1. `runtime.start_session(..., prompt: str | None = None)`.** `prompt` is checked by
  `runtime.check_prompt(text) -> str` (stripped text; `LadoError` for an empty one,
  `the first message is empty`, or one over `MAX_MESSAGE`, `the first message is <n>
  characters, the limit is <limit>`, counted after stripping as `_human_text` counts)
  at the top of `start_session`, next to the `first` check, before `check_repo`. `None`
  means no message; an empty string is refused (a CLI flag given empty is a mistake; the
  UI sends `None` for an empty field).
- **D2. The message.** `state.queue_message(session, state.HUMAN, SUPERVISOR,
  FIRST_MESSAGE, text, before_start=True)` with `FIRST_MESSAGE = "the human's first
  message"`, inside the same `try` as the other before-start messages and after them
  (after `runs.resume` and after `first`), so a failed start's undo drops it with them.
  The summary is fixed and the body is always the whole text, also for one short line:
  Kilo and OpenCode take the queue's lines at launch on `--prompt` (argv, which `ps`
  shows), so a summary made from the text would put it there; one rule for every
  provider. The chat shows a human's message by its body (`Chat.tsx`: `body || summary`),
  so the human sees their text; `lado log` shows the summary with the body under it.
- **D3. Sender `human`.** It is the human's message: the chat shows it as theirs, the
  supervisor's instructions make it answer with `send_message(to="human")`, and the
  turn's-end reply check (`replied` / `missing`) covers it as any human message. No copy
  to the supervisor is needed (it is to the supervisor).
- **D4. `start_approved_session` passes no `prompt`.** Its brief is its first input;
  `prompt` and `first` may both be given to `start_session` (the order is `first`, then
  `prompt`), but no caller does now.
- **D5. CLI.** In `lado start`'s parser a mutually exclusive group of `--prompt TEXT` and
  `--prompt-file FILE` (help: "a first message to the supervisor ...; FILE - reads
  stdin"). `cmd_start` reads it first (`_read_prompt(args)`: the file as UTF-8, `-` as
  `sys.stdin.read()`; an `OSError` or `UnicodeDecodeError` is `lado: cannot read the first
  message from <FILE>: <reason>`, exit 1) and calls `runtime.check_prompt` before
  `_start_clone` clones or `start_session` runs; `_start_clone` keeps the read text in
  `args` so the second `cmd_start` call after the clone does not read stdin again. After
  the `Started session` / `Resumed session` line it prints `first message: queued for the
  supervisor`. Argv: `lado start`'s own argv is short-lived (it exits, or replaces itself
  with `tmux attach` by `execvpe`); the rule "no message text on an agent's command line"
  is about the agents, which never get it (D2).
- **D6. API.** `models.Launch.prompt: str | None = None` and `models.Resume.prompt: str |
  None = None`, passed to `start_session`; a refusal is 400 with the core's text as any
  `LadoError`. `make web-types` regenerates `web/openapi.json` and `web/src/api.gen.ts`.
- **D7. The window's row.** In `Launch.tsx`, a `<details className="launch-advanced
  launch-first">` before Advanced, in both modes and both sources, `open` false each time
  the window opens. Its `<summary>`: `First message to the supervisor (optional)`, or with
  text `First message to the supervisor: ` and the text's first non-empty line, one line
  with an ellipsis (CSS `text-overflow`). Inside: a `<textarea aria-label="First message"
  rows=4>` (vertical resize; Enter is a new line, it never submits), its note, and while
  the text is longer than `limits.max_message` (the `GET /api/limits` the composer uses)
  the note `<n> characters, the limit is <limit>` (class `field-note bad`) and the start
  button off. The field is off while busy (cloning, starting). `prompt` is sent as the
  text when it has non-white-space, else left out. Two adjacent `launch-advanced` rows
  share one top border (CSS).
- **D8. Version.** 0.37.0 (minor): a CLI option and API fields; no schema migration, no
  MCP tool change. CHANGELOG gets `## 0.37.0 (unreleased)`.

## Risks / Trade-offs

- A human used to typing into the supervisor's terminal after `lado start` may expect
  the answer there; the supervisor answers in the chat (and its terminal shows the turn).
  This is the rule for every human message; AGENTS.md and the CLI's help say so.
- The fake agent of the integration tests reads LADO's bodies as commands on its first
  input; a first input from `human` must be recorded as read (`first_read`) like LADO's,
  which may need a small change in `fake_agent.py` (the test says which).
