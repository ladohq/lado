# Uninstall: design

Task: LAD-35. Change: `openspec/changes/uninstall/` (proposal, delta `uninstall`,
`design.md` D1–D10).

## Problem

LADO leaves a program, processes, `~/.lado` and worktrees and branches in every
repository a session ran in, and only `lado.db` knows which repositories those are. The
human wants two things from an uninstall: a user who gives LADO up can remove it and
clean up after it; and a release test can reset a machine to a new user's state, install
an older LADO and check `lado update` to the new one.

Root cause: no command undoes what LADO made, though LADO knows all of it.

## What the user sees

```text
$ lado uninstall
LADO 0.37.0 will be uninstalled (tmux socket "lado", LADO_HOME ~/.lado):

Stop:
  the UI server (http://127.0.0.1:8765)
  session "app" (running: supervisor, developer)
  session "old" (stopped)
Repositories:
  ~/work/app
    remove worktree .lado/worktrees/app/developer and branch lado/app/developer (merged)
    keep   worktree .lado/worktrees/app/reviewer and branch lado/app/reviewer: not merged into main
  ~/work/gone: no longer there, passed over
Delete:
  ~/.lado (85 MB: history, artifacts, installed kits, backups, logs)
Remove the program:
  uv tool uninstall lado
Agent CLIs keep their own records of these folders (e.g. Claude Code's ~/.claude.json):
see docs/install.md, Uninstall.

Uninstall? [y/N] y
Stopped the UI server
Stopped session "app"
Ended LADO's tmux server
Removed worktree ~/work/app/.lado/worktrees/app/developer and branch lado/app/developer
Kept worktree ~/work/app/.lado/worktrees/app/reviewer: not merged into main
Deleted ~/.lado
Removing the program: uv tool uninstall lado
Uninstalled lado

Left on this machine:
  ~/work/app: worktree .lado/worktrees/app/reviewer, branch lado/app/reviewer
    git -C ~/work/app worktree remove --force .lado/worktrees/app/reviewer
    git -C ~/work/app branch -D lado/app/reviewer
```

- `--dry-run`: the plan only. `--yes`: no question (required without a terminal).
- `--keep-data`: stops everything and removes the program; `~/.lado` and the repositories
  stay, so LADO installed again resumes the sessions.
- `LADO_HOME=/tmp/try lado uninstall`: that folder and its sessions only; the program
  stays and its removal command is printed (the human's decision).
- Refused with nothing changed: inside an agent, during `lado update`, on a newer
  `lado.db`.

The release test the human runs:

```bash
lado uninstall --yes                   # a new user's machine, but the agent CLIs' records
uv tool install lado==0.35.0           # the release users have
lado start ~/work/app                  # use it as a user would
lado update                            # the upgrade under test
```

## Options

1. Docs only: the human finds the repositories in `lado.db` by hand. Kept as the fallback
   for a LADO before the command.
2. **`lado uninstall`, a core module behind a thin CLI** (chosen), shaped like `lado
   update`: plan, confirmation, steps said as they run, reusing the stops, finish's
   merged rule and the update's lock.
3. A `--purge` on `lado stop --all`: mixes a daily command with a destructive one and
   leaves the program to the human. Rejected.

## Held against the roadmap and the principles

Stage 7's desktop app uninstalls through the OS and can call the same core for the data.
Projects (Later) add repositories; the repository step goes by `lado.db`'s sessions, so
it follows. Neutral core: no provider involved; the docs name each CLI's own records. One
source of truth: repositories from `lado.db`, the merged rule shared with finish, the
installer read from the same files as `lado update`. No silent drops: what stays is
listed with the command that removes it. Never touch the user's agent config: the CLIs'
records stay. Only what is used: no UI button, no `--discard`.

## Testing

- Unit (`tests/test_uninstall.py`, real git in `tmp_path`, tmux recorded): the plan's
  content and that `--dry-run` changes nothing; refusals; the repository rule (merged,
  unmerged, dirty, branch without worktree, gone repository, the exclude line, `.lado/`
  files kept); the home guard; default-home detection; the remover for a uv receipt, a
  pipx metadata with a suffix, none; a failing remover; no import after the remover;
  `--keep-data`; exit codes. `tests/test_cli.py`: the confirmation, `--yes`, no terminal,
  `uninstall` runs without `migrate_if_safe`, an older `lado.db` migrated by the stop.
- Integration (`tests/integration/test_uninstall.py`, fake agent): a running session with
  a merged and an unmerged worker and a UI server; `lado uninstall --yes` with the test's
  `LADO_HOME` (not the default: the program is kept, so the test never removes LADO):
  no agent, loop, viewer or UI server process left, the test's tmux server gone, the
  merged work removed, the unmerged kept and listed, the home deleted, exit 0. A second
  test: `--keep-data`, then `lado start` resumes the session.
- No live or smoke test: no agent CLI behaves differently (Testing, the lowest layer).
- By hand at release: the release test above on a machine with a uv tool install.
