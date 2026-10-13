# Release candidates: implementation plan

**Goal:** a minor LADO release is first published to PyPI as a release candidate
`X.Y.0rcN` that the human tests by hand; users are never offered one; a LADO running an RC
is offered newer RCs and the final and says it is a pre-release; the Release workflow
refuses a final whose code is not its last RC's (LAD-31).

**Architecture:** `update.offered(data, current)` picks the newest final release, or for a
pre-release install the newest of all; `check`'s cache records which kind it looked for.
`update.shown` gives `X.Y.ZrcN (pre-release)` to `lado doctor` and the system report;
`UpdateInfo.prerelease` / `available_prerelease` drive two pills in the System panel.
`scripts/release_check.py` runs in the Release workflow before `make dist`.
`docs/release.md` holds the process and the manual checklist.

**Tech stack:** Python 3.10+ (stdlib, FastAPI, pydantic), React + TypeScript (vitest),
pytest (unit, UI with Playwright), GitHub Actions.

**Spec:** `openspec/changes/release-candidates/` (proposal, delta `release-candidates`,
`design.md` D1–D11). **Design doc:**
`docs/superpowers/specs/2026-10-13-release-candidates-design.md`. **Mockup:** run artifact
`task/lad-31/mockup-prerelease.html` (approved).

