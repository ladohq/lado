Task: LAD-247

## Why

Found in the review of PR #258 (LAD-242): its description was the text of PR #260 (LAD-240).
The developers of the two runs wrote their draft of the description to the same file,
`/tmp/claude-1000/pr.md`; the second run overwrote it, and the first one's `gh pr edit` sent
the other run's text.

Cause: every agent of a machine (LADO's container, or the user's host) runs as one user with
one `/tmp`, and LADO gives no agent a temporary folder of its own:

- an agent has no `TMPDIR` of LADO's (checked in the container: unset), so `mktemp`, Python's
  `tempfile` and the agent CLIs all write to the shared `/tmp`;
- Claude Code keeps its own temporary folder, where each agent's scratchpad is, in
  `/tmp/claude-<uid>`, one for all its agents on the machine: its root is taken from
  `CLAUDE_CODE_TMPDIR` (else `/tmp/claude`), not from `TMPDIR` (read in Claude Code 2.1.295's
  own code, the image's). The model sees that prefix and puts a file of a habitual name
  (`pr.md`) at its root, the same name in every agent;
- Kilo and OpenCode keep folders in the shared `/tmp` too (`/tmp/kilo`, `/tmp/opencode`);
- no instruction tells an agent to keep its temporary files apart.

Options weighed (the human's answer #5725, "all recommendations"):

- A rule in the sdlc kit's roles only: guards those roles alone, not other kits; lives in
  another repository; nothing enforces it. Long-term cost: every kit repeats it.
- A line in LADO's instructions only: cheap, but a model may ignore it, and `mktemp` and the
  CLIs still write to the shared `/tmp`.
- Taken: LADO gives each agent a temporary folder of its own as its `TMPDIR`, for every
  provider (and as Claude Code's own temporary root), and every agent's instructions say to
  keep temporary files there. One place in the core, every kit and provider covered; the
  coming cloud workers (ROADMAP, Later) keep it as it is.

## What Changes

- Each agent LADO launches (a session's start, a resume, `spawn_worker`, a run's worker) gets
  its own folder `<parent>/lado-<uid>/<session>/<agent>`, owner only (0700), as `TMPDIR`; the
  parent is the `TMPDIR` the agent's environment has from its layers (login shell, outside
  folder, project), else `/tmp`.
- A Claude Code agent also gets that folder as `CLAUDE_CODE_TMPDIR`, so its own temporary
  folder and scratchpad are its own.
- The folder stays over a stop and a resume and goes when LADO forgets the agent
  (`finish_worker`) or its session (`lado forget`).
- A user's own `TMPDIR` (login shell, outside folder, project) becomes the parent; it is not
  named as a variable LADO does not use.
- Every agent's instructions (supervisor and workers, every provider) say that its temporary
  files go to `$TMPDIR`, never to a fixed path in `/tmp`.
- A `lado-<uid>` folder that is not a folder of the user's own (a link, a file, another
  owner) refuses the launch with a line naming it.
- A patch (0.46.1): a fix, no MCP tool, CLI or schema change.

The folders keep agents from colliding by name; they are not a security boundary: an agent of
the same user can still read another's folder if it goes there on purpose.

## Scope

- `src/lado/runtime.py` (the folder at each launch, `TMPDIR` in the launch environment, the
  instructions' line, the warnings of variables not used, the removal on forget),
  `src/lado/agent_env.py` or `src/lado/providers/base.py` (where the folder's path is made),
  `src/lado/providers/claude.py` (`CLAUDE_CODE_TMPDIR`).
- Tests: unit (`tests/test_runtime*.py`, `tests/test_claude.py`, the providers' launch tests),
  integration with the fake agent (`tests/integration/`), live (`tests/live/test_live.py`).
- `docs/design/agents.md` (an agent's environment), CHANGELOG.md under `## 0.46.1 (unreleased)`.

## Out of scope

- A rule in the sdlc kit (kit-sdlc): LADO's line covers every role of every kit (#5725, 4);
  no task for the kit.
- Isolation between agents by permission (one user per agent, a sandbox): same user by
  LADO's design; the task asks against collisions.
- Moving the files of an agent's CLI that do not follow `TMPDIR` or `CLAUDE_CODE_TMPDIR`
  (Claude Code's messaging sockets in `/tmp/cc-socks`, tmux's `TMUX_TMPDIR`): they are the
  CLI's own, named per process, and did not collide.
- Cleaning `/tmp` of folders left by older LADO versions or crashed sessions.
