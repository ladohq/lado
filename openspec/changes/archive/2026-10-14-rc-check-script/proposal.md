Task: LAD-51

## Why

Every release candidate (RC) is checked by the human by hand (docs/release.md, section 4),
and that section is six one-line items that leave the hard parts to guesswork: which
repository to start a session on, how to remove the scratch home, its tmux server and its
session afterwards, which final release to go back to, and how.

The rollback written there does not work when the RC moved the database's schema:
`lado update` keeps exactly one backup of lado.db (`self_update._back_up` deletes every
other file in `~/.lado/backups/`), so the final's backup is gone after the next update,
the update back to the final included, and the final refuses the newer database.

Root cause: the checklist is prose for a person to retype, with versions, paths and
variables to fill in, and nothing keeps the one file a rollback needs.

## What Changes

- **`scripts/rc_check.py`** (standard library only, run with `python3` from the
  repository's root), three commands:
  - `sandbox [X.Y.ZrcN]`: a clean install of the RC (by default the newest release on
    PyPI; a final there is refused with a request for the RC's version) with
    `uv tool install` into a temporary folder, a `LADO_HOME` and a tmux socket of its
    own, every LADO process with `LADO_TELEMETRY=0`. Checks, one `[ok  ]`/`[FAIL]` line
    each: the installed version, statistics off, `lado doctor` (no FAIL, `(pre-release)`),
    a session on a scratch git repository started and shown by `lado ls`. Then the
    sandbox's UI and its link until the human presses Enter (`--no-ui` skips it), the
    session stopped, and everything removed with the RC's own `lado uninstall --yes`.
    A failed check stops it and keeps the folder, printing its path and the command that
    removes it; Ctrl-C removes everything. The human's own `~/.lado` is never touched.
  - `upgrade X.Y.ZrcN`: runs the human's own `lado update X.Y.ZrcN` on the terminal (its
    plan and question as usual) and, when the LADO it updated was a final release,
    copies that final's backup `~/.lado/backups/lado.db.<final>` to
    `~/.lado-rc/lado.db.<final>`, the only copy kept there.
  - `rollback`: back to the final the copy was taken from. It prints its plan and asks;
    stops the human's sessions and UI server, runs `lado update <final>`, restores
    lado.db from the copy when the RC moved the schema, then starts the sessions and the
    UI again on the final.
  - `sandbox` and `upgrade` end with what is left by hand: the sdlc session to its first
    gate, the UI, and each item of CHANGELOG.md's `## X.Y.Z (unreleased)` as a checklist.
- **docs/release.md, section 4** rewritten around the script (the text in the design
  doc's appendix, shown to the human as `release-section-draft.md`): 4.1 a clean install, 4.2 your own LADO on the RC, 4.3 by
  hand, 4.4 going back.
- **`scripts/release_notes.py`** gives its section's text as a function of its own, which
  `rc_check.py` reads the CHANGELOG items through.
- AGENTS.md (Layout, `scripts/`) names the script.

## Scope

In: the script and its unit tests, section 4 of docs/release.md, the small refactor of
`release_notes.py`, AGENTS.md's line.

## Out of scope

- **`lado update` keeping the final's backup** (several backups, or one per final): a
  change to LADO itself for what only the RC tester meets; the script's copy in
  `~/.lado-rc/` covers it. A tracker task only with the human's yes.
- **The sdlc session to its first gate in the sandbox**: kit sdlc needs a tracker,
  its key and `.lado/sdlc.md`; it is checked by hand on the human's own LADO, in a real
  project (the human's decision).
- **A model turn in the sandbox**: the session only has to start and stop; Claude Code
  waits on its folder trust dialog without calling a model.
- **Running the script in CI or an integration test**: it installs from PyPI and starts a
  real agent CLI; unit tests with a recorded runner cover its logic, and the developer
  runs `sandbox` once on a published RC.
- **A CHANGELOG line and a version bump**: the script and the docs are not in the package
  users install.

## Impact

- New: `scripts/rc_check.py`, `tests/test_rc_check.py`.
- Changed: `scripts/release_notes.py` (a `section` function), `tests/test_release_notes.py`
  if needed, `docs/release.md` section 4, AGENTS.md (Layout).
- LAD-50 (open) adds `LADO_TELEMETRY=0` to the same section and a test that every
  `LADO_HOME=$(mktemp -d)` line of docs/release.md has it; the section no longer has such
  lines, so whichever change lands second moves that check onto the script (design D9).
- No change to the `lado` package, no schema, no MCP or API change. Version: none.
