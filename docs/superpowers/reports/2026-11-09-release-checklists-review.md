# LAD-253 release-checklists: review report

Pull request #266 `fix/lad-253-release-checklists` → `main`. Scale: tweak, depth precision. Head
reviewed: `6a8ef5f9`. docs/release.md keeps the release's order and the checks of every RC; each
version's own checks move to `docs/releases/X.Y.Z.md`, one section per RC, starting with
`docs/releases/0.45.0.md`. `scripts/rc_check.py` prints docs/release.md's every-RC list, then the
RC's own section; `scripts/release_check.py` lets a final differ from its last RC in its own
checklist. Delta: changes to `release-candidates`.

## Rounds

1. Local, precision, `origin/main...6a8ef5f9`: the scripts, their tests, docs/release.md,
   docs/releases/0.45.0.md and docs/design/modules.md against the spec, tasks 1.1-5.2 and
   decisions D1-D8; a trial archive. Found F1.
2. External 1, Claude Code GitHub Action: no blockers; E1-E5. It did not read
   docs/releases/0.45.0.md in full nor the text of 4.1-4.6 in docs/release.md; those were read
   locally.

External rounds used: 1 of 1. Stand-ins: 0.

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| F1 | minor | two paragraphs of docs/release.md not wrapped to the file's width (97 and 137 characters) | declined: no effect on behaviour |
| E1 | minor | external: `rc_check.py`'s parse does not skip fenced code | declined: no such input today; details are nested lines by 4.7's form |
| E2 | minor | external: the RC's section heading is matched exactly; a trailing space gives "no section" | declined: the result is a loud warning (D4) |
| E3 | — | external: without docs/release.md the checklist is one warning and nothing else | refuted: the scenario "Not the repository's root" asks for it |
| E4 | minor | external: a test is bound to docs/releases/0.45.0.md | declined: the file stays as the release's record; task 2.1 asks for the test |
| E5 | minor | external: the every-RC list is not checked against the headings 4.1-4.6 | declined: the list is the one source `rc_check.py` reads (D1) |

## Checks

`make lint` green; the touched tests 107 passed; `openspec validate release-checklists --strict`
valid and the trial archive 82 passed; `rc_check.checklist` of 0.45.0rc1 gives 6 every-RC checks
and 56 items of 0.45.0 without a warning; CI on `6a8ef5f9`: `ci-ok` green.

Not run: `rc_check.py sandbox` and `upgrade` as a whole (they install from PyPI and touch the
human's LADO); the human runs them on 0.45.0rc2.

## Found on the way

Nothing.
