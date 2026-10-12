# First message at a session's start: implementation plan

**Goal:** the human gives a session's supervisor its first message when the session starts
or is resumed: `lado start --prompt` / `--prompt-file` and the New session window's
folded First message row (LAD-19).

**Architecture:** `runtime.start_session` gets `prompt`, checked by `runtime.check_prompt`
and queued as a message from `human` (fixed summary `runtime.FIRST_MESSAGE`, the text as
its body) after LADO's own before-start messages; `cli.cmd_start` and the server's start
and resume pass it; `web/src/Launch.tsx` gets the row.

**Tech stack:** Python 3.10+ (argparse, FastAPI, pydantic), React + TypeScript (vitest),
pytest (unit, integration with the fake agent, UI with Playwright).

**Spec:** `openspec/changes/first-message/` (proposal, delta `session-first-message`,
`design.md` D1–D8). **Design doc:** `docs/superpowers/specs/2026-10-12-first-message-design.md`.
**Mockup:** run artifact `task/lad-19/mockup-first-message.html` (v2, variant C).

Each task: tests first, then the code, then the named test run, then a commit (message in
the repository's style, `(LAD-19)` at the end).

## Global constraints

- Limit: `runtime.MAX_MESSAGE` (8000 characters), the UI's `Limits.max_message`; no new
  constant for it.
- Summary: `FIRST_MESSAGE = "the human's first message"`; the body is always the whole
  stripped text.
- Texts: `the first message is empty`; `the first message is <n> characters, the limit is
  <limit>`; `lado: cannot read the first message from <FILE>: <reason>`; `first message:
  queued for the supervisor`; the row `First message to the supervisor (optional)` /
  `First message to the supervisor: <first line>`; the note `sent to the supervisor as
  your message once it starts; its answer comes in the chat`; over the limit `<n>
  characters, the limit is <limit>`.
- No schema change, no MCP tool change; version 0.37.0 (CHANGELOG `## 0.37.0
  (unreleased)`).
- `make web-types` after the API models change; commit `web/openapi.json` and
  `web/src/api.gen.ts`.

## Review focus

1. A multi-line text whose first line is short: it must still be the body, never the
   summary (Kilo/OpenCode argv) — Task 1's argv test.
2. `lado start <git-url> --prompt-file -`: stdin read once, before the clone, and not read
   again by the second `cmd_start` after it — Task 2's clone test.
3. A resume whose start fails after the session was taken: the human's message is dropped
   with the queue, not left pending for a later resume — Task 1's failed-start test.
4. Text with only white space in the window: no `prompt` sent (not an empty string, which
   the core refuses) — Task 4's empty test.
5. Folding the row while the text is over the limit: Start stays off, and the row shows
   the first line — Task 4's limit test.

---

### Task 1: The core's first message (D1–D4)

**Files:** modify `src/lado/runtime.py` (near `FIRST_INPUT`, `start_session`); test
`tests/test_runtime.py`, `tests/test_codex.py`.

**Produces:** `runtime.FIRST_MESSAGE: str`; `runtime.check_prompt(text: str) -> str`
(stripped; raises `LadoError`); `runtime.start_session(..., prompt: str | None = None)`.

- [ ] Step 1: tests in `tests/test_runtime.py` (fixtures `repo`, `fake_tmux`):
  - `test_a_new_session_starts_with_the_humans_first_message`:
    `runtime.start_session(str(repo), "s", None, provider="claude", prompt="  Take LAD-19\nAsk me first \n")`;
    `[m] = state.list_messages("s")`; `(m.sender, m.recipient, m.summary, m.body) ==
    ("human", "supervisor", runtime.FIRST_MESSAGE, "Take LAD-19\nAsk me first")`.
  - `test_a_one_line_first_message_is_a_body_too`: `prompt="Go"` gives `m.body == "Go"`
    and `m.summary == runtime.FIRST_MESSAGE`.
  - `test_a_resumed_session_gets_the_humans_message_after_lados`: start, `runs.start` a
    run (as `test_server_launch.py`'s resume test does with a kit), `stop_session`, resume
    with `prompt="Continue"`; the supervisor's messages after the stop are, in order,
    `session resumed: 1 open run` from `lado` (and a step message if the run's state is
    the lead's), then the human's.
  - `test_an_empty_first_message_is_refused_before_anything` (`"  \n "`) and
    `test_a_first_message_over_the_limit_is_refused` (`"x" * (runtime.MAX_MESSAGE + 1)`):
    `LadoError` with the spec's text; `state.get_session("s") is None`; `fake_tmux == []`.
  - `test_a_failed_start_drops_the_humans_message`: make the launch fail as
    `test_a_start_whose_environment_fails_launches_nothing` does but after the session is
    taken (patch `tmux.new_session` to raise); for a resume, no `pending` message from
    `human` is left (`state.list_messages`), as LADO's own are not.
  - `test_without_a_prompt_nothing_new_is_queued`: no message from `human`.
  - `test_an_opencode_family_supervisor_gets_the_fixed_line_not_the_text` (parametrize
    `kilo`, `opencode`): `prompt="Take LAD-19\nsecret plan"`; argv's `--prompt` value is
    `f"[from human] {runtime.FIRST_MESSAGE} (#{m.id}, 2 lines: call read_messages)"` and
    no argv item holds `LAD-19` or `secret`.
  - With the `first_input` fixture: `test_an_agent_that_starts_at_its_first_input_takes_the_humans_message`:
    `prompt="Go"`; no message with summary `runtime.FIRST_INPUT`; argv
    `["firstinput", f"[from human] {runtime.FIRST_MESSAGE} (#{m.id}, 1 line: call read_messages)"]`.
  - In `tests/test_codex.py`: `test_a_codex_supervisor_with_a_first_message_gets_no_first_input`
    (as `test_a_codex_supervisor_starts_with_lado_s_line`, with `prompt="Go"`): one
    message, from `human`; `argv[-1]` starts with `[from human] the human's first message`.
- [ ] Step 2: `uv run pytest tests/test_runtime.py tests/test_codex.py -n auto -k "first_message or first_input or humans"`: they fail.
- [ ] Step 3: code:

  ```python
  FIRST_MESSAGE = "the human's first message"


  def check_prompt(text: str) -> str:
      """The human's first message for a session's supervisor, stripped; refused when empty
      or over MAX_MESSAGE, before anything starts."""
      text = text.strip()
      if not text:
          raise LadoError("the first message is empty")
      if len(text) > MAX_MESSAGE:
          raise LadoError(f"the first message is {len(text)} characters, the limit is {MAX_MESSAGE}")
      return text
  ```

  In `start_session`: a parameter `prompt: str | None = None` (docstring: "the human's
  first message, for a new session and a resume alike"); `text = check_prompt(prompt) if
  prompt is not None else None` right after the `first` check; in the `try`, after the
  `first` block: `if text is not None: state.queue_message(session, state.HUMAN,
  SUPERVISOR, FIRST_MESSAGE, text, before_start=True)`.
- [ ] Step 4: the same run passes; `uv run pytest tests/test_runtime.py tests/test_codex.py tests/test_runtime_start_approved.py -n auto`.
- [ ] Step 5: commit `runtime.py`, the two test files: "A session's supervisor can start with the human's first message (LAD-19)".

### Task 2: `lado start --prompt` / `--prompt-file` (D5)

**Files:** modify `src/lado/cli.py` (`cmd_start`, `_start_clone`, the `start` parser);
test `tests/test_cli.py`.

**Consumes:** `runtime.check_prompt`, `start_session(prompt=...)`.

- [ ] Step 1: tests in `tests/test_cli.py` (fixtures `repo`, `fake_tmux`, `capsys`,
  `monkeypatch`, `tmp_path`):
  - `test_start_with_a_prompt_queues_it_and_says_so`: `main(["start", str(repo), "--name",
    "s", "--provider", "claude", "--no-attach", "--prompt", "Take LAD-19"]) == 0`;
    `first message: queued for the supervisor` in stdout after the `Started session` line;
    the human's message's body is `Take LAD-19`.
  - `test_start_reads_the_prompt_from_a_file_and_from_stdin`: a file `brief.md` with two
    lines; and `monkeypatch.setattr("sys.stdin", io.StringIO("Line one\nLine two\n"))`
    with `--prompt-file -` (another session name): bodies `Line one\nLine two`.
  - `test_start_refuses_both_prompt_options`: `pytest.raises(SystemExit)` with code 2, `not
    allowed with` in stderr, `state.get_session("s") is None`.
  - `test_start_refuses_a_prompt_file_it_cannot_read`: exit 1, stderr starts with `lado:
    cannot read the first message from {missing}:`, no session.
  - `test_start_refuses_an_empty_prompt`: `--prompt ""` exit 1, `the first message is
    empty`, no session.
  - `test_a_git_url_with_a_bad_prompt_clones_nothing`: `monkeypatch.setattr(clone,
    "clone", fail)` where `fail` raises `AssertionError`; `main(["start",
    "file:///nowhere/app.git", str(tmp_path / "app"), "--prompt", ""])` is 1 and the folder
    is not made.
  - `test_a_git_url_reads_stdin_once`: a fake `clone.clone` that makes a repo with a commit
    at the folder (as LAD-6's CLI tests do), stdin `Go\n` with `--prompt-file -`; the
    human's message body is `Go` (a second read would give `""` and refuse).
  - `test_a_resume_with_a_prompt`: start, `main(["stop", "s"])`, start again with
    `--prompt Continue`: `Resumed session` then `first message: queued for the supervisor`;
    the last message is the human's.
  - `test_start_help_names_the_prompt_options`: `--prompt` and `--prompt-file` in
    `start --help`.
- [ ] Step 2: `uv run pytest tests/test_cli.py -n auto -k prompt`: they fail.
- [ ] Step 3: code. Parser:

  ```python
  first = start.add_mutually_exclusive_group()
  first.add_argument(
      "--prompt", metavar="TEXT",
      help="a first message to the supervisor, from you; it answers in the UI's chat",
  )
  first.add_argument(
      "--prompt-file", metavar="FILE",
      help="the first message from a file; - reads it from stdin",
  )
  ```

  In `cmd_start`, first thing (before `clone.is_url`): `if not hasattr(args,
  "prompt_text"): args.prompt_text = _read_prompt(args)`, where `_read_prompt` returns
  None without either option, the checked text otherwise:

  ```python
  def _read_prompt(args: argparse.Namespace) -> str | None:
      """The first message of `--prompt` or `--prompt-file` (`-`: stdin), checked."""
      if args.prompt is not None:
          return runtime.check_prompt(args.prompt)
      if args.prompt_file is None:
          return None
      try:
          if args.prompt_file == "-":
              text = sys.stdin.read()
          else:
              text = Path(args.prompt_file).read_text(encoding="utf-8")
      except (OSError, UnicodeDecodeError) as error:
          raise runtime.LadoError(
              f"cannot read the first message from {args.prompt_file}: {error}"
          ) from error
      return runtime.check_prompt(text)
  ```

  (The CLI's main prints a `LadoError` as `lado: <text>` with exit 1; check that path.)
  Pass `prompt=args.prompt_text` to `start_session`; after the Started/Resumed line, `if
  args.prompt_text is not None: print("first message: queued for the supervisor")`.
  `_start_clone` calls `cmd_start(args)` again with `args.prompt_text` already set, so
  stdin is not read twice.
- [ ] Step 4: `uv run pytest tests/test_cli.py -n auto`: passes.
- [ ] Step 5: commit: "lado start takes a first message for the supervisor (LAD-19)".

### Task 3: The API's `prompt` (D6)

**Files:** modify `src/lado/server/models.py` (`Launch`, `Resume`), `src/lado/server/app.py`
(`start`, `resume`); regenerate `web/openapi.json`, `web/src/api.gen.ts`; test
`tests/test_server_launch.py`.

- [ ] Step 1: tests (fixtures `client`, `repo`, `fake_tmux`; the file's `launch` helper):
  - `test_a_start_with_a_prompt_queues_the_humans_first_message`: `launch(client, repo,
    prompt="Take LAD-19")` is 200; the human's message's body is `Take LAD-19`.
  - `test_a_resume_with_a_prompt`: start, stop, `client.post("/api/sessions/s/resume",
    json={"prompt": "Continue"})` is 200; the last message is the human's.
  - `test_an_empty_prompt_is_400`: `prompt="  "` → 400 with detail `the first message is
    empty`, no session.
- [ ] Step 2: run, they fail.
- [ ] Step 3: `prompt: str | None = None` in `Launch` and `Resume` with a comment "the
  human's first message to the supervisor (runtime.check_prompt)"; `prompt=given.prompt`
  in both `start_session` calls. `make web-types`.
- [ ] Step 4: `uv run pytest tests/test_server_launch.py -n auto` and `make web` (the
  stale-types check) pass.
- [ ] Step 5: commit with `web/openapi.json` and `web/src/api.gen.ts`: "The API's start and
  resume take the human's first message (LAD-19)".

### Task 4: The window's First message row (D7)

**Files:** modify `web/src/Launch.tsx`, `web/src/styles.css`; test `web/src/Launch.test.tsx`.

**Consumes:** `Launch.prompt`, `Resume.prompt` in `api.gen.ts`; `getLimits` (the
composer's `GET /api/limits` call in `api.ts`).

- [ ] Step 1: vitest tests in the file's style (the mocked `fetch` it uses):
  - "the first message row is folded when the window opens": the summary text `First
    message to the supervisor (optional)` is shown, no textbox named `First message`.
  - "a first message is sent with the start": open the row (click its summary), type
    `Take LAD-19`, press Start session; the `POST /api/sessions` body has `prompt: "Take
    LAD-19"`.
  - "an empty first message is not sent": type `   `; the body has no `prompt` key.
  - "folded with text the row shows its first line": type `Line one{Enter}Line two`, click
    the summary; it reads `First message to the supervisor: Line one`.
  - "a first message over the limit keeps Start off": limits `max_message: 20`, 21
    characters: the note `21 characters, the limit is 20`, Start session disabled; also
    after folding.
  - "the Resume window sends its first message": in Resume mode, the
    `/api/sessions/<name>/resume` body has `prompt`.
  - "Clone and start carries the first message": the `POST /api/sessions` after the clone
    job has `prompt`.
- [ ] Step 2: `cd web && npx vitest run src/Launch.test.tsx`: they fail.
- [ ] Step 3: code: state `prompt` (string) and `limits` (the composer's loader); a
  component `FirstMessage({text, onText, limit, disabled})` rendering

  ```tsx
  <details className="launch-advanced launch-first">
    <summary>{first ? <>First message to the supervisor: <span className="launch-first-peek">{first}</span></> : "First message to the supervisor (optional)"}</summary>
    <div className="field">
      <textarea aria-label="First message" rows={4} value={text} disabled={disabled}
        placeholder="What the supervisor should do first" onChange={(e) => onText(e.target.value)} />
      {over ? <span className="field-note bad">{text.length} characters, the limit is {limit}</span>
            : <span className="field-note">sent to the supervisor as your message once it starts; its answer comes in the chat</span>}
    </div>
  </details>
  ```

  placed before the Advanced `<details>`; `first` is the first non-empty line, trimmed;
  `over` counts the trimmed text against `limits.max_message`. The start, resume and
  after-clone requests add `prompt: prompt.trim()` only when it is non-empty; `ready`,
  `cloneReady` and the Resume button are off while `over`. CSS: `.launch-first textarea`
  as the mockup's (`width: 100%`, padding 8px 10px, the field's border and radius,
  `resize: vertical`, focus ring as `.composer-box:focus-within`), `.launch-first .field {
  margin-top: 10px }`, the summary one line with `overflow: hidden; text-overflow:
  ellipsis; white-space: nowrap`, and `.launch-advanced + .launch-advanced { border-top:
  0; padding-top: 0 }`.
- [ ] Step 4: `make web` passes (tsc, vitest, build).
- [ ] Step 5: commit: "The New session window takes a first message for the supervisor (LAD-19)".

### Task 5: End to end: integration and UI

**Files:** test `tests/integration/test_session_start.py`, `tests/ui/test_launch.py`;
maybe `tests/integration/fake_agent.py`.

- [ ] Step 1: integration tests (`-m integration`, the fake agent):
  - `test_a_session_starts_with_the_humans_first_message`: `runtime.start_session(str(repo),
    "s", None, "fake", prompt="Take LAD-19\nAsk first")`; wait until the human's message is
    `delivered` (`state.list_messages`), and the fake agent's first input
    (`fake_logs(...)/inputs.jsonl`) holds `[from human] the human's first message`. If the
    test needs the fake agent to read it, extend `lado_bodies` to call `read_messages` for a
    first line from `human` too (reported as `first_read`, bodies of `human` not run as
    commands), and assert the read body.
  - `test_a_resumed_session_gets_the_humans_message_after_lados`: start, stop, resume with
    `prompt="Continue"`; the supervisor's first input has the `[from lado] session resumed`
    line before the `[from human]` line, and both are delivered.
- [ ] Step 2: UI e2e (`-m ui`, `shot`): `test_a_session_starts_with_a_first_message`: open
  New session, folder `repo`, open the First message row, type two lines, shot of the
  window, Start session; the Activity chat shows the text as the human's message (shot).
- [ ] Step 3: `uv run pytest -m integration -n auto tests/integration/test_session_start.py`
  and `uv run pytest -m ui tests/ui/test_launch.py` pass; attach the two screenshots as run
  artifacts.
- [ ] Step 4: commit: "End-to-end tests of the first message (LAD-19)".

### Task 6: Docs

**Files:** `docs/design/ui.md`, `AGENTS.md`, `README.md`, `CHANGELOG.md`.

- [ ] Step 1: `docs/design/ui.md`, Launch and session control: replace "No first message,
  no tmux attach." with "No tmux attach." and add a bullet **First message** (decided
  2026-10-12, LAD-19; mockup `task/lad-19/mockup-first-message.html` v2, variant C): the
  row, folded each time, its peek, its note, the limit, sent as `prompt` of start, resume
  and the start after a clone; the message is the human's, after LADO's on a resume.
- [ ] Step 2: AGENTS.md: How agents talk, the paragraph on an agent's first input: a
  supervisor's queue may also hold the human's first message (`start_session(prompt=)`,
  from `human`, summary `runtime.FIRST_MESSAGE`, the text only as its body, so never on
  argv; after LADO's messages); Try it locally: `lado start ... --prompt TEXT |
  --prompt-file FILE|-`; Layout, `runtime.py`: `check_prompt`.
- [ ] Step 3: README's start: one line on `--prompt`.
- [ ] Step 4: CHANGELOG.md: `## 0.37.0 (unreleased)` on top with "`lado start --prompt
  TEXT` / `--prompt-file FILE` and the New session window's First message row give the
  supervisor a first message from you, also on a resume." and "API: `prompt` in `POST
  /api/sessions` and `POST /api/sessions/{name}/resume`."
- [ ] Step 5: `make lint`, `openspec validate first-message --strict`; commit: "Docs of
  the first message (LAD-19)".

## Regression run

`make lint`; `make test`; `uv run pytest -m integration -n auto
tests/integration/test_session_start.py`; `uv run pytest -m ui tests/ui/test_launch.py`;
`make web`; `openspec validate --specs --strict`. CI runs `make check` and the smoke.
