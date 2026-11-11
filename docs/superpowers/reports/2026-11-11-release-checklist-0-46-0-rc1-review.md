# LAD-269 release-checklist-0-46-0-rc1: review report

Pull request #281 `fix/lad-269-release-checklist-0-46-0-rc1` → `main`. Scale: tweak, depth
precision. Head reviewed: `c3877fea`. The release's checklist `docs/releases/0.46.0.md` with its
section `## 0.46.0rc1` (manual checks of the 8 CHANGELOG items and what covers each), and the
real-file test of `tests/test_rc_check.py` extended to `0.46.0rc1`. No delta (`--skip-specs`);
no code, version or CHANGELOG change. The RC's commit and tag follow the merge, each push with
the human's yes.

## Rounds

1. Local, precision. The checklist equals the approved proposal's text byte for byte; every
   exact line checked against the code (`Launch.tsx`, `LaunchWhere.tsx`, `LaunchTeam.tsx`,
   `Recommendation.tsx`, `doctor.py`, `state.py`, `runtime.py`, `docs/cli.md`); all 21 named
   test files exist; the 8 items match `## 0.46.0 (unreleased)`; `SCHEMA_VERSION` 39 at
   `v0.45.0` and on main. The test can fail (a missing file raises, a warning fails the
   assert). Every task of `tasks.md` checked. No findings.
2. External 1, Claude Code GitHub Action: no blockers; three nits F1–F3, all refuted. It did
   not read `proposal.md` and `.openspec.yaml`; the local round did.

External rounds used: 1 of 1. Stand-ins: 0.

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| F1 | nit | external: the folded list's tooltip reads "title, name and state" in the checklist, "name and state" in CHANGELOG | refuted: the checklist follows the code (`web/src/Sessions.tsx:530`); CHANGELOG is out of scope |
| F2 | nit | external: the `<filled in at the RC>` placeholders could be refused at the RC step | refuted: intended (design decision 2), filled in with the RC as for 0.45.0rc1; `rc_check.py` out of scope |
| F3 | nit | external: `Use <name>-2` is a hint, not a fixed line | refuted: `Launch.tsx` renders `Use ${next}`, which is `<name>-2` when free; `<name>` is a placeholder |

## Found on the way

None. (F1's CHANGELOG wording may be touched up at the final.)

## Checks

On `c3877fea`:
- `make lint` green; `uv run pytest -n0 tests/test_rc_check.py` 80 passed; `openspec validate
  release-checklist-0-46-0-rc1 --strict` valid.
- CI: every job green, `ci-ok` and the smoke included; `mergeStateStatus` CLEAN.

Not run: `scripts/rc_check.py` as a whole (it installs from PyPI; the test covers its list),
`live.yml` (it runs on the RC's commit), the checklist's manual checks (the human's, at the RC).
