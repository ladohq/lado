## 1. release_check.py frees the final's own checklist (D5)

- [x] 1.1 `tests/test_release_check.py` (unit, a git repository in a temp folder as its
  other tests): a final whose commit also changes `docs/releases/0.37.0.md` against
  `v0.37.0rc2` passes; one that changes `docs/releases/0.36.0.md` fails with
  `v0.37.0 differs from v0.37.0rc2 in docs/releases/0.36.0.md`. Red before 1.2.
- [x] 1.2 `scripts/release_check.py`: the final's `docs/releases/X.Y.Z.md` is free beside
  `FREE`; its docstring names it. 1.1 passes.

## 2. rc_check.py prints docs/release.md's list and the RC's section (D1-D4)

- [ ] 2.1 `tests/test_rc_check.py` (unit): replace the three `test_checklist_*` tests with
  ones over a docs/release.md text with the every-RC list and a checklist text, one per
  scenario of "The release candidate's checklist is docs/release.md's and the release's
  own": every-RC lines then the RC's top-level items, nested lines left out; only the RC's
  own section (`rc2` of a file with `rc1` and `rc2`); no file, no section, no list, no
  docs/release.md, each its warning line of D4; the pyproject.toml warning kept. A test
  over the real `docs/release.md` and `docs/releases/0.45.0.md`: `checklist` of
  `0.45.0rc1` has no warning line. Red before 2.2.
- [ ] 2.2 `scripts/rc_check.py`: `checklist(version, release_md, checklist_md, pyproject)`
  by D1-D4, `print_checklist` reads `docs/release.md` and `docs/releases/X.Y.Z.md` from
  the current folder; `BY_HAND`, `_release_notes` and the CHANGELOG items go; the module's
  docstring says what the list is. 2.1 passes; `tests/test_release_notes.py`'s test of
  `rc_check` reading CHANGELOG items goes or changes with it.

## 3. docs/release.md: the order and the checks of every RC (D6)

- [ ] 3.1 Section 2: step 0, before `uv version`, writes the RC's section `## X.Y.ZrcN` of
  `docs/releases/X.Y.Z.md` (the file made at the first RC), in its own pull request the
  human reads, or in the RC's commit.
- [ ] 3.2 Section 4: its intro says what `rc_check.py` prints (the list below, then the
  RC's section) and that the System panel is the popover of `live` in the top bar; then
  `### The checks of every RC` with one `- [ ] ` line per check of D6. 4.1-4.6 rewritten
  by D6 from part «г» of the session artifact `release-md-audit`, every "from 0.4x.0" item
  removed (moved by 4.1), the Linux part of 4.5 shortened, the installers' skip rule, 4.6
  without `/tmp/lado-rc-beside`. The line "Each line of CHANGELOG.md's … tried once" goes:
  the checklist reviews them.
- [ ] 3.3 A new subsection at the end of section 4, `### 4.7 The release's checklist` (no
  section is renumbered, so the `section N` references and `.lado/sdlc.md`'s "The final"
  stay right): where it lives, D2's form, who writes it and when
  (before each RC's commit; the human's edits after the last RC need no new RC, section 6
  names the exception), what goes in it (each item of CHANGELOG.md's `(unreleased)`
  section with what covers it and what is tried by hand; steps the automatic tests do not
  cover; an earlier version's check again only when the release touches it), its
  language (English).
- [ ] 3.4 Section 6 ("What the workflow refuses"): the final may differ from its last RC in
  CHANGELOG.md, `docs/releases/X.Y.Z.md`, pyproject.toml and uv.lock.
- [ ] 3.5 Check: `uv run python scripts/rc_check.py --help` still runs; every command named
  in docs/release.md exists (`--help` of `rc_check.py` and the `lado` commands named).

## 4. docs/releases/0.45.0.md (D2)

- [ ] 4.1 The file by D2, in English: section `## 0.45.0rc1` made from the session artifact
  `release-checklist-0.45.0rc1`, without what docs/release.md's every-RC checks now hold
  (they are named once at the top), with the version's items moved out of docs/release.md
  (projects with each CLI and in the web UI, secrets in three browsers and on the Mac,
  models, Settings in Safari and Firefox and on a phone, the New session window, the
  folder of documents, real phone and tablet, stop with an open question, Codex and a model
  server in the container, the resume of a kept model after the image's update, the model
  servers lost on going back, the Codex shared login's live test), and its block of the
  48 CHANGELOG items with what covers each. No `## 0.45.0rc2` yet (out of scope).
- [ ] 4.2 `tests/test_telemetry.py::test_release_checks_in_a_fresh_home_send_nothing`
  reads `docs/releases/*.md` beside docs/release.md (D7); it passes.

## 5. The documents that describe the scripts

- [ ] 5.1 docs/design/modules.md: `rc_check.py`'s line (its list from docs/release.md and
  `docs/releases/X.Y.Z.md`, no longer CHANGELOG items), `release_check.py`'s line (the
  final's checklist free). docs/telemetry.md unchanged unless it names the list.
- [ ] 5.2 No CHANGELOG.md line (rule 6). `make lint`, `make test`,
  `openspec validate release-checklists --strict` and the trial archive of `.lado/sdlc.md`
  pass.
