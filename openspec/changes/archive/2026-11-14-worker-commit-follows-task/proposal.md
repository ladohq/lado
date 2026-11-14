Task: LAD-173

## Why

A worker told by its supervisor "Create hello.txt … Do not commit" committed anyway and said
why: "the worker instruction required committing although the task body said not to". Found in
the manual check of 0.44.0rc1 (2026-11-02), Codex in LADO's container (commit b852a5b on
`lado/demo/worker`).

Cause, checked against the code at d432b0f6: the rule is not in the default kit's role
`worker` (it says nothing of commits) but in LADO's own instructions for every worker,
`runtime.WORKER_INSTRUCTIONS` ("Commit your work on that branch.") and, for a flow run's
worker, `runtime.RUN_WORKER_INSTRUCTIONS` ("Commit your work on that branch."). They go into
the agent's system prompt (Claude Code's `--append-system-prompt-file`, Codex's
`developer_instructions`, the OpenCode family's `instructions`); the task arrives as a message. The rule names no exception,
so the model ranks it over the task. Every kit's workers have the defect, not only the default
kit's.

Options with their long-term cost:

- **The rule names the task as its exception (taken).** One sentence in LADO's two worker
  instructions: commit by default, unless the task explicitly says otherwise. Neutral (the same
  text for every provider), one place, no cost later.
- Move the rule out of LADO into the kits' roles: every kit repeats it, and a kit that forgets
  gets workers that never commit, whose work `lado finish` cannot merge. Rejected: a second
  source of the same rule.
- A general rule "the task wins over LADO's instructions": the task could then switch off the
  report by `send_message`/`flow_advance` or a read-only role's limits. Rejected: too wide.

## What Changes

- `runtime.WORKER_INSTRUCTIONS` and `runtime.RUN_WORKER_INSTRUCTIONS`: "Commit your work on
  that branch." becomes "Commit your work on that branch, unless your task says otherwise: an
  explicit instruction of your task (not to commit, to leave the branch as it is) wins over
  this default." The rest of both texts is unchanged.
- A live test: a worker told "Do not commit" leaves its branch without a new commit and the
  file in its worktree; a worker whose task says nothing of commits commits its work.
- Docs: `docs/design/agents.md` (what a worker's instructions say of commits), CHANGELOG under
  Fixed.
- Version: the patch; it rides in `## 0.47.0 (unreleased)`.

## Scope

`src/lado/runtime.py` (the two texts), a unit test of the texts, a live test, the docs above,
CHANGELOG.

## Out of scope

- The default kit's role `worker`: it has no rule on commits, so nothing to change there.
- The supervisor's instructions: a worker that did not commit as told is refused by
  `lado finish` / `finish_worker` for its uncommitted changes, as today; the supervisor asks it
  to commit or finishes with `discard`. That refusal is the safeguard against lost work and
  stays.
- Other rules of the workers' instructions (reporting, read-only roles, the container's tool
  versions): the task does not override them (see the rejected general rule).
- A check by LADO that a worker obeyed (e.g. comparing its branch with its task): the model's
  judgement is the fix; LADO cannot parse a task's free text (only what is used).
