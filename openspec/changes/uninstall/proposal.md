Task: LAD-35

## Why

LADO has no way out. A user who gives LADO up must find by hand what it left behind: the
program, a tmux server with agents, the UI server, `~/.lado` (history, artifacts, kits'
git cache, backups, logs) and, in every repository a session ran in, worker worktrees
under `.lado/worktrees/`, branches `lado/<session>/<agent>` and a line in
`.git/info/exclude`. Which repositories those are is known only to `lado.db`: once the
user deletes `~/.lado`, nobody can tell where to clean.

The human has a second use for it: testing an upgrade as a user meets it. Uninstall to a
clean state (as a new user's machine), install an older release, then `lado update` to the
new one. That needs an uninstall that leaves nothing of LADO's own behind.

Root cause: LADO knows everything it made (sessions, their repositories, its home, how it
was installed) but offers no command that undoes it; only LADO can do it completely.

## What Changes

- **CLI**: `lado uninstall [--dry-run] [--keep-data] [--yes]`. It prints its plan, asks
  `Uninstall? [y/N]` (`--yes` skips it; without a terminal `--yes` is required), then:
  1. stops the UI server, every session of this `LADO_HOME` (as `lado stop --all`) with
     their loops, and the UI's terminal viewers; ends LADO's tmux server when no session
     is left on its socket;
  2. in each repository of the sessions in `lado.db`, removes the worktrees and branches
     `lado finish` would remove without asking (merged into the repository's current
     branch, nothing uncommitted), keeps every other one and lists it with the git
     commands that remove it; removes the `.git/info/exclude` line and the empty
     `.lado/worktrees` folder once no worktree is left there; the project's own files in
     `.lado/` (e.g. `sdlc.md`) are never touched;
  3. deletes the `LADO_HOME` folder;
  4. as its last step, when `LADO_HOME` is the default `~/.lado`, removes the program
     itself with the tool that installed it (`uv tool uninstall lado`, `pipx uninstall
     lado`); installed otherwise, or with another `LADO_HOME`, it keeps the program and
     prints the command that removes it.
- `--dry-run` prints the plan only. `--keep-data` stops everything and removes the
  program, but keeps `LADO_HOME` and the repositories as they are, so a reinstalled LADO
  resumes the sessions.
- Refused, with nothing changed: inside an agent, while `lado update` runs, and on a
  `lado.db` of a newer LADO.
- **Docs**: an Uninstall section in `docs/install.md` (what the command does, what it
  leaves: the agent CLIs' own records of the folders, clones in `~/lado`, kept worktrees;
  and the same by hand, for a LADO before this command or one installed with pip), a
  pointer in README.md, AGENTS.md (Layout, the CLI sections), CHANGELOG.md.
- Goes into the unreleased 0.37.0 (a new CLI command: minor). No schema migration, no MCP
  tool or API change.

## Scope

- The core module `lado.uninstall` (plan and run) and the command `lado uninstall`.
- Cleaning this `LADO_HOME`'s sessions' repositories by `lado finish`'s rule.
- The program's removal for a uv tool or pipx install, from any source.
- Docs as above.

## Out of scope

- A button in the web UI: the UI server would remove itself and the page it serves; the
  human's decision (uninstall is a terminal command).
- Discarding unmerged or uncommitted work (`--discard`): uninstall never loses a line of
  an agent's work; it lists what it keeps with the commands to remove it (the human's
  decision).
- The agent CLIs' own records (Claude Code's `~/.claude.json` projects and
  `~/.claude/projects/`, OpenCode's and Kilo's session data): "Never touch the user's
  global agent config"; the docs name them with their paths (the human's decision). So
  after a reinstall Claude Code does not ask again whether to trust a folder it trusted.
- Repositories cloned by `lado start <git-url>` into `~/lado/`: they are the user's
  repositories now (the human's decision); only LADO's worktrees and branches in them go.
- Other `LADO_HOME`s and other tmux sockets (`LADO_TMUX_SOCKET`): the command sees only
  its own, as `lado stop --all` and `lado update` do; the plan says which.
- tmux, uv, git and the agent CLIs: the user installed them for their own use too.
- A `lado.db` of a newer LADO: refused; the newer LADO's `lado uninstall`, or the steps by
  hand, remove it.

## Impact

- New: `src/lado/uninstall.py`, `tests/test_uninstall.py`,
  `tests/integration/test_uninstall.py`.
- Changed: `src/lado/cli.py` (the command; no migration before it), `src/lado/update.py`
  (the program's remover), `src/lado/runtime.py` (the merged-and-clean check shared with
  finish, the exclude line's removal), docs.
- Version: minor (0.37.0, already unreleased).
