# uninstall Specification

## Purpose
How LADO is removed from a machine: `lado uninstall` stops everything of its `LADO_HOME`,
removes in each session's repository only the work `lado finish` would remove, deletes
`LADO_HOME`, and for the default home removes the program last, saying each step; with
`--keep-data` a LADO installed again resumes the sessions.

## Requirements

### Requirement: The plan comes before any change

`lado uninstall` SHALL print its plan before it changes anything: the UI server and the
sessions of this `LADO_HOME` it stops (by name, with the tmux socket it sees), each
repository with the worktrees and branches it removes and those it keeps, the `LADO_HOME`
folder it deletes with its size, the program and the command that removes it (or why it
keeps it), and one line naming what it leaves by design (the agent CLIs' own records,
see `docs/install.md`).

#### Scenario: Dry run
- **WHEN** the human runs `lado uninstall --dry-run` with a session running
- **THEN** the plan names the session, its repository and `~/.lado`, the exit code is 0,
  and the session, its worktrees, `~/.lado` and the program are as before

### Requirement: lado uninstall asks before it changes anything

After its plan `lado uninstall` SHALL ask `Uninstall? [y/N]`; only `y` or `yes` goes on.
`--yes` SHALL skip the question; without a terminal on stdin and without `--yes` it SHALL
refuse with exit 1. `--dry-run` SHALL print the plan and exit 0 without asking or changing
anything.

#### Scenario: Not confirmed
- **WHEN** the human answers `n`, or presses Enter, at `Uninstall? [y/N]`
- **THEN** it prints `Not uninstalled.`, exits 1 and nothing changed

#### Scenario: No terminal
- **WHEN** `lado uninstall` runs from a script without `--yes`
- **THEN** it exits 1 with `lado: not uninstalled: confirm with --yes` and nothing changed

### Requirement: Refusals leave everything as it was

`lado uninstall` SHALL refuse, with nothing changed and exit 1: inside an agent
(`LADO_AGENT` set); while `lado update` runs (its lock is held); and when `lado.db` has a
newer schema than this LADO's, naming the newer LADO's `lado uninstall` and the steps by
hand in `docs/install.md`. While it runs it SHALL hold the update's lock, so an update
started meanwhile is refused. A `lado.db` of an older schema SHALL be migrated as
`lado stop --all` migrates it.

#### Scenario: Inside an agent
- **WHEN** an agent runs `lado uninstall --yes`
- **THEN** it is refused as `lado uninstall is for the human`, and nothing changed

#### Scenario: An update runs
- **WHEN** `lado update` holds its lock and the human runs `lado uninstall --yes`
- **THEN** it is refused naming the running update, and nothing changed

#### Scenario: A newer database
- **WHEN** `lado.db` has a schema version above this LADO's
- **THEN** it is refused before the plan, and nothing changed

### Requirement: Everything of this LADO_HOME stops

After confirmation `lado uninstall` SHALL stop the UI server of this `LADO_HOME`, stop
every session not stopped yet as `lado stop --all` does, wait for each session's loop to
end, and close this `LADO_HOME`'s terminal viewers. A loop that does not end SHALL stop the uninstall
before any repository or file is touched, saying so, with exit 1.

#### Scenario: A running session and the UI server
- **WHEN** a session with a supervisor and a worker runs, the UI server runs, and the
  human confirms the uninstall
- **THEN** no agent process, session loop or UI server of this `LADO_HOME` is left, and
  LADO's tmux server has ended

### Requirement: The uninstall ends LADO's tmux server only when no session is left

When no tmux session is left on LADO's
socket, `lado uninstall` SHALL end that tmux server; when sessions of another `LADO_HOME` remain there,
it SHALL keep the server and name them.

#### Scenario: Another LADO_HOME on the same socket
- **WHEN** a session of another `LADO_HOME` runs on the same tmux socket
- **THEN** that session runs on, the tmux server is kept, and the output names the
  session it left

### Requirement: Repositories keep every line of work

For each repository of the sessions in `lado.db` (running and stopped), `lado uninstall`
SHALL remove each worktree under `.lado/worktrees/<session>/` and each branch
`lado/<session>/<name>` of those sessions by `lado finish`'s rule: merged into the
repository's current branch and with nothing uncommitted, it is removed (the worktree,
then the branch); otherwise both SHALL be kept and listed with the git commands that
remove them.

#### Scenario: Merged and unmerged workers
- **WHEN** a repository has a merged clean worker `dev` and an unmerged worker `rev`
- **THEN** `dev`'s worktree and branch are gone, `rev`'s stay, and the output lists `rev`'s
  worktree and branch with `git worktree remove --force <path>` and `git branch -D <branch>`

