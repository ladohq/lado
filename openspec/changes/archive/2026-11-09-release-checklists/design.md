## Context

docs/release.md section 4 and `scripts/rc_check.py`'s printed list are rewritten so that
docs/release.md holds the checks of every RC and `docs/releases/X.Y.Z.md` those of one
version (proposal.md). The human chose: the checklist in the repository with an exception
in `release_check.py`, written before each RC's commit with one section per RC, printed
by `rc_check.py` after the every-RC checks, in English, and 0.45.0's checklist in this
pull request.

## Decisions

### D1. docs/release.md's every-RC list is the one source of the script's permanent lines

Section 4 opens with `### The checks of every RC`, one `- [ ] ` line per check, each naming
its subsection (`4.1`, …) and saying "first RC of a cycle" where it holds only then.
`rc_check.py` reads those lines from `docs/release.md` in the current folder: the list
between that heading and the next heading, its top-level `- [ ] ` lines. `BY_HAND` goes.
Why: a second copy in the script drifts (AGENTS.md, one source of truth); today's two
lines already do.

### D2. A release's checklist: one file per version, one section per RC

`docs/releases/X.Y.Z.md` starts with `# LADO X.Y.Z: the release's checks`, a short
paragraph (the last final, the schema's move, what the every-RC checks of docs/release.md
cover), then `## X.Y.ZrcN` sections in order. A section's items are top-level
`- [ ] **Title.**` lines, an item's detail on nested lines under it; `###` subheadings may
group items. `rc_check.py` prints `[ ] <first line after "- [ ] ">` for each top-level
item of the RC's own section, from its heading to the next `## ` heading. The first RC's
section holds the version's whole list; a later RC's only what its fixes touch.
Why: the printed list stays one line per check, and rc2 does not repeat rc1's work.

### D3. The checklist's parse is the script's own, standard library only

`rc_check.py` imports nothing of LADO (its docstring); the parse is a few lines of its own
(heading match by `re`, items by prefix). `release_notes.section` is no longer used by it,
since CHANGELOG items are no longer printed: their review is part of the checklist.

### D4. Missing pieces are warnings, as the missing CHANGELOG section was

No `docs/release.md` here: one line `warning: no docs/release.md here: run the script
from the repository's root`, and nothing else. No list under the every-RC heading:
`warning: docs/release.md has no list "The checks of every RC"`. No file or section:
`warning: docs/releases/X.Y.Z.md has no section "## X.Y.ZrcN": write the RC's checklist
before its commit (docs/release.md, section 2)` (or `no docs/releases/X.Y.Z.md`). The
warning about a pyproject.toml of another version stays, now saying the checklist may not
be the RC's. Exit codes do not change. Why: no silent drop, and a missing document never
fails a check that passed.

### D5. release_check.py frees only the final's own checklist

`FREE` gains `docs/releases/X.Y.Z.md` for the tag `vX.Y.Z` being checked, not the whole
folder: an edit of another release's file after the last RC is still refused. Why: the
exception is as narrow as the need (the human's edits of this release's checklist).

### D6. The every-RC checks after the audit

Kept every RC: 4.1 sandbox; 4.3 the sdlc run to its first gate answered in the UI and a
look at the chat, a gate's card and the System panel's `pre-release` pill (the popover of
`live`); 4.4 `rollback` (reading `lado update <final>`'s warning before `y`) and, once per
RC that moved the schema, the user's way back on a test home; 4.5 the image on the Mac in
full (no Docker Desktop in CI), on Linux the pull and one session, the installers on the
Mac and Windows only when `git diff --stat vX.Y.Z vX.Y.ZrcN -- docker/install.sh
docker/install.ps1` prints something. First RC of a cycle: 4.2 `upgrade` (with `ls
~/.lado-rc` before and one `lado.db.<final>` after), 4.6 the image's update from the last
final, without the second LADO beside it. Fixed by the audit (part «а» and «г» of
`release-md-audit`): New session → Where → Project… → the project → Repository → "Start in
<title or id>"; in a fresh container the window opens on New empty folder and Where →
Other folder… lists `LADO_WORKSPACE`'s folders. Every "from 0.4x.0" item moves to
0.45.0's checklist. Why: the human's answer 3; the Linux part and the second LADO are the
container tests' (`tests/container/`, on the bytes pushed, docs/release.md section 8).

### D7. The fresh-home telemetry guard reads the checklists too

`tests/test_telemetry.py::test_release_checks_in_a_fresh_home_send_nothing` checks every
`LADO_HOME=$(mktemp -d)` line of docs/release.md; the Mac's project-secrets step with such
a line moves to `docs/releases/0.45.0.md`, so the test reads `docs/releases/*.md` too.
Why: the guard must not lose the line it was written for.

### D8. Test layers

All unit (`make test`): `rc_check.checklist` and `release_check.problems` are pure logic
over files and a git repository made in a temp folder, as their tests are now. Nothing
crosses LADO's processes; no integration or UI test.
