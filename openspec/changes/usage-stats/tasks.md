Plan: `docs/superpowers/plans/2026-10-14-usage-stats.md` (each task's tests and steps).
Design doc: `docs/superpowers/specs/2026-10-14-usage-stats-design.md`.

## 1. The usage table (D1-D4, D10, D12)

- [ ] 1.1 `spawned_detail` with the role's kit (and the tests that pin it), `usage`, `usage_time`, `USAGE_KINDS`, `USAGE_TRIGGERS`, the backfill, schema 27
  (`MIGRATIONS[26]`); `tests/agent_helpers.schema_before`. Check: `uv run pytest
  tests/test_usage.py tests/test_state.py -n auto` and the tests that use
  `previous_schema`.

## 2. Reading it (D5, D6, D9)

- [ ] 2.1 `usage_counts` from `usage` (same shape), `usage_summary`, `usage_start`;
  `telemetry.lado_errors`; the report counts a forgotten session. Check: `uv run pytest
  tests/test_usage.py tests/test_telemetry.py tests/test_cli_telemetry.py -n auto`.

## 3. The command (D7, D8)

- [ ] 3.1 `stats.py`, the `stats` parser and `cmd_stats`, no kick after `stats`. Check:
  `uv run pytest tests/test_stats.py tests/test_cli.py tests/test_lazy_imports.py -n auto`.

## 4. End to end

- [ ] 4.1 `tests/integration/test_usage_stats.py`: start, spawn, stop, stats, forget,
  stats. Check: `uv run pytest -m integration -n auto tests/integration/test_usage_stats.py`.

## 5. Docs

- [ ] 5.1 CHANGELOG.md (`0.38.0 (unreleased)`), AGENTS.md, docs/telemetry.md.

## 6. Regression

- [ ] 6.1 `make lint`, `make test`, the changed integration files with `-m integration`,
  `openspec validate usage-stats --strict`, `openspec validate --specs --strict`; the
  output of `lado stats` by hand, and a migration of a copy of a real schema-26 `lado.db`,
  in the build report.