### Requirement: The uninstall touches nothing else of a repository

When `.lado/worktrees` holds nothing after the worktrees' removal, `lado uninstall` SHALL remove that folder
and the `/.lado/worktrees/` line of `.git/info/exclude`; it SHALL never remove or change
any other file under `.lado/`. A repository that is gone or that git cannot read SHALL be
named and passed over.

#### Scenario: The project's own files stay
- **WHEN** the repository has `.lado/sdlc.md` and every worktree was removed
- **THEN** `.lado/sdlc.md` is there unchanged, `.lado/worktrees` and the exclude line are
  gone

#### Scenario: A kept worktree keeps the exclude line
- **WHEN** one worktree of the repository is kept
- **THEN** `.lado/worktrees` and the `/.lado/worktrees/` line of `.git/info/exclude` stay

#### Scenario: A repository that is gone
- **WHEN** a session's repository folder was deleted
- **THEN** the output names it as passed over and the uninstall goes on

### Requirement: LADO_HOME is deleted whole and only it

`lado uninstall` SHALL delete the `LADO_HOME` folder with everything in it after the
repositories. It SHALL delete it only when it is the default `~/.lado` or holds `lado.db`,
and never when it is `/`, the user's home folder or a folder above it; such a folder SHALL
be named as kept, with exit 1. A file it cannot delete SHALL be named, with exit 1.

#### Scenario: The default home
- **WHEN** the uninstall of the default home is confirmed
- **THEN** `~/.lado` does not exist afterwards

#### Scenario: LADO_HOME is the home folder
- **WHEN** `LADO_HOME` is the user's home folder
- **THEN** nothing in it is deleted, and the output says why

### Requirement: The program goes last, only with the default home

When `LADO_HOME` is the default `~/.lado`, `lado uninstall` SHALL, as its last step,
remove the program with the tool that installed it: `uv tool uninstall lado` for a uv tool
install (a `uv-receipt.toml` in its prefix), `pipx uninstall lado<suffix>` for a pipx one
(`pipx_metadata.json`), whatever source either installed from. Nothing
SHALL be imported after the remover started. A remover that fails SHALL be named with its
exit code and the command to run by hand, with exit 1.

#### Scenario: A uv tool install
- **WHEN** LADO was installed with `uv tool install lado` and the uninstall of `~/.lado` is
  confirmed
- **THEN** `uv tool uninstall lado` runs last, and `lado` is no longer on the PATH

### Requirement: Otherwise the uninstall keeps the program and says how to remove it

Installed otherwise than with uv tool or pipx (pip in
an environment, a working copy run with `uv run`), `lado uninstall` SHALL keep the program and print
where it runs from and how to remove it. With another `LADO_HOME` it SHALL keep the
program and print the command that removes it, since `~/.lado` may still use it.

#### Scenario: Another LADO_HOME
- **WHEN** `LADO_HOME=/tmp/try lado uninstall --yes` runs
- **THEN** `/tmp/try` is deleted, `~/.lado` is untouched, the program stays and the output
  prints `uv tool uninstall lado` as the command to remove it

#### Scenario: A working copy
- **WHEN** `uv run lado uninstall --yes` runs in a working copy
- **THEN** the program is kept and the output says it runs from that environment

### Requirement: Keep data

With `--keep-data`, `lado uninstall` SHALL stop everything as without it and remove the
program by the same rule, but SHALL keep `LADO_HOME` and every repository as they are. The
sessions it stopped SHALL be resumable with `lado start` by a LADO installed again.

#### Scenario: Reinstall and resume
- **WHEN** the human runs `lado uninstall --keep-data --yes`, installs LADO again and runs
  `lado start <repo> --name <session>`
- **THEN** the session resumes with its runs and history, and its worktrees are where they
  were

### Requirement: The outcome is said step by step

`lado uninstall` SHALL print each step as it is done, and at the end what it left and why
(kept worktrees and branches, a kept program or folder). It SHALL exit 0 when each step of
the plan was done and 1 when one failed or was refused; a step that fails SHALL not keep
the next steps from running, except that no repository or file is touched after a session
could not be stopped.

#### Scenario: A clean machine
- **WHEN** the uninstall of the default home, installed with uv tool, ends with exit 0
- **THEN** `uv tool install lado==<version>` and `lado doctor` behave as on a machine LADO
  was never installed on: no session, no installed kit, no marketplace but the official one
