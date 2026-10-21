Task: LAD-112

## Why

`tests/integration/test_uninstall_process.py::test_uninstall_leaves_nothing` fails now and
then on `assert not any(alive(pid) for pid in pids)`: right after `lado uninstall --yes`
an agent's process is still there (CI of PR #116, run 39305606788, integration 3.13 shard
3; the failed job passed on a rerun).

Root cause: `lado uninstall` stops a session with `tmux kill-session` and then ends the
tmux server with `kill-server`. Both return at once: tmux sends the agents SIGHUP and each
agent's process ends on its own, a moment later; a process whose parent, the tmux server,
has ended stays a zombie until init reaps it. The uninstall never waits for them, and the
test looks at once.

This is not the test's defect alone. On SIGHUP Claude Code (and the fake agent with
`FAKE_AGENT_HANGUP_HOOK`) first runs its session-end hook, `lado hook`, which opens
`lado.db` through `state.home()`, and `state.home()` makes the folder. When the uninstall
has deleted `LADO_HOME` by then, the dying agent makes `~/.lado` again with an empty
`lado.db`, and a confirmed uninstall leaves the folder behind. The living spec
(`uninstall`, "Everything of this LADO_HOME stops") already says that no agent process is
left.

## What Changes

- **`lado uninstall` waits for the agents' processes to end.** Before it stops the
  sessions it takes the process of each of their tmux panes; after the sessions and their
  loops have stopped, and before any repository or file is touched, it waits up to 10 s
  for those processes to end. A zombie counts as ended.
- **An agent that does not end stops the uninstall**, as a loop that does not end does:
  exit 1 before any repository or file is touched, naming the session, the pids and the
  command that ends them (`kill <pid> ...`); `lado uninstall` run again goes on.
- **The test stays strict and gains a case**: `test_uninstall_leaves_nothing` keeps its
  check at once after the uninstall; a new integration test with an agent that runs its
  session-end hook on SIGHUP checks that `LADO_HOME` is not made again.
- `docs/cli.md` (`lado uninstall`): it waits for the agents' processes.
- CHANGELOG.md: one line under `## 0.42.1 (unreleased)`, Fixed.

## Scope

`src/lado/uninstall.py`, a helper in `src/lado/tmux.py` for the panes' processes,
`tests/test_uninstall.py`, `tests/integration/test_uninstall_process.py`, `docs/cli.md`,
`docs/design/modules.md` (the module line, if it names the stop's steps), CHANGELOG.md. A
patch (a fix); no schema, MCP tool or CLI option change.

## Out of scope

- **`lado stop` and `lado update`**: after their stop nothing is deleted, so an agent that
  ends a moment later writes into a `lado.db` that is still there; the race is harmless
  there (agreed with the human).
- **Killing an agent that does not end with SIGKILL and going on**: its children (the
  hook, MCP servers) could be left, and the uninstall would delete files under them;
  stopping with the command to end it keeps "no repository or file is touched after
  something did not stop" (agreed with the human).
- **Only waiting in the test** (`wait_for`): the flake goes, but `~/.lado` can still come
  back after a real uninstall.
- **`state.home()` not making the folder for a hook**: every process of LADO opens
  `lado.db` through it; changing that is wider than this defect and does not stop a hook
  that runs before the deletion from racing it.

## Impact

- `src/lado/uninstall.py` (`_Uninstall._stop`), `src/lado/tmux.py`.
- `tests/test_uninstall.py`, `tests/integration/test_uninstall_process.py`.
- `docs/cli.md`, CHANGELOG.md.
- Modified capability spec `uninstall`.
