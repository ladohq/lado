## 1. Core

- [x] 1.1 `runtime.FIRST_MESSAGE`, `runtime.check_prompt`, `start_session(prompt=...)`
  queued from `human` after LADO's before-start messages (D1–D4). Unit tests
  (`tests/test_runtime.py`): "A new session with a first message", a one-line text is a
  body too, "A resumed session with a first message" (order after `session resumed`),
  "An empty first message", "A first message over the limit" (nothing stored, no tmux
  call), "A start that fails" (no pending human message left), "No first message",
  "Kilo or OpenCode launched with a first message" (argv has the fixed line, not the
  text), a first-input CLI takes the human's line and no `FIRST_INPUT`; in
  `tests/test_codex.py` "Codex with a first message".

## 2. CLI

- [x] 2.1 `lado start --prompt TEXT | --prompt-file FILE|-`, read and checked before a
  clone and the start, `first message: queued for the supervisor` (D5). Unit tests
  (`tests/test_cli.py`): "Text on the command line", "Text from stdin" and a file, "Both
  options" (exit 2), "A file that cannot be read" (exit 1), an empty `--prompt`, "A git
  URL with a bad first message" (no clone), stdin read once across the clone, "A resume
  with a first message", the help names both options.

## 3. API

- [ ] 3.1 `Launch.prompt`, `Resume.prompt` passed to `start_session` (D6); `make
  web-types`, both generated files committed. Unit tests (`tests/test_server_launch.py`):
  start and resume with `prompt`, an empty `prompt` is 400 with the core's text.

## 4. UI

- [ ] 4.1 The New session window's First message row, New and Resume, folder and clone
  (D7; mockup `task/lad-19/mockup-first-message.html` v2, variant C). vitest
  (`web/src/Launch.test.tsx`): "Folded by default", "A first message sent", an empty one
  not sent, "Folded with text", "Over the limit" (Start off, also folded), "Resume with a
  first message", "Clone and start with a first message". `make web` passes.

## 5. End to end

- [ ] 5.1 Integration (`tests/integration/test_session_start.py`, `-m integration`): a new
  session's supervisor gets `[from human] the human's first message` with its first input
  and the message is delivered; a resume's first input has LADO's `session resumed` line
  before the human's. Extend `fake_agent.lado_bodies` to read a first `[from human]` line
  only if the test needs the body.
- [ ] 5.2 UI e2e (`tests/ui/test_launch.py`, `-m ui`): a session started with a first
  message from the window; the Activity chat shows it as the human's. Screenshots of the
  window and the chat attached as run artifacts.

## 6. Docs and release notes

- [ ] 6.1 `docs/design/ui.md` (Launch and session control: the First message row; "No
  first message" removed), AGENTS.md (How agents talk: the human's first message in a
  supervisor's first input; Try it locally: `--prompt` / `--prompt-file`; Layout:
  `check_prompt`), README's start (one line), CHANGELOG.md `## 0.37.0 (unreleased)`.

## 7. Regression

- [ ] 7.1 `make lint`, `make test`, `uv run pytest -m integration -n auto
  tests/integration/test_session_start.py`, `uv run pytest -m ui tests/ui/test_launch.py`,
  `make web`, `openspec validate first-message --strict`, `openspec validate --specs
  --strict`; CI green.
