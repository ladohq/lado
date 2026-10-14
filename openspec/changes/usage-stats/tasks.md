Plan: `docs/superpowers/plans/2026-10-14-usage-stats.md` (each task's tests and steps).
Design doc: `docs/superpowers/specs/2026-10-14-usage-stats-design.md`.

## 1. Forgotten usage (D1-D4)

- [ ] 1.1 `forgotten_usage` (schema 27, `MIGRATIONS[26]`), `USAGE_KINDS`, the copy in
  `delete_session`, `usage_counts` over both tables, `usage_start`;
  `tests/agent_helpers.schema_before`. Check: `uv run pytest tests/test_state.py -n auto`
  and the tests that use `previous_schema`.

## 2. Telemetry (D3, D6)

- [ ] 2.1 `telemetry.lado_errors` (renamed from `_lado_errors`); the report counts a
  forgotten session. Check: `uv run pytest tests/test_telemetry.py
  tests/test_cli_telemetry.py -n auto`.

## 3. The command (D5, D7, D8)

- [ ] 3.1 `stats.py`, the `stats` parser and `cmd_stats`, no kick after `stats`. Check:
  `uv run pytest tests/test_stats.py tests/test_cli.py tests/test_lazy_imports.py -n auto`.

## 4. End to end

- [ ] 4.1 `tests/integration/test_usage_stats.py`: start, stop, stats, forget, stats.
  Check: `uv run pytest -m integration -n auto tests/integration/test_usage_stats.py`.

## 5. Docs

- [ ] 5.1 CHANGELOG.md (`0.38.0 (unreleased)`), AGENTS.md, docs/telemetry.md.

## 6. Regression

- [ ] 6.1 `make lint`, `make test`, the two integration files with `-m integration`,
  `openspec validate usage-stats --strict`, `openspec validate --specs --strict`; the
  output of `lado stats` by hand in the build report.
