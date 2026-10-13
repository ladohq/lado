Task: LAD-31

## Why

LADO is going public, and a broken release now costs its users: an update stops their
sessions, may migrate their lado.db, and an older LADO refuses a migrated database. Today a
release is tested only by machines (CI, the smoke, the Windows probe, `make test-live`) on
the release commit itself, then published at once; nobody uses the build PyPI serves before
the users get it.

Root cause: a release has one form, the final version, so the only build a person could try
by hand is already the one every user is offered.

## What Changes

- **Release candidates on PyPI**: a minor release (X.Y.0: features, MCP or CLI changes,
  schema migrations) is first published as a PEP 440 pre-release `X.Y.0rcN` by the same
  tag-driven Release workflow (`vX.Y.0rcN`); a patch release may have one at the human's
  choice. Heavy checks (the Windows probe, `make test-live`) run on the RC's commit. The
  human installs the RC (`lado update X.Y.0rcN`) and works with it, following the checklist
  in a new `docs/release.md`; their "ok" releases the final.
- **Users are not offered an RC**: a LADO that runs a final release is offered final
  releases only (`lado update`, the daily check, `lado ls`, `lado doctor`, the UI's System
  panel), as today; `pip install lado` and `uv tool install lado` take none by PEP 440.
  An RC is installed only when its version is named.
- **A LADO that runs a pre-release is offered the newer pre-releases too**: the tester on
  rc1 sees rc2 or the final in `lado update`, the daily check, `lado ls`, `lado doctor` and
  the System panel; after the final it is a final release again and is offered final
  releases only. The update check's cache records which kind it looked for.
- **A pre-release says so**: `lado doctor` prints `LADO: X.Y.ZrcN (pre-release)`, the
  System panel shows a grey `pre-release` pill beside the version in its head and beside an
  offered pre-release in its Update block (mockup `mockup-prerelease.html`, approved).
  API: `UpdateInfo.prerelease` and `UpdateInfo.available_prerelease`.
- **The final is the last RC's code**: the Release workflow refuses a final tag `vX.Y.0`
  without an RC tag `vX.Y.0rcN`, and any final tag whose commit differs from its latest RC
  tag's commit in more than CHANGELOG.md, the `version = "…"` line of `pyproject.toml` and
  that of the `lado` package in `uv.lock` (`scripts/release_check.py`). A fix during the RC is a new RC.
- **main is frozen while an RC is tested**: only fixes for that RC are merged until the
  final is tagged; a convention the human keeps at merge approval, with the workflow's
  check as the safety net.
- **Docs**: `docs/release.md` (the process and the RC checklist), AGENTS.md's Release and
  "Before a release" paragraphs, `docs/design/ui.md` (System panel), CHANGELOG.md.

## Scope

In: the release process with RCs (docs), the Release workflow's check of a final tag, the
update offer by the running LADO's kind, the pre-release marks in `lado doctor`, the system
report and the System panel.

## Out of scope

- **A release flow in a kit** (RC → checks → human gate → final): the human asked; the
  process is LADO's own facts (PyPI, schema, providers), one project releases this way, and
  kit sdlc's blueprint already plans a release hand-off flow for v2: a later task there.
- **TestPyPI or GitHub-only builds for RCs**: rejected with the human; they cannot test
  `lado update` and the real publishing.
- **GitHub Releases**: LADO publishes none today; "What's new" links the tag's page.
- **A `release/X.Y` branch**: rejected with the human for a freeze of main (7a).
- **A beta channel users opt into** (e.g. `lado update --pre`): no user asked; a tester
  names the RC's version once.
- **An automatic end-to-end run of the published RC**: the existing automated checks run on
  the RC's commit; the RC's point is a person's use.
- **A UI e2e test of the pill**: the test server always runs the working copy's version;
  the pill is covered by the component's unit test (vitest).
- **Enforcing the freeze of main** in the integrator or a branch rule: kit sdlc's concern;
  the workflow's check catches a final with code not in the RC.

## Impact

- Code: `src/lado/update.py`, `src/lado/cli.py` (`_update`), `src/lado/self_update.py`
  (`latest_plan`), `src/lado/doctor.py`, `src/lado/server/models.py` and `app.py`
  (`UpdateInfo`), `web/src/SystemPanel.tsx`, `web/openapi.json`, `web/src/api.gen.ts`,
  `scripts/release_check.py`, `.github/workflows/release.yml`.
- Tests: `tests/test_update.py`, `tests/test_cli.py`, `tests/test_doctor.py`,
  `tests/test_server_system.py`, `tests/test_release_check.py`,
  `web/src/SystemPanel.test.tsx`, `tests/ui/test_system_panel.py`.
- Docs: `docs/release.md` (new), AGENTS.md, `docs/design/ui.md`, CHANGELOG.md.
- No schema change, no MCP change. Version: minor (new API fields), in 0.37.0.
