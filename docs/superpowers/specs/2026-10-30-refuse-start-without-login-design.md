# Refuse a start without a login (LAD-161)

Change: `openspec/changes/refuse-start-without-login/` (proposal with AC-1..AC-10, the
delta of `provider-logins`, `design.md` with the decisions D1-D8). This document is the
human's view: what a user gets, what was decided with the human, and how the human checks
it. Mockup: the run's artifact `mockup-start-without-login.html`.

## What a user gets

- **The New session window does not offer a CLI that cannot start.** With Claude Code not
  logged in, the Provider list shows `claude · not logged in`, greyed out. A folder whose
  last session ran Claude no longer preselects it: Provider says "choose…" and a red note
  says "Claude Code is not logged in: its agents cannot start. Log in first"; the link
  closes the window and opens Settings → Providers and environment. Start stays disabled
  until another CLI is chosen or Claude Code is logged in.
- **A project with its own login counts.** In the Project way the list is read with the
  chosen project's variables and secrets: a project holding `CLAUDE_CODE_OAUTH_TOKEN`
  offers Claude even when LADO itself has no Claude login.
- **`lado start` refuses with the reason** instead of starting a supervisor that waits:
  ```
  $ lado start ~/workspace/shop --provider claude
  lado: Claude Code is not logged in, so the session was not started: log in in LADO's UI
  (Settings → Providers and environment, `lado ui`), or set CLAUDE_CODE_OAUTH_TOKEN as
  LADO's secret or a project secret
  ```
  `lado start <git-url>` and `lado start --new` say it before they clone or make a folder.
- **A supervisor's `spawn_worker` is refused** for a worker whose CLI needs a login and has
  none: "Claude Code is not logged in, so the worker was not started: ask the human to log
  in in Settings → Providers and environment, or start the worker with another provider".
  Sessions mix CLIs: a Kilo session's Claude worker is refused, a Claude session's Kilo
  worker starts. A session started from another session's approved proposal is refused
  the same way.
- **A resume is never refused.** A stopped Claude session resumed without a login (by
  hand, at LADO's start, after an update) starts, and its supervisor waits in Needs you
  as LAD-157 made it; the Resume window warns in amber: "Claude Code is not logged in: the
  supervisor waits until you log in. Log in…".
- **Codex, OpenCode and Kilo** start without a login, as before. A login LADO cannot read
  refuses nothing: the agent starts with the warning it has today.

## Decided with the human

Questions #1961 and #1969 of run task/lad-161, all recommendations taken:

1. The window greys a CLI without its login, never preselects it, and shows "Log in first"
   (mockup states 1-2).
2. The Project way checks with the project's secrets (state 3).
3. A resume goes on, with the amber note in the Resume window (state 4).
4. The refusal texts of `lado start` and `spawn_worker` (state 5); the approved
   `start_session` refuses the same way.
5. A login that cannot be read refuses nothing.
6. Sessions mix CLIs: a session's start checks the supervisor's CLI, each worker its own.

Scale full, review breadth first; minor version (0.44.0, already unreleased).

## How the human checks it

- In a LADO without a Claude login: open New session on a folder whose last session was
  Claude; see the greyed option, the note, and the link to Settings.
- `lado start <repo> --provider claude`: the refusal, and `lado ls` shows no new session.
- Log in on Settings, open New session again: Claude is offered and preselected as before.
- Stop a Claude session, log out, resume it: it resumes and the supervisor waits in Needs
  you; log in, and it starts by itself.
- In a Kilo session, ask the supervisor for a Claude worker without a login: it reports the
  refusal.

## Engineering decisions (for the record)

- One check in the core (`logins.refusal`, raised by `runtime.check_login`) before anything
  is stored; the CLI, the server and the MCP tools pass the `LadoError` on as they do.
- The check reads `agents_env(project)`, the environment the agent starts from, so a later
  LAD-160 rule about the chosen login method is followed without a second rule.
- The launch-time wait of LAD-157 stays unchanged for a resume and for a login lost between
  the check and the launch; the status is read twice for a new Claude agent (≈0.1 s).
- `GET /api/providers` gains `login_missing` and `?project=`; the window decides from it.
- `lado doctor`'s warning says that new sessions and workers are refused.
