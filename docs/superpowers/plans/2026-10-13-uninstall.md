# Uninstall: implementation plan

**Goal:** `lado uninstall [--dry-run] [--keep-data] [--yes]` stops everything of this
`LADO_HOME`, cleans its sessions' repositories by `lado finish`'s rule, deletes
`LADO_HOME` and, for the default home, removes the program (LAD-35).

**Architecture:** a new core module `src/lado/uninstall.py` (`plan`, `print_plan`, `run`);
`cli.cmd_uninstall` refuses, prints, asks and calls it. Reuses `runtime.stop_all`,
`server.run.stop`, `loop.wait_stopped`, `terminal.close_viewers`, `runtime.remove_work`,
the update's lock; new small helpers in `runtime.py` (`work_of`, `keeps_work`,
`include_worktrees`) and `update.py` (`remover`).

**Spec:** `openspec/changes/uninstall/` (proposal, delta `uninstall`, `design.md`
D1–D10). **Design doc:** `docs/superpowers/specs/2026-10-13-uninstall-design.md`.

Each task: tests first, then the code, then the named test run, then a commit (message
in the repository's style, `(LAD-35)` at the end).

## Task 1: finish's rule as one function (D4)

**Files:** `src/lado/runtime.py`, `tests/test_runtime.py` (or the file that tests
`finish_preview` today).

1. Tests: `work_of(repo, worktree, branch)` on real git: merged and clean (`keeps_work` is
   None), a commit not in the current branch, uncommitted changes, branch gone with
   commits in the worktree's HEAD, both gone (None). The existing finish tests stay
   green unchanged.
2. Code: factor `work_of` and `keeps_work` out of `_work_state` and `_refusal`; those two
   call them (the worker's name stays in finish's texts).
3. `uv run pytest tests/test_runtime.py -n auto`; commit.

## Task 2: the exclude line's counterpart (D5)

**Files:** `src/lado/runtime.py`, `tests/test_runtime.py`.

1. Tests: `include_worktrees(repo)` drops `/.lado/worktrees/` and keeps every other line
   of the common `info/exclude`, also from a linked worktree; no file is no error;
   `exclude_worktrees` then `include_worktrees` gives the file as before.
2. Code; run; commit.

## Task 3: the program's remover (D8)

**Files:** `src/lado/update.py`, `tests/test_update.py`.

1. Tests (`LADO_UPDATE_PREFIX` at a `tmp_path` prefix): a `uv-receipt.toml` of an index
   install and of a git install both give `["uv", "tool", "uninstall", "lado"]`; a
   `pipx_metadata.json` with `suffix: "@1"` gives `["pipx", "uninstall", "lado@1"]`;
   neither gives None; `LADO_UNINSTALL_REMOVER` gives its argv.
2. Code: `remover(where=None)`.
3. Run; commit.

## Task 4: the plan (D1, D3, D4, D6, D7, D10)

**Files:** `src/lado/uninstall.py`, `tests/test_uninstall.py`.

1. Tests (`tmp_path` homes and repos, tmux and the server's `running` replaced):
   - `plan()` lists the UI server, running and stopped sessions with the socket, each
     repository with remove/keep and the reason, the home with its size, the remover or
     why the program stays, the agent CLIs' line (spec: "The plan comes before any
     change");
   - a newer `user_version` raises before a plan; an older one is shown with the
     migration line, read-only (the file's bytes and mtime unchanged);
   - no `lado.db`: no sessions, the folder and the program only;
   - default-home detection: `LADO_HOME` unset with `HOME` at `tmp_path`, set to the same
     folder by another spelling (a symlink), set elsewhere;
   - the guard: `LADO_HOME` = `HOME`, `/`, an ancestor of `HOME`, a folder without
     `lado.db` that is not the default: planned as kept with the reason;
   - `--dry-run`'s path (`plan` + `print_plan`) changes nothing: a listing of the home and
     the repos, `git worktree list` and `git branch` before and after are equal.
2. Code: `Plan`, `plan()`, `print_plan(plan, say)`.
3. `uv run pytest tests/test_uninstall.py -n auto`; commit.

## Task 5: the run (D2, D4–D9)

**Files:** `src/lado/uninstall.py`, `tests/test_uninstall.py`.

1. Tests:
   - order: the lock, server stop, `stop_all`, `wait_stopped` per session, viewers,
     kill-server only with no session left (recorded tmux: with another session listed,
     no kill-server and the session named) (spec: "Everything of this LADO_HOME stops");
   - a loop that does not end: exit 1, no repository or file touched;
   - the update's lock held: refused, nothing changed ("Refusals…");
   - repositories: merged worker removed; unmerged and dirty kept and listed with both
     git commands; a branch without worktree, merged and not; a gone repository named and
     passed over; `.lado/sdlc.md` kept; the exclude line and `.lado/worktrees` gone only
     when empty; a worktree of another session folder keeps them ("Repositories keep
     every line of work");
   - the home deleted; the guard keeps it with exit 1; an undeletable file (a read-only
     folder) named with exit 1 ("LADO_HOME is deleted whole and only it");
   - the program: default home runs the remover last (`LADO_UNINSTALL_REMOVER` as a
     script that records its argv and the time after the home is gone); another home
     keeps it and prints the command; no remover prints the prefix and how; a failing
     remover gives its exit code, the command and exit 1; `sys.modules` gains nothing
     after the remover started (as the update's test does) ("The program goes last…");
   - `--keep-data`: stops, runs the remover, home and repos unchanged ("Keep data");
   - exit codes and the `Left on this machine:` block ("The outcome is said step by
     step").
2. Code: `run(plan, say, keep_data)`; `self_update.take_lock` made public for it.
3. Run; commit.

## Task 6: the CLI

**Files:** `src/lado/cli.py`, `tests/test_cli.py`.

1. Tests: `lado uninstall --help` names the three options; inside an agent refused;
   `--dry-run` exits 0 without asking; `n` and an empty answer print `Not uninstalled.`
   and exit 1; no terminal without `--yes` exits 1 with `lado: not uninstalled: confirm
   with --yes`; `--yes` calls `run`; `main` does not call `migrate_if_safe` for
   `uninstall`; a newer database is printed as LADO's error, exit 1.
2. Code: the parser entry (help `remove LADO: stop its sessions and UI server, clean
   their repositories, delete LADO_HOME and the program`), `cmd_uninstall`, the
   migration exception beside `stop`.
3. `uv run pytest tests/test_cli.py tests/test_uninstall.py -n auto`; commit.

## Task 7: end to end with the fake agent

**Files:** `tests/integration/test_uninstall.py`.

1. `test_uninstall_leaves_nothing`: a session with the fake agent, a worker whose branch
   is merged into the repo's current branch, a worker with an unmerged commit, the UI
   server started in the background, a UI terminal viewer open; `lado uninstall --yes`
   (the test's `LADO_HOME`, so the program stays): exit 0; no process of the session
   (agents, `lado loop`, the server's pid) is alive; `tmux -L <test socket>` has no
   server; the merged worktree and branch are gone, the unmerged ones listed and there;
   the test's `LADO_HOME` is gone; the output names the program as kept.
2. `test_uninstall_keep_data_resumes`: `lado uninstall --keep-data --yes`, then `lado
   start <repo> --name <session>` resumes with the run's history and the worktrees in
   place.
3. `uv run pytest -m integration -n auto tests/integration/test_uninstall.py`; commit.

## Task 8: docs

**Files:** `docs/install.md`, `README.md`, `AGENTS.md`, `CHANGELOG.md`.

1. `docs/install.md`: a section **Uninstall** (after Update, in the contents list): the
   command, its options, what it stops, the repository rule, what it leaves and why
   (kept work with its commands; clones in `~/lado`; per agent CLI its own records:
   Claude Code `~/.claude.json` projects and `~/.claude/projects/`, Codex nothing of
   LADO's agents (their homes were LADO's), OpenCode and Kilo their data folders under
   `~/.local/share/`); **By hand** for a LADO before 0.37 or a pip install: `lado stop
   --all`, `lado server stop`, per repository `git worktree list` and the removal of
   `.lado/worktrees/*` work and `lado/*` branches, `rm -rf ~/.lado`, `uv tool uninstall
   lado` / `pipx uninstall lado` / `pip uninstall lado`; the release test of an upgrade
   (design doc).
2. README.md: one line under Update pointing to the section.
3. AGENTS.md: Layout gets `uninstall.py`; the CLI sections a paragraph on `lado
   uninstall`; `update.py`'s entry names `remover` and `LADO_UNINSTALL_REMOVER`.
4. CHANGELOG.md under `## 0.37.0 (unreleased)`: one line for `lado uninstall`.
5. `openspec validate uninstall --strict`, `make lint`; commit.

## Regression run

`make lint`; `make test` (`-n auto`, report the numbers); `uv run pytest -m integration
-n auto tests/integration/test_uninstall.py`; `openspec validate --specs --strict`. CI
runs the rest (`make check`, smoke). No live test: nothing in a provider changes.
