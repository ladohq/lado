Plan: `docs/superpowers/plans/2026-10-14-bug-report.md` (each task's tests and steps).
Design doc: `docs/superpowers/specs/2026-10-14-bug-report-design.md`.

## 1. Error journal (D2)

- [x] 1.1 `telemetry._journal` writes `chain`, `stack`, `fingerprint` and `provider`;
  `record` scrubs once. Check: `uv run pytest tests/test_telemetry.py -n auto`, `uv run
  pytest -m integration -n auto tests/integration/test_telemetry_processes.py`.

## 2. System info (D6)

- [x] 2.1 `doctor.ServerState`, `doctor.report(system, server)` with the `not running` and
  `running` lines; `/api/system` unchanged. Check: `uv run pytest tests/test_doctor.py
  tests/test_server_system.py -n auto`.

## 3. Report and link (D1, D3, D4)

- [x] 3.1 `bug_report.py`: `errors`, `kinds`, `build`, the 8000-character bound, the
  privacy test. Check: `uv run pytest tests/test_bug_report.py tests/test_lazy_imports.py
  -n auto`.

## 4. CLI (D7, D9)

- [x] 4.1 `lado bug-report`, `can_show_browser`, no migration; `BROWSER=true` in
  `tests/conftest.py` with its guard. Check: `uv run pytest tests/test_cli_bug_report.py
  tests/test_cli.py -n auto`.

## 5. API (D5)

- [x] 5.1 `GET /api/bug-report` (`BugReport`, the browser line's check); `make web-types`,
  both files committed. Check: `uv run pytest tests/test_server_bug_report.py -n auto`,
  `make web`.

## 6. UI (D8)

- [x] 6.1 `BugIcon`, the rail's Report a bug above Settings, route `/report`,
  `ReportBug.tsx` to the mockup's variant A; vitest. Check: `make web`.
- [ ] 6.2 UI e2e `tests/ui/test_bug_report.py` with screenshots. Check: `uv run pytest -m
  ui tests/ui/test_bug_report.py`.

## 7. Docs (D11)

- [ ] 7.1 AGENTS.md, `docs/design/ui.md`, `docs/telemetry.md`, README, CHANGELOG.md
  (`## 0.38.0 (unreleased)`). Check: `make lint`.

## 8. Regression

- [ ] 8.1 `make lint`, `make test`, the integration file of 1.1, `uv run pytest -m ui
  tests/ui/test_bug_report.py tests/ui/test_system_panel.py tests/ui/test_layout.py`,
  `make web`, `openspec validate bug-report --strict`, `openspec validate --specs
  --strict`.
