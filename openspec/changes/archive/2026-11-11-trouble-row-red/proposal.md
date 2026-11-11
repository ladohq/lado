Task: LAD-229

## Why

A session whose tmux session is gone or whose loop does not run shows its status in words on
its row of the session list (`tmux session is gone`, `session loop not running`) in `--muted`
with a hollow `--muted` ring before it. Its head and its strip icon's tooltip say the same
trouble in `--danger` with a full `--danger` dot, and `docs/design/ui.md` (Look) says
`--danger` marks a session that needs an action. So the one row that needs the human's action
does not stand out in the list.

Cause: the rule `.status-stopped, .status-tmux_gone, .status-loop_down { color: var(--muted) }`
in `web/src/styles.css` is older than LAD-223 and dates from when the list greyed every session
that did not run; stopped sessions later lost the status line (their line says "stopped … ago"),
and the trouble kept the grey. Not a design choice: the document and the mockup of LAD-223 say
`--danger`. Found in the review of LAD-223 (BACKLOG.md, "A row's trouble status is grey where
the design says red").

Options weighed (mockup artifact `task/lad-229/mockup-trouble-status.html`):

- B (taken, the human, 2026-11-11): the status in words in `--danger` with a full `--danger`
  dot before it, the dot of the trouble in the session's head and its icon's tooltip. One mark
  of trouble everywhere. Long-term cost: none; one CSS rule less.
- A: `--danger` text with a `--danger` ring. The hollow ring already means "idle" in the list
  (a running session with no agent at work), so a red ring reads as a red idle.
- Keep the grey and change the document: the trouble stays hidden in the list, against the
  rule that `--danger` marks a session that needs an action.

## What Changes

- A row of a session in trouble (`tmux_gone`, `loop_down`) shows its status in words in
  `--danger`, with a full `--danger` dot before it, in both themes.
- The dead selector `.status-stopped` goes: the row never shows a stopped session's status.
- BACKLOG.md loses the entry "A row's trouble status is grey where the design says red".
- A patch (0.46.1): a UI fix, no API, CLI or schema change.

## Scope

- `web/src/styles.css`: the rules `.status-stopped, .status-tmux_gone, .status-loop_down` and
  `.status-tmux_gone::before, .status-loop_down::before`.
- Tests: UI e2e (`tests/ui/test_session_list.py`).
- `docs/design/ui.md` (the session list's rows; Look).
- CHANGELOG.md under `## 0.46.1 (unreleased)`; BACKLOG.md.

## Out of scope

- The session's head, the strip's icon and its tooltip: they already show the trouble in
  `--danger`.
- The row's title, its line and its group: a session in trouble in which something waits stays
  under Needs you with its line saying what waits.
- The status words themselves (`lado ls`'s words): unchanged, by the task.
- The phone: the list is the same component and takes the same rule; nothing of its own.
