## Context

A release is `uv version X.Y.Z`, a commit on main, CI, the Windows probe and
`make test-live` on that commit, then the tag `vX.Y.Z`; the Release workflow
(`.github/workflows/release.yml`) checks the tag against the package's version, runs
`make dist` and `uv publish`. Nothing in it is a pre-release step: the first build anyone
installs from PyPI is the one every user is offered.

LADO already reads PEP 440 pre-releases (`update._key`, `update.prerelease`): `update.latest`
skips them, so the daily check (`update.check`), `lado update` without a version
(`cli._update`) and the UI's plan (`self_update.latest_plan`) never offer one, and
`update.release` finds a named one for `lado update X.Y.ZrcN`. A tag `v0.37.0rc1` with
version `0.37.0rc1` passes today's workflow. What is missing: a process, a guard that the
final is what was tested, and a tester on an RC learns of no newer RC (`latest` is the
newest final, older than the RC).

Root cause: a release has only its final form, so a person can try only the build every
user gets at the same time.

## Options

1. **PEP 440 RCs on PyPI, final = last RC's code** (chosen with the human): the same
   workflow publishes `X.Y.ZrcN`; installers and LADO's own update skip it unless its version
   is named. Long-term cost: one stdlib script and a workflow step, a rule in `update.py`,
   two API booleans and a pill; a freeze of main while an RC is tested; the RC shows in
   PyPI's release history.
2. **RCs on TestPyPI**: invisible on PyPI, but another trusted publisher, an
   `--extra-index-url` for dependencies, and `lado update` (PyPI's JSON) cannot install
   it, so the update path, the riskiest part, goes untested. Rejected.
3. **A wheel on a GitHub release or `uv tool install git+…@tag`**: `update.installer`
   reads such an install as not from an index (`None`): no `lado update` from or to it.
   Rejected.

Held against AGENTS.md's Design principles: *One source of truth*: whether a version is a
pre-release is `update.prerelease`, the one parser; the UI gets it as booleans in
`UpdateInfo`, never by parsing a version in TypeScript. *No silent drops*: a final tag
the workflow refuses names why and publishes nothing. *Only what is used*: no beta channel,
no flag; the only new offer is to the install that already runs a pre-release, the
human's own. *Neutral core*: no provider is involved. ROADMAP: later stages (Projects, the
desktop app) read the same `UpdateInfo`.

## Decisions

- **D1. What is offered depends on this LADO's kind.** `update.offered(data, current)`
  is `latest(data, pre=prerelease(current))`; `latest(data, pre=True)` takes the newest
  release of all, pre-releases included. `check`, `cli._update` (no version) and
  `self_update.latest_plan` call `offered`. Any newer pre-release is offered to a
  pre-release, also one of a later X.Y.Z (0.38.0rc1 to a 0.37.0rc2): only a tester runs
  one, and the simple rule is enough; once on a final, the tester is offered finals only.
- **D2. The cache keeps its kind.** `update-check.json` gets `"pre": true|false`, written
  with each look; `check` treats a cache whose `pre` differs from
  `prerelease(lado.__version__)` (a missing key is `false`) as stale and looks again at
  once. `Check` keeps no new field: `available` still compares with `current`.
- **D3. The mark comes from the server.** `UpdateInfo.prerelease = update.prerelease(current)`,
  `UpdateInfo.available_prerelease = available is not None and prerelease(available)`.
  `doctor.check_lado` and `doctor.report` print `X.Y.ZrcN (pre-release)` through one
  helper, `update.shown(version)`. `web/openapi.json` and `web/src/api.gen.ts` are made
  again (`make web-types`).
- **D4. The pill** is the existing `.pill.dim` (grey, `white-space: nowrap` added so it
  does not break), beside `LADO <version>` in `.system-head` and after the date in the
  Update block's row; the top bar's `↑ X` mark is unchanged. Mockup
  `mockup-prerelease.html`, approved.
- **D5. The workflow's check is a script.** `scripts/release_check.py <tag>`, standard
  library, runs git: a tag that is no `vX.Y.Z` final passes; a final looks up
  `git tag --list 'vX.Y.Zrc*'` and takes the highest N numerically (rc10 after rc2); none
  and Z == 0 fails; one is compared by `git diff --name-only <rc> <tag>` and `git diff -U0
  <rc> <tag> -- pyproject.toml uv.lock` (each `+`/`-` line, headers aside, must match
  `^[+-]version = "[^"]*"$`; in uv.lock only the line in the `[[package]]` block named
  `lado`, found by the hunk's line numbers in each side's file, so a dependency bumped
  between the RC and the final is refused: the human's addition after design_ok). It
  prints one line per problem and exits 1. The workflow checks out with `fetch-depth: 0`
  (tags and history) and runs it after the version check, before `make dist`. Tested by
  `tests/test_release_check.py` on a temporary git repo.
- **D6. Only X.Y.0 needs an RC.** Patches may have one (then the diff rule holds); a patch
  without one passes, as the human chose "at the human's choice" for patches.
- **D7. No override.** A final the check refuses is fixed by a new RC; no workflow input
  bypasses it (only what is used).
- **D8. The kit's `lado:` need** compares `X.Y.Z` only (`kits._version`): `0.37.0rc1`
  meets `>=0.37`, so an RC can be tried with the kits that need its release. Left as is.
- **D9. The freeze of main** (human's 7a) is written in `docs/release.md` and AGENTS.md's
  Release paragraph; nothing in LADO or the kit enforces it; D5 catches a final with code
  the RC did not have.
- **D10. CHANGELOG.md** keeps `## X.Y.Z (unreleased)` through the RCs; the final's
  commit dates it. An RC adds no heading.
- **D11. Tests.** Unit: `test_update.py` (D1, D2), `test_cli.py` (`lado update` without a
  version on both kinds), `test_doctor.py` (D3 lines), `test_server_system.py`
  (`UpdateInfo` booleans), `test_release_check.py` (D5, D6), vitest
  `SystemPanel.test.tsx` (D4). UI e2e: `tests/ui/test_system_panel.py`, a stable server
  with only a newer RC in the index shows no `↑` and no Update block. No integration test:
  nothing crosses processes beyond what the update tests already cover.

## Risks / Trade-offs

- The RC is visible on PyPI's history page and `pip install --pre lado` takes it: the human
  accepted it (question 1).
- The freeze relies on the human at merge approval; a merge by mistake costs a new RC, not
  a bad release (D5).
- A diff rule by file names: a CHANGELOG change during the final is free text; the final's
  commit is reviewed as any release commit.
- `pyproject.toml`'s `version` line rule would also pass a `version = ` line of another
  table: none exists in this repo's pyproject.toml.
