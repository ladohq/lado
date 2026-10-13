# Release candidates: design

Task: LAD-31. Change: `openspec/changes/release-candidates/`. Mockup: run artifact
`task/lad-31/mockup-prerelease.html` (approved).

## Problem

LADO is going public; a broken release stops users' sessions, may migrate their lado.db,
and an older LADO refuses a migrated database. Every check of a release today is a
machine's, on the release commit, and the build PyPI serves is first used by everyone at
once. Root cause: a release has only its final form.

## What the maintainer and the users see after the change

**Releasing a minor version (X.Y.0)**

1. `uv version X.Y.0rc1`, commit `Release candidate X.Y.0rc1` on main, push. CI green on
   it, the Windows probe green, `make test-live` for every provider (Claude Code with the
   human's yes). Tag `vX.Y.0rc1`: the Release workflow publishes `X.Y.0rc1` to PyPI as a
   pre-release.
2. main is frozen: only fixes for this RC are merged until the final is tagged.
3. The human installs it on their own LADO, `lado update X.Y.0rc1`, and works with it by
   `docs/release.md`'s checklist. A fix is merged to main and released as `rc2` the same way
   (step 1 again); the human's LADO shows `rc2` as available.
4. On the human's "ok": `uv version X.Y.0`, CHANGELOG's heading dated, commit `Release
   X.Y.0`, CI green, tag `vX.Y.0`. The workflow checks that the commit differs from the last
   RC's only in CHANGELOG.md and the version lines, then publishes. The Windows probe and the
   live tests are not run again: the code is the RC's.
5. A patch (X.Y.Z, Z > 0) may go the same way at the human's choice, or directly as today.

**A user on a final release** sees no change: `lado update`, the daily check, `lado ls`,
`lado doctor` and the System panel offer final releases only; `pip install lado` and
`uv tool install lado` take none.

**The tester on an RC**

- `lado doctor`: `[ok  ] LADO: 0.37.0rc2 (pre-release), the latest version`, or `[warn]`
  with `LADO 0.37.0 is available: lado update`.
- `lado ls` ends with `LADO 0.37.0rc2 is available: lado update` when rc2 is out.
- System panel: a grey `pre-release` pill beside `LADO 0.37.0rc1` in the head; the Update
  block `0.37.0rc2 is out · 14 Oct · pre-release` with **Update…**; the final offered
  without a pill. After updating to the final, the install is a final release again.

## `docs/release.md` (new; the developer writes it from this outline)

1. **When an RC is needed**: every X.Y.0; a patch at the human's choice.
2. **The RC**: the steps of item 1 above, the commit message `Release candidate X.Y.ZrcN`,
   the tag `vX.Y.ZrcN` (PEP 440, no dash: `uv version` and the tag check need the same
   spelling), CHANGELOG untouched.
3. **The freeze**: only fixes for the RC are merged to main until the final; another merge
   makes the final impossible (the workflow's check) and needs a new RC from main.
4. **Manual checklist** (the human, on the RC):
   - a clean install in a separate home: `LADO_HOME=$(mktemp -d) LADO_TMUX_SOCKET=lado-rc
     uvx --from lado==X.Y.ZrcN lado doctor`, then `lado start` of a scratch repo there and
     `lado stop`;
   - the upgrade of the human's own LADO from the last final with a session running:
     `lado update X.Y.ZrcN` (the migration when the schema moved, the sessions resumed, the
     UI server back; `update.log` read);
   - a session with the sdlc kit through one run to its first gate, answered in the UI;
   - the UI: the chat, a gate's card, the System panel with its `pre-release` pill;
   - each line of CHANGELOG's `X.Y.Z (unreleased)` tried once;
   - going back if needed: `lado update <last final>`; when the schema moved, the backup
     `~/.lado/backups/lado.db.<last final>` is restored by hand after `lado stop --all`.
   No fixed soak time: the final follows the human's "ok".
5. **The final**: item 4 above, and that the Windows probe and the live tests ran on the
   RC's commit.
6. **What the workflow refuses** (`scripts/release_check.py`) and how to get round it: a
   new RC.

## Architecture

- `src/lado/update.py`: `latest(data, pre=False)`, `offered(data, current)`,
  `shown(version)`, the cache's `pre` key in `check`.
- `src/lado/cli.py` `_update`, `src/lado/self_update.py` `latest_plan`: `offered`.
- `src/lado/doctor.py`: `check_lado`, `report` with `shown`.
- `src/lado/server/models.py` `UpdateInfo.prerelease`, `available_prerelease`;
  `src/lado/server/app.py` `update_state`; `web/openapi.json`, `web/src/api.gen.ts`.
- `web/src/SystemPanel.tsx`, `web/src/styles.css` (`.pill` nowrap).
- `scripts/release_check.py`, `.github/workflows/release.yml`.
- `docs/release.md`, AGENTS.md (Release, Before a release, Layout's `update.py`),
  `docs/design/ui.md` (System panel), CHANGELOG.md.

## Choices and their long-term cost

| Choice | Taken | Cost |
|---|---|---|
| Where RCs go | PyPI pre-release | visible in PyPI's history; tests the real path |
| TestPyPI | no | no `lado update` test, a second publisher |
| GitHub-only wheel | no | not updatable by `lado update` |
| main during an RC | frozen (7a) | merges wait hours to a day |
| `release/X.Y` branch | no | cherry-picks, two CHANGELOGs |
| Final = RC's code | workflow check | a script and `fetch-depth: 0` |
| Offer to a tester | by the running LADO's kind | one rule, one cache key |
| A kit flow for releases | later, kit sdlc v2 | none now |

## Testing

| Requirement | Layer | Tests |
|---|---|---|
| A final release offers only final releases | unit + UI e2e | `test_update.py` (`offered`, `check`), `test_cli.py` (`lado update` prints the latest), `tests/ui/test_system_panel.py` (a newer RC only: no `↑`, no Update block) |
| A pre-release is offered newer pre-releases | unit | `test_update.py` (rc1 → rc2, rc2 → final, the cache's kind stale after a move), `test_cli.py`, `test_self_update.py` (`latest_plan`) with `lado.__version__` patched |
| A pre-release says so | unit + vitest | `test_doctor.py`, `test_server_system.py`, `SystemPanel.test.tsx` (head pill, offer pill, none on a final) |
| A final release is the code of its last RC | unit | `test_release_check.py` on a temporary git repo: final after RC passes, a code file fails, a non-version pyproject line fails, X.Y.0 without RC fails, a patch without RC passes, rc10 beats rc2, an RC tag passes; `test_ci_workflow.py`-style assertion that release.yml runs the check with full history before `make dist` |

No integration test: nothing new crosses processes. Regression: `make lint`, `make test`,
`make web`, the UI test file with `-m ui`, `openspec validate --specs --strict`.

## Version

Minor: new API fields (`UpdateInfo`), released in 0.37.0 (already unreleased on main).
