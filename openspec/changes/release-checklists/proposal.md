Task: LAD-253

## Why

The manual check of a release candidate, docs/release.md section 4, mixes two kinds of
check: those every RC needs (a clean install, the human's own LADO moved onto the RC and
back, the image and its update, the installers) and those of one version (items marked
"from 0.43.0", "from 0.45.0": projects with each CLI, secrets in three browsers, model
servers, real phones). The second kind only grows: each release adds its items and none
leaves, so the section goes stale. The audit before 0.45.0rc1 (session artifact
`release-md-audit`) found eight places where it was wrong for 0.45.0, twelve missing
steps and several steps that the Release workflow's container tests already run on the
bytes it publishes. For 0.45.0rc1 the human was given a separate checklist of that
version (`release-checklist-0.45.0rc1`), which worked better than the section.

`scripts/rc_check.py` ends `sandbox` and `upgrade` with "what is left by hand", but it
prints its own two lines (`BY_HAND`, a second copy of 4.3's first lines) and every item
of CHANGELOG.md's `## X.Y.Z (unreleased)`; 4.3's other items and 4.4 to 4.6 are not in
it, so the printed list matches neither the document nor what the human really checks.

Cause: the document has no place for a version's own checks, so they were added to the
permanent text, and the script's list is kept by hand beside the document.

Options weighed for where a release's checklist lives:

- A (taken, the human's choice): in the repository, `docs/releases/X.Y.Z.md`, one file per
  version with one section per RC, written before that RC's commit; `release_check.py`
  lets the final differ from its last RC in that file, as in CHANGELOG.md. The checklist
  has a history, `rc_check.py` reads it from the checkout at the tag, and the human's
  edits after the last RC need no new RC. Long-term cost: one more file per release and
  one more exception in the freeze check, limited to the final's own file.
- B: in the repository without the exception: an edit after the last RC forces a new
  RC for a document no user runs.
- C: outside the code (a tracker task or a LADO artifact): `rc_check.py` cannot print it,
  and nothing in the repository says what a release was checked for.

## What Changes

- **docs/release.md** keeps the release's order and the checks of every RC, corrected by
  the audit (part «г» of `release-md-audit`), and drops every version's own item:
  - section 2 gains the step before the RC's commit: write the RC's section of
    `docs/releases/X.Y.Z.md`;
  - section 4 opens with the list of the every-RC checks by hand, one `- [ ]` line each,
    the one list `rc_check.py` prints; then 4.1 the clean install, 4.2 the own LADO
    (with `ls ~/.lado-rc` before and after), 4.3 by hand: the sdlc run to its first gate
    and a look at the UI, 4.4 going back (read `lado update <final>`'s warning before
    `y`: it names what is lost), 4.5 the image (all of it on the Mac; on Linux the pull and
    one session, as the container tests run the rest on the bytes published; the
    installers only when `docker/install.sh` or `docker/install.ps1` changed since the
    last final), 4.6 the image's update (first RC of a cycle, without the second LADO
    beside it, which `tests/container/test_two_lados.py` covers);
  - a new subsection 4.7, "The release's checklist": where it lives, when and by whom it is
    written, its form, and what goes into it (each CHANGELOG item with what covers it and
    what to try by hand, and an earlier version's check again only when the release
    touches it);
  - the System panel is named as the popover of `live` in the top bar; the New session
    path and the fresh container's New session window are written as rc1 has them.
- **docs/releases/0.45.0.md**: new, the checklist of 0.45.0, in English: its section
  `## 0.45.0rc1` made from the session artifact `release-checklist-0.45.0rc1` and the
  version's items that leave docs/release.md (projects, models, the New session window,
  the folder of documents, real phones, Codex in the container, the Codex shared login's
  live test, the model servers lost on going back, the resume of a kept model after the
  image's update). The section of rc2 is written by rc2's release task.
- **scripts/rc_check.py**: the list at the end of `sandbox` and `upgrade` is the every-RC
  list of docs/release.md, then the items of the RC's own section of
  `docs/releases/X.Y.Z.md`; `BY_HAND` and the printing of CHANGELOG items go.
- **scripts/release_check.py**: a final `vX.Y.Z` may differ from its last RC in
  `docs/releases/X.Y.Z.md` too.
- Tests, docs/design/modules.md and docs/telemetry.md follow.
- No CHANGELOG.md line: internal documents and release tooling, which users do not
  notice (docs/release.md, CHANGELOG rule 6). No version bump: the change ships in
  0.45.0rc2, a fix release of the frozen 0.45.0.

## Scope

- docs/release.md, the new `docs/releases/` with 0.45.0's checklist, `rc_check.py`'s
  printed list, `release_check.py`'s exception, their tests and the documents that
  describe them.

## Out of scope

- The human's report on 0.45.0rc1 and its remarks about the process: it comes later; its
  findings are their own tasks (or a revision of this design before `design_ok`).
- Checking the image in `rc_check.py` (docs/release.md: by hand): a feature, not this
  change.
- The section `## 0.45.0rc2` of 0.45.0's checklist: written by rc2's release task, from
  the fixes merged after rc1, before rc2's commit; this pull request is one of them.
- Checklists of past releases: the archive of a release's checks starts with 0.45.0.
- A checklist for a patch released without an RC: `rc_check.py` does not run for it, and
  section 5 already names its checks.
