Plan: `docs/superpowers/plans/2026-10-13-usage-telemetry.md` (each task's tests and
steps). Design doc: `docs/superpowers/specs/2026-10-13-usage-telemetry-design.md`.

## 1. Core (D1–D6)

- [x] 1.1 `telemetry.py`: `State`, `state`, `choose`, `clear`, `FIELDS`, `record`,
  `bounded_append`, `scrub`, the outbox and its drop count; `LADO_TELEMETRY=0` and the
  `telemetry_on` fixture in `tests/conftest.py`; the lazy-import check. Check:
  `uv run pytest tests/test_telemetry.py tests/test_lazy_imports.py -n auto`.

## 2. Capture points and log bounds (D3, D12)

- [x] 2.1 `cli.main`, `hooks.main` and `_log`, `mcp_server._reasons(tool)`,
  `loop.RepeatedErrors` and `loop.log`, the server's exception handler, `server.log`
  rotated at start and copy-truncated while the server runs. Check: `uv run pytest tests/test_cli.py tests/test_runtime.py
  tests/test_mcp_server.py tests/test_loop.py tests/test_server_system.py
  tests/test_telemetry.py -n auto`.
- [x] 2.2 Integration: a failing hook of the fake agent journals and queues. Check:
  `uv run pytest -m integration -n auto tests/integration/test_telemetry_processes.py`.

## 3. Report, sender and CLI (D7–D11)

- [x] 3.1 `report`, `batch`, `send`, `kick`, `_post` (PostHog batch, no profiles, no
  GeoIP; the outbox's 30-day age and the report's 30-day window; 2 s per network operation, ended after 30 s, silent on any failure, bounded
  while unreachable); `state.spawned_provider`, `state.usage_counts`; the `telemetry_endpoint`
  fixture. Check: `uv run pytest tests/test_telemetry.py tests/test_state.py -n auto`.
- [x] 3.2 `lado telemetry status|on|off|show|send`, the question of `lado start` and
  `lado ui`, the kick after a human's command. Check: `uv run pytest
  tests/test_cli_telemetry.py -n auto`.

## 4. Kicks (D7)

- [x] 4.1 The session loop and the UI server kick every `KICK_EVERY`; integration send to
  a local endpoint, and `lado start` with an unreachable one. Check: `uv run pytest tests/test_loop.py -n auto`, `uv run pytest -m
  integration -n auto tests/integration/test_telemetry_processes.py`.

## 5. API (D13)

- [x] 5.1 `GET`/`POST /api/telemetry`, `GET /api/telemetry/preview`,
  `SystemInfo.telemetry`, the report's `- Statistics:` line; `make web-types`, both
  generated files committed. Check: `uv run pytest tests/test_server_system.py
  tests/test_doctor.py -n auto`, `make web`.

## 6. Web UI (D13; mockup 1A, 2, 3)

- [x] 6.1 `Telemetry.tsx` (banner, Settings section), the System panel's row, styles;
  vitest. Check: `make web`.
- [x] 6.2 UI e2e with screenshots, attached to `build-report`. Check: `uv run pytest -m
  ui tests/ui/test_statistics.py tests/ui/test_system_panel.py`.

## 7. Docs

- [x] 7.1 `docs/telemetry.md` with the fields test; AGENTS.md, docs/design/ui.md,
  README.md, CHANGELOG.md. Check: `uv run pytest tests/test_telemetry.py -n auto -k docs`.

## 8. Regression run

- [x] 8.1 `make lint`, `make test`, the integration and UI files above, `make web`,
  `openspec validate usage-telemetry --strict`, `openspec validate --specs --strict`;
  results in `build-report`.
