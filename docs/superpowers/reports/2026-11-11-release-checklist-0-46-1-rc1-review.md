# LAD-272 release-checklist-0-46-1-rc1: review report

Pull request #290 `fix/lad-272-release-checklist-0-46-1-rc1` → `main`. Scale: tweak, depth
precision. Head reviewed: `37b62453`. The release checklist `docs/releases/0.46.1.md` gains its
section `## 0.46.1rc1`; CHANGELOG.md's `## 0.46.1 (unreleased)` loses its task keys, and its items
on the temporary folders and on `lado stop` are written in the user's words; the real-file test of
`tests/test_rc_check.py` also checks `0.46.1rc1`. No delta (archived with `--skip-specs`).

## Rounds

1. Local, precision. The range `dc9375f1..37b62453`. Every quoted line of the checklist against the
   code (`loop.py`, `providers/base.py`, `runtime.py`, `doctor.py`, `cli.py`, `LaunchModel.tsx`,
   `install.sh`, `kilo.py`), and the loop's lines and `loop.wait_stopped` against `v0.46.0` for
   4.2's update and 4.4's rollback; the 15 named test files exist; the checklist matches the
   proposal's block byte for byte; 6 of 6 tasks checked. Finding F1.
2. External 1, Claude Code GitHub Action: no blockers; E1-E3 confirmed (minor), E4 refuted. It did
   not read `proposal.md`, which matches the checklist it read.

External rounds used: 1 of 1. Stand-ins: 0.

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| F1 | minor | local: the `lado stop` item of CHANGELOG still says "loop" (rule 4, LADO's inside) | declined: the human approved the text (#5923); the user sees the word in `lado ls` (`session loop not running`) |
| E1 | minor | external: the unsafe-folder check depends on the login shell; a shell whose startup files set `TMPDIR` lets the start pass | declined: no false green, the check then fails loudly ("the start passed") |
| E2 | minor | external: the broken-session check lacks the `loop.log` line `loop ended: its tmux session is gone` | declined: the CHANGELOG item promises the red row and `lado ls`, which the check looks at |
| E3 | minor | external: "no new `/tmp/opencode`" cannot be told from an older folder without an `ls` before the start | declined: "no new … made by them" already means a comparison; wording |
| E4 | — | external: the supervisor's folder kept after a finish is not told from one that never was | refuted: the section's first check shows it with `ls -ld` |

## Found on the way

None.

## Checks

On `37b62453`:
- `make lint` green; `make test` 6155 passed, 7 skipped.
- `scripts/release_notes.py v0.46.1rc1`: 8 items, no `LAD-`.
- `openspec validate release-checklist-0-46-1-rc1 --strict` valid; the trial archive with
  `--skip-specs`, then `openspec validate --specs --strict`: 83 passed.
- CI 27/27, `ci-ok` pass, `mergeStateStatus: CLEAN`.

Not run: `scripts/rc_check.py` (it installs from PyPI; `tests/test_rc_check.py[0.46.1rc1]` covers
its list), the live tests (they run on the RC's commit), the checklist's manual checks (the human
runs them at the RC).

No change to `providers/`, `hooks.py`, `mcp_server.py`, `runtime.py`, `agent_env.py` or
`tests/live/`.
