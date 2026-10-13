Plan: `docs/superpowers/plans/2026-10-13-release-candidates.md` (each task's tests and
steps). Design doc: `docs/superpowers/specs/2026-10-13-release-candidates-design.md`.

## 1. The offer (D1, D2)

- [ ] 1.1 `update.latest(data, pre=False)`, `update.offered(data, current)`,
  `update.shown(version)`; `check` with the cache's `pre` key. Check:
  `uv run pytest tests/test_update.py -n auto`.
- [ ] 1.2 `cli._update` and `self_update.latest_plan` call `offered`. Check:
  `uv run pytest tests/test_cli.py tests/test_self_update.py -n auto -k update`.

## 2. The marks (D3, D4)

- [ ] 2.1 `doctor.check_lado` and `doctor.report` through `update.shown`. Check:
  `uv run pytest tests/test_doctor.py -n auto`.
- [ ] 2.2 `UpdateInfo.prerelease`, `UpdateInfo.available_prerelease`; `make web-types`.
  Check: `uv run pytest tests/test_server_system.py tests/test_server.py -n auto -k update`.
- [ ] 2.3 `SystemPanel.tsx`: the pills; `.pill` nowrap. Check: `make web`
  (`SystemPanel.test.tsx`).
- [ ] 2.4 UI e2e: a stable server is not offered a newer RC. Check:
  `uv run pytest -m ui tests/ui/test_system_panel.py`; the screenshot in `build-report`.

## 3. The release check (D5, D6, D7)

- [ ] 3.1 `scripts/release_check.py`. Check: `uv run pytest tests/test_release_check.py -n0`.
- [ ] 3.2 `.github/workflows/release.yml`: `fetch-depth: 0`, the check before `make dist`.
  Check: `tests/test_ci_workflow.py` or a new assertion that the step runs before
  `make dist`; `make lint`.

## 4. Docs (D9, D10)

- [ ] 4.1 `docs/release.md`: the process and the RC checklist. AGENTS.md: Release, "Before a
  release", `update.py` in Layout (`offered`, the cache's kind). `docs/design/ui.md`: System
  panel. CHANGELOG.md under 0.37.0. Check: read against the design doc.

## 5. Regression

- [ ] 5.1 `make lint`, `make test`, `make web`, `uv run pytest -m ui tests/ui/test_system_panel.py`,
  `openspec validate --specs --strict`. Check: all green, counts in `build-report`.