Each task: tests first, then the code, then the named test run, then a commit (message in
the repository's style, `(LAD-31)` at the end).

## Global constraints

- Texts, exactly: `(pre-release)` after a version (`update.shown`); the check's failures
  `vX.Y.0 needs a release candidate: tag vX.Y.0rc1 first`, `vX.Y.Z differs from
  vX.Y.ZrcN in <path>` (one line per file), `vX.Y.Z changes a line of <path> that is not
  its version: <line>`; the UI pill's text `pre-release`.
- The tag of an RC is `vX.Y.ZrcN` (PEP 440 normalized, the form `uv version --short`
  prints); `scripts/release_check.py` reads finals as `^v(\d+)\.(\d+)\.(\d+)$` and RCs as
  `^v<X.Y.Z>rc(\d+)$`; any other tag passes untouched.
- Tests fake this LADO's version with `monkeypatch.setattr(lado, "__version__", "0.37.0rc1",
  raising=False)` (the attribute is lazy) and PyPI with the `published` fixture.
- No schema change, no MCP change.

## Task 1: the offer (`src/lado/update.py`)

Tests (`tests/test_update.py`):
- `latest(data)` skips pre-releases (exists); `latest(data, pre=True)` returns the newest
  of all, a yanked RC skipped.
- `offered`: 0.36.0 with {0.36.0, 0.37.0rc1} → 0.36.0; 0.36.0 with {0.37.0rc1, 0.37.0}
  → 0.37.0; 0.37.0rc1 with {0.36.0, 0.37.0rc1, 0.37.0rc2} → 0.37.0rc2; 0.37.0rc2 with
  {0.37.0rc2, 0.37.0} → 0.37.0.
- `check` writes `"pre"`; a fresh cache with `"pre": true` read by a final release looks
  again (the index is read: count the `published` reads or change the index between the
  calls); a cache without the key is `false`; a fresh cache of the same kind is not looked
  at again (exists, keep).
- `shown("0.37.0rc1") == "0.37.0rc1 (pre-release)"`, `shown("0.36.0") == "0.36.0"`.

Code: `latest(data, pre=False)`; `offered(data, current) = latest(data,
pre=prerelease(current))`; `shown`; in `check`, `stale = not cached or force or age >=
CHECK_EVERY or cached.get("pre", False) != prerelease(lado.__version__)`, the look calls
`offered`, `_write_cache` writes `pre`. Run: `uv run pytest tests/test_update.py -n auto`.

## Task 2: `lado update` and the UI's plan

Tests: `tests/test_update.py` / `tests/test_cli.py` (where `lado update`'s tests are):
0.36.0 with a newer RC only prints `LADO 0.36.0 is the latest version.`; 0.37.0rc1 with
rc2 out plans `LADO 0.37.0rc1 -> 0.37.0rc2`. `tests/test_self_update.py`: `latest_plan`
on 0.37.0rc1 with rc2 gives a plan to rc2, on 0.36.0 with an RC only gives None.

Code: `cli._update` (no version) and `self_update.latest_plan` call `update.offered(index,
lado.__version__)`. Run: `uv run pytest tests/test_update.py tests/test_cli.py
tests/test_self_update.py -n auto -k update`.

## Task 3: the doctor and the system report

Tests (`tests/test_doctor.py`): on 0.37.0rc2 with nothing newer, `check_lado` is OK with
`0.37.0rc2 (pre-release), the latest version`; with 0.37.0 out, WARN with detail
`0.37.0rc2 (pre-release)` and the hint `LADO 0.37.0 is available: lado update`; with the
check off, `0.37.0rc2 (pre-release) (no update check: …)`; `report`'s LADO line names
`(pre-release)`; on a final release nothing changes.

Code: `doctor.check_lado` and `doctor.report` use `update.shown(lado.__version__)`. Run:
`uv run pytest tests/test_doctor.py -n auto`.

## Task 4: the API

Tests (`tests/test_server_system.py`, where `/api/update` is tested): `prerelease` and
`available_prerelease` for 0.36.0 (false, false), 0.37.0rc1 with rc2 (true, true),
0.37.0rc2 with 0.37.0 (true, false).

Code: `UpdateInfo.prerelease: bool`, `UpdateInfo.available_prerelease: bool` (comments as
the model's others), set in `app.update_state`; `make web-types`, commit
`web/openapi.json` and `web/src/api.gen.ts`. Run: `uv run pytest
tests/test_server_system.py -n auto -k update`, then `make web`.

## Task 5: the System panel

Tests (`web/src/SystemPanel.test.tsx`, `fetch` mocked): with `prerelease: true` the head
has a `pre-release` pill beside `LADO 0.37.0rc1`; with `available: "0.37.0rc2",
available_prerelease: true` the Update region has `0.37.0rc2 is out` and a pill; with
`available: "0.37.0", available_prerelease: false` it has none; a final release has no pill
anywhere.

Code: `SystemPanel.tsx`: `<span className="pill dim">pre-release</span>` after the
version's `<strong>` in `.system-head` (when `info?.prerelease`) and after the released
date in `UpdateBlock` (when `info.available_prerelease`), as in the mockup;
`styles.css`: `.pill { white-space: nowrap }` and a small left margin in the head.
`docs/design/ui.md`, System panel: one sentence on the pills. Run: `make web`.

UI e2e (`tests/ui/test_system_panel.py`): `published(**{"99.0.0rc1": "2026-10-04"})`
before the first look: `live` reads `live` with no `↑`, the panel has no Update region;
`shot(page)`. Run: `uv run pytest -m ui tests/ui/test_system_panel.py`. The screenshot goes
in `build-report`; the RC side cannot run in e2e (the server is the working copy's
version): say so there.

## Task 6: the release check

Tests (`tests/test_release_check.py`, a temporary git repo with a pyproject.toml,
uv.lock, CHANGELOG.md and `src/x.py`, tags made by the test; the script run as
`python scripts/release_check.py <tag>` with `cwd` the repo, or its `main(argv)`):
- `v0.37.0rc1` passes (an RC);
- `v0.37.0` after `v0.37.0rc1` with only the version lines and CHANGELOG changed passes;
- the same plus `src/x.py` fails naming `src/x.py`;
- a pyproject change of another line fails naming the line;
- `v0.38.0` with no RC tag fails with the exact text;
- `v0.37.1` with no RC passes; `v0.37.1` after `v0.37.1rc1` with a code change fails;
- with `v0.37.0rc2` and `v0.37.0rc10`, rc10 is the one compared;
- a tag that is no version (`v1`, `nightly`) passes.

Code: `scripts/release_check.py` (stdlib; `subprocess.run(["git", …], check=True)`), one
line per problem on stderr, exit 1 on any. `.github/workflows/release.yml`:
`actions/checkout` with `fetch-depth: 0`, a step `Check a final release is its last
release candidate` running `python3 scripts/release_check.py "$GITHUB_REF_NAME"` after
the version check and before `make dist`. A test (in `tests/test_ci_workflow.py` or a new
`tests/test_release_workflow.py`, reading the YAML as the existing one does) asserts the
step's place and the checkout's depth. Run: `uv run pytest tests/test_release_check.py
tests/test_ci_workflow.py -n0`.

## Task 7: docs

`docs/release.md` from the design doc's outline (items 1–6). AGENTS.md: the Release
paragraph points to `docs/release.md` and says, in its words: RC first for X.Y.0, the
heavy checks on the RC, the freeze of main, the final tag checked by
`scripts/release_check.py`; "Before a release" says where the Windows probe and the live
tests run; Layout's `update.py` names `offered` and the cache's kind; `scripts/` lists
`release_check.py`. CHANGELOG.md under `## 0.37.0 (unreleased)`: a LADO on a release
candidate is offered the next one and the release, and says it is a pre-release
(`lado doctor`, the System panel); a final release is never offered one; API
`UpdateInfo.prerelease`, `available_prerelease`. Check: read each against the design doc;
`openspec validate release-candidates --strict`.

## Task 8: regression

`make lint`, `make test`, `make web`, `uv run pytest -m ui tests/ui/test_system_panel.py`,
`openspec validate --specs --strict`, each to a log outside the tree with its exit status
read. Counts in `build-report`.
