Task: LAD-19

## Why

A new session's supervisor starts with nothing to do: the human waits for it to come up,
then types what they want into the UI's chat or its terminal. Often the human knows the
first task before pressing Start ("take LAD-19 from the tracker and design it with me"),
and a resumed supervisor, which remembers nothing of its earlier work, needs one sentence
to be pointed at what is next.

The root cause is one: the core already queues a first message for a supervisor before it
starts (`runtime.start_session(first=FirstInput(...))`, used by supervisor-started
sessions, and LADO's own `session resumed` messages), but the human has no way to give
one: `lado start` has no option for it and the New session window says "No first
message".

## What Changes

- **Core**: `runtime.start_session` takes the human's first message, `prompt`. It is
  checked before anything changes (not empty, at most `runtime.MAX_MESSAGE` characters)
  and queued for the new supervisor as a message from `human`, after LADO's own messages
  of a resume, so the supervisor gets it with its first hook as any queued message. A new
  session and a resume take it alike.
- **CLI**: `lado start ... --prompt TEXT` or `--prompt-file FILE` (`-` reads stdin), for a
  folder, a git URL (read and checked before the clone) and a resume alike.
- **UI**: the New session window, in its New and Resume modes, has a folded row **First
  message to the supervisor (optional)** above Advanced; opened, a text field (mockup
  `mockup-first-message.html` v2, variant C). Folded with text in it, the row shows the
  text's first line.
- **API**: `prompt` in `POST /api/sessions` (`Launch`) and
  `POST /api/sessions/{name}/resume` (`Resume`).
- New minor release (0.37.0): a CLI option and API fields. No schema migration, no MCP
  tool change.

## Scope

- The core's `prompt` of `start_session` and its check.
- `lado start --prompt` / `--prompt-file`, also with a git URL and on a resume.
- The New session window's First message row, New and Resume modes, Folder and Clone from
  URL alike; `Launch.prompt`, `Resume.prompt`.
- Docs: `docs/design/ui.md` (Launch and session control), AGENTS.md (How agents talk: a
  supervisor's first input; Try it locally: `lado start`), README's start (one line),
  CHANGELOG.md.

## Out of scope

- Files attached to the first message: an upload needs the session's artifact scope,
  which exists only once the session does; the human attaches files in the chat right
  after the start (the human's decision, point 6).
- A new session started from an existing one with a first message: already there, as
  supervisor-started sessions (the supervisor's `ask_human` with the brief and
  `Start session <name>`; the new supervisor gets the brief and the human's comment as
  its first message). The human's decision, point 7.
- Projects (ROADMAP, Later): the window's Projects source does not exist yet; when it
  does, it sends the same `prompt` with its `where`.
- A first message to a worker or to an agent other than the supervisor: a session starts
  with its supervisor only.
- Remembering earlier first messages or templates of them: nothing asks for it ("Only
  what is used").

## Acceptance criteria

- AC-1: `lado start <repo> --prompt "Take LAD-19"` starts the session, and its supervisor
  gets, with its first hook, one message from `human` whose text is `Take LAD-19`; the
  Activity chat shows it as the human's message.
- AC-2: `lado start <repo> --prompt-file brief.md` and `... --prompt-file -` (text on
  stdin) do the same with the file's or stdin's text, multi-line text kept whole.
- AC-3: `lado start` on a stopped session with `--prompt` resumes it, and the supervisor
  gets LADO's `session resumed: …` message first and the human's message after it.
- AC-4: An empty text, a text over 8000 characters, an unreadable file, or both options
  at once are refused before anything starts or is cloned: no session, no clone, no
  message.
- AC-5: `lado start <git-url> --prompt-file -` reads stdin and checks the text before the
  clone starts.
- AC-6: In the New session window the row "First message to the supervisor (optional)" is
  folded each time the window opens; opened, its text field takes the message; folded
  with text, the row shows the text's first line; an empty field sends no message.
- AC-7: A text over the limit in the window shows how long it is against the limit, and
  Start (Clone and start, Resume) stays off.
- AC-8: The Resume window has the same row, and its message reaches the resumed
  supervisor after LADO's `session resumed` message.
- AC-9: The human's text never appears on an agent CLI's command line: with Kilo and
  OpenCode, whose queue's lines at launch go on `--prompt`, the line carries a fixed
  summary, not the text.
