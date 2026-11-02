Task: LAD-106

## Why

Symptom: Claude Code asks "trust this folder?" in every repository it does not trust yet
(a new folder, a fresh container, a repository cloned from the UI), before any hook runs,
and only in the agent's terminal. Its default answer, "No, exit", closes the agent on a
single Enter. No flag, permission mode (`bypassPermissions` too) or setting skips it. A
human who started a session from the UI on a phone had no terminal, and the session stood
until another agent typed the answer into its tmux window.

Cause: LADO only reads the trust (`_trusted` in `src/lado/providers/claude.py`) and shows
the agent in Needs you with what to answer (`ClaudeProvider.first_hook_blocker`); recording
it was left to the human, because of the design principle "Never touch the user's global
agent config". Claude Code keeps the trust in its global config:
`projects["<folder>"].hasTrustDialogAccepted` in `~/.claude.json` (or
`$CLAUDE_CONFIG_DIR/.claude.json`, or an older `<config home>/.config.json`). There is no
official non-interactive way; the common one (wtw, Vellum, AgentWorkforce cloud) is to
write that flag before the CLI starts.

Checked by hand with Claude Code 2.1.295 (this repository's container, a config of its
own, 2026-10-27):

- the entry of the repository's main root covers its linked worktrees: started in a
  worktree, Claude Code asked nothing;
- `hasTrustDialogHooksAccepted` is not needed: the repository's own SessionStart hook in
  `.claude/settings.json` ran with `hasTrustDialogAccepted` alone;
- a project entry written into the file by another process (temp file and rename) while
  Claude Code ran survived Claude Code's own rewrite of the file at its exit: it watches
  the file and re-reads it.

Options weighed (the human chose A, decision #1832, option 1, no setting):

- A (taken): LADO records the trust of the session's repository itself, before it starts a
  Claude agent, through one careful writer of Claude Code's config. Long-term cost: an
  explicit exception to "Never touch the user's global agent config", written down; one
  function to keep true to Claude Code's file format, pinned by the same hand checks as
  `_trusted` today and by the smoke test with the real CLI.
- B: answer the dialog by keys typed into the agent's window when its screen shows it
  (AgentWorkforce relay). Fragile, and against "Events, not screens".
- C: Trust/Exit buttons in the UI that type the answer: still screen-driven, and the human
  must still act each time. Left for later (Out of scope).

Held against the design principles: the exception is narrow (one key of one project entry,
only when it is missing) and is recorded in AGENTS.md; nothing above `providers/` learns
of Claude Code's file (the provider decides in `first_hook_blocker` and returns a neutral
`Blocker`); no silent drop: every write is told whoever starts the agent and written to
the session's loop.log, and a write that fails or is refused keeps the trust question as
the fallback, saying why. Codex has its own trust and its own task (LAD-152); OpenCode and
Kilo ask nothing.

## What Changes

- Before a Claude agent starts (session start, resume, a worker's spawn), when Claude Code
  does not trust the agent's folder, LADO sets `hasTrustDialogAccepted: true` in the
  `projects` entry of the repository's main root (its real path) in the config file
  `_trusted` reads, and changes nothing else. It writes only when that flag is not `true`
  already.
- One function in `src/lado/providers/claude.py` changes Claude Code's config safely, for
  this and later edits: it re-reads the file right before the write, applies one change,
  keeps every other key, writes nothing when the change changes nothing, writes to a
  temporary file beside it and replaces the old one in one step (same mode; a symlink's
  target, not the link), and leaves a file it cannot read or understand as it is.
- A missing config file is created holding only that entry (mode 600) (the human's choice
  at #1856: Claude Code takes such a file and adds the rest itself; its first-run screens
  are LAD-104's).
- The line `LADO recorded Claude Code's trust in <repo> in <config file>` is told whoever
  starts the agent (`lado start`'s stderr, `Started.warnings`, `spawn_worker`'s warnings)
  and written to the session's loop.log, once per repository (the human's choice at
  #1856); no notice in the UI.
- When LADO cannot record the trust, the agent waits in Needs you as today, and the reason
  says why: `Claude Code asks whether to trust <repo>: LADO could not record the trust
  (<why>); in its terminal choose "Yes, I trust this folder" (Enter alone answers "No,
  exit" and closes the agent)`. A config LADO cannot read stays a warning, as today, and is
  not touched.
- AGENTS.md's principle "Never touch the user's global agent config" names this one
  exception; docs/design/agents.md, docs/design/modules.md, docs/install.md (Docker, "Your
  first session" and "If something goes wrong in Docker"), docs/testing.md and
  CHANGELOG.md (`## 0.44.0 (unreleased)`, Added) say what LADO writes and that a trusted
  repository's own Claude Code hooks (`.claude/`) and MCP servers (`.mcp.json`) run without
  a question (the human's choice at #1856: choosing the folder is the consent).
- A feature: the minor version (0.44.0).

## Scope

- Claude Code's folder trust for the session's repository, for every Claude agent LADO
  starts.
- The shared writer of Claude Code's config.
- Tests: unit, an integration test with the fake agent, the smoke test with the real CLI.

## Out of scope

- Trust/Exit buttons in the UI: the human chose the write instead (#1832); the question in
  Needs you stays the fallback.
- Codex's folder trust: LAD-152.
- Claude Code's first-run screens (theme, login, the bypass mode's disclaimer): LAD-104 and
  BACKLOG.md's "Claude Code's first-run screens…".
- A setting to switch the write off: the human chose no setting (#1832).
- Keeping back repositories with their own `.claude/` settings or `.mcp.json`: the human
  chose to trust every repository a session is started in (#1856); the docs say so.
- `hasTrustDialogHooksAccepted` and the worktree's own path: not needed (checked by hand,
  above).
- A notice in the UI that LADO recorded the trust: the log and the starter's lines suffice
  (#1856).

## Decisions for the record

- D1. The write lives in `ClaudeProvider.first_hook_blocker`, which already decides what
  holds a Claude agent before its first hook and runs at start, resume and spawn; it
  records the trust and then returns no reason. `base.Blocker` gains `note` (what the
  provider did so that nothing holds the agent), told and logged as the other lines are.
  No new provider method: the runtime's call stays one, and nothing above `providers/`
  knows of Claude Code's file.
- D2. The writer `edit_config(env, change)` in `claude.py`: `change` gets the parsed config
  and returns whether it changed it. The file is the one `_trusted` reads (one function
  finds it for both). A JSON object is required at the top; anything else is a
  `ValueError` naming the file, and the file is not touched. Written as Claude Code writes
  it (JSON, indent 2), to `<name>.<random>.tmp` in the same folder, flushed and fsynced,
  then `os.replace`; the old file's mode is kept (a new file 600, since Claude Code keeps
  its login there); a symlinked config is written through to its target, so a dotfiles
  link stays a link.
- D3. LADO's own writes are serialised by an exclusive `flock` on
  `LADO_HOME/claude-config.lock`, so two agents started at once (the UI and the loop) do
  not lose each other's entry. Claude Code's own lock is an internal detail of its binary
  and is not used; its watcher re-reads the file (checked by hand).
- D4. The key is the real path of the repository's main root (`gitpaths.main_root`), as
  `_trusted` reads it; an existing entry keeps all its keys, `hasTrustDialogAccepted:
  false` (Claude Code's default for a folder it has seen) becomes `true`. A `projects`
  that is not an object, or an entry that is not an object, is left as it is: a reason
  with why (for an entry) or the warning (for `projects`, which `_trusted` already
  refuses).
- D5. `tests/conftest.py`'s `claude_config` becomes autouse, so no test can reach the
  user's own Claude Code config now that LADO writes there.
- D6. The smoke test's Claude config drops its pre-written trust, so CI proves on the real
  CLI that LADO's write lets it start without the question; the container tests keep
  theirs.

## Impact

- Code: `src/lado/providers/claude.py`, `src/lado/providers/base.py` (`Blocker.note`),
  `src/lado/runtime.py` (`_first_hook_blocker`, loop.log at start and resume).
- Tests: `tests/test_providers.py`, `tests/test_runtime.py`, `tests/test_docker.py`,
  `tests/conftest.py`, `tests/integration/` (fake provider and agent, a new test),
  `tests/smoke/conftest.py`, `tests/real_clis.py`, `tests/live/conftest.py`.
- Docs: AGENTS.md, docs/design/agents.md, docs/design/modules.md, docs/install.md,
  docs/testing.md, CHANGELOG.md.
- Specs: new `claude-folder-trust`; `container` (the guide's trust question).
